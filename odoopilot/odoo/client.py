from __future__ import annotations

import logging
from typing import Any, cast

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30.0


class OdooError(Exception):
    """Raised when Odoo returns a JSON-RPC error."""

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class OdooClient:
    """Async Odoo JSON-RPC client.

    Authenticates per-user using Odoo's xmlrpc-style uid + password.
    All calls are stateless (no session cookie) so they work without a browser session.
    """

    def __init__(
        self,
        url: str,
        db: str,
        *,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._url = url.rstrip("/")
        self._db = db
        self._http = httpx.AsyncClient(timeout=timeout)
        self._uid_cache: dict[str, int] = {}  # cache uid lookups by username

    async def authenticate(self, username: str, password: str) -> int:
        """Return the Odoo uid for a username/password pair."""
        cache_key = f"{username}:{password}"
        if cache_key in self._uid_cache:
            return self._uid_cache[cache_key]

        result = await self._jsonrpc(
            "/web/dataset/call_kw",
            model="res.users",
            method="search",
            args=[[["login", "=", username]]],
            kwargs={},
            uid=1,
            password=password,
            # authenticate endpoint uses a different path
            _auth_endpoint=True,
            _auth_username=username,
            _auth_password=password,
        )
        uid = result[0] if result else None
        if not uid:
            raise OdooError(f"Authentication failed for user '{username}'")
        uid_int = int(uid)
        self._uid_cache[cache_key] = uid_int
        return uid_int

    async def search_read(
        self,
        model: str,
        domain: list[Any],
        fields: list[str],
        *,
        uid: int,
        password: str,
        limit: int = 80,
        offset: int = 0,
        order: str | None = None,
    ) -> list[dict[str, Any]]:
        """Call search_read on an Odoo model."""
        kwargs: dict[str, Any] = {
            "fields": fields,
            "limit": limit,
            "offset": offset,
        }
        if order:
            kwargs["order"] = order
        return cast(
            list[dict[str, Any]],
            await self._call(
                model=model,
                method="search_read",
                args=[domain],
                kwargs=kwargs,
                uid=uid,
                password=password,
            ),
        )

    async def read(
        self,
        model: str,
        ids: int | list[int],
        fields: list[str],
        *,
        uid: int,
        password: str,
    ) -> list[dict[str, Any]]:
        """Call read on an Odoo model."""
        id_list = [ids] if isinstance(ids, int) else ids
        return cast(
            list[dict[str, Any]],
            await self._call(
                model=model,
                method="read",
                args=[id_list, fields],
                kwargs={},
                uid=uid,
                password=password,
            ),
        )

    async def search(
        self,
        model: str,
        domain: list[Any],
        *,
        uid: int,
        password: str,
        limit: int = 80,
        offset: int = 0,
    ) -> list[int]:
        """Call search on an Odoo model, returning record IDs."""
        return cast(
            list[int],
            await self._call(
                model=model,
                method="search",
                args=[domain],
                kwargs={"limit": limit, "offset": offset},
                uid=uid,
                password=password,
            ),
        )

    async def execute_kw(
        self,
        model: str,
        method: str,
        args: list[Any],
        *,
        uid: int,
        password: str,
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        """Call an arbitrary method on an Odoo model."""
        return await self._call(
            model=model,
            method=method,
            args=args,
            kwargs=kwargs or {},
            uid=uid,
            password=password,
        )

    async def close(self) -> None:
        await self._http.aclose()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _call(
        self,
        *,
        model: str,
        method: str,
        args: list[Any],
        kwargs: dict[str, Any],
        uid: int,
        password: str,
    ) -> Any:
        return await self._jsonrpc(
            "/web/dataset/call_kw",
            model=model,
            method=method,
            args=args,
            kwargs=kwargs,
            uid=uid,
            password=password,
        )

    async def _jsonrpc(
        self,
        path: str,
        *,
        model: str,
        method: str,
        args: list[Any],
        kwargs: dict[str, Any],
        uid: int,
        password: str,
        _auth_endpoint: bool = False,
        _auth_username: str | None = None,
        _auth_password: str | None = None,
    ) -> Any:
        if _auth_endpoint:
            payload = {
                "jsonrpc": "2.0",
                "method": "call",
                "id": 1,
                "params": {
                    "service": "common",
                    "method": "authenticate",
                    "args": [self._db, _auth_username, _auth_password, {}],
                },
            }
            url = f"{self._url}/jsonrpc"
        else:
            payload = {
                "jsonrpc": "2.0",
                "method": "call",
                "id": 1,
                "params": {
                    "model": model,
                    "method": method,
                    "args": args,
                    "kwargs": {
                        **kwargs,
                        "context": {"lang": "en_US"},
                    },
                },
            }
            url = f"{self._url}/web/dataset/call_kw/{model}/{method}"

        headers = {
            "Content-Type": "application/json",
        }
        if not _auth_endpoint:
            # Use basic auth header to pass uid/password
            import base64

            creds = base64.b64encode(f"{uid}:{password}".encode()).decode()
            headers["Authorization"] = f"Basic {creds}"

        logger.debug("Odoo RPC %s %s.%s", path, model, method)
        resp = await self._http.post(url, json=payload, headers=headers)
        resp.raise_for_status()

        data = resp.json()
        if "error" in data:
            err = data["error"]
            msg = err.get("data", {}).get("message") or err.get("message", "Unknown Odoo error")
            raise OdooError(msg, code=err.get("code"))

        return data.get("result")
