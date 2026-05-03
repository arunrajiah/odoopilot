"""In-process rate limiting and bounded worker pool for the webhook handlers.

Why this exists
---------------

Both webhooks (Telegram, WhatsApp) previously spawned a fresh
``threading.Thread(daemon=True)`` per inbound update with no upper bound.
Combined with the per-message LLM call (which is paid, often metered, and
takes a few seconds to return), an unbounded inbound rate is two real
problems at once:

1. **Cost amplification** — a malicious or misbehaving sender can drive
   arbitrary LLM API spend on the operator's account by repeatedly sending
   messages to a linked chat.
2. **Resource exhaustion** — unbounded thread spawning will eventually
   starve the Odoo worker process.

This module bounds both:

* :func:`allow` — a sliding-window rate limiter keyed by ``(channel,
  chat_id)``. Returns ``False`` when the linked user has exceeded their
  per-hour message budget; the caller drops the message silently (returning
  200 to the platform so it doesn't retry-storm us).
* :func:`submit` — submit a callable to a bounded thread pool. When the
  pool is saturated, returns ``False`` and the caller drops the message —
  again returning 200 so the platform doesn't retry-storm us.

Configuration
-------------

Three ``ir.config_parameter`` keys override the defaults; values are read
once at first use and re-read after an Odoo restart:

* ``odoopilot.rate_limit_per_hour`` (default ``30``)
* ``odoopilot.rate_limit_window_seconds`` (default ``3600``)
* ``odoopilot.worker_pool_size`` (default ``8``)
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

_logger = logging.getLogger(__name__)

_DEFAULT_LIMIT = 30
_DEFAULT_WINDOW = 3600
_DEFAULT_POOL_SIZE = 8


# Opportunistic GC of empty buckets runs every Nth ``allow()`` call.
# Without it, ``_buckets`` grows by one entry per unique (channel,
# chat_id) ever seen -- benign for installs with a fixed team, but a
# slow leak under churn. The sweep is cheap (it's a dict comprehension
# over keys whose bucket has gone empty) and amortises across many
# messages.
_BUCKET_GC_INTERVAL = 256


class RateLimiter:
    """Thread-safe sliding-window rate limiter keyed by (channel, chat_id)."""

    def __init__(self, limit: int = _DEFAULT_LIMIT, window: int = _DEFAULT_WINDOW):
        self._limit = max(1, int(limit))
        self._window = max(1, int(window))
        self._buckets: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()
        self._call_count = 0

    def allow(self, channel: str, chat_id: str) -> bool:
        """Return ``True`` if this message should be processed.

        Returns ``False`` when the linked user has exceeded their budget for
        the current window. The bucket is pruned of stale entries each call
        so memory usage is bounded by the number of currently-active senders.
        Every :data:`_BUCKET_GC_INTERVAL` calls we additionally sweep the
        whole dict and drop keys whose bucket is empty after pruning -- this
        prevents unbounded growth across (channel, chat_id) churn.
        """
        if not channel or not chat_id:
            # No way to attribute the message — fail open. The caller still
            # has to process it; the bounded pool below limits concurrency.
            return True
        now = time.monotonic()
        cutoff = now - self._window
        key = (channel, chat_id)
        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            allowed = len(bucket) < self._limit
            if allowed:
                bucket.append(now)

            # Opportunistic sweep every Nth call. Drop empty buckets so
            # the dict size tracks active senders, not lifetime distinct
            # senders.
            self._call_count += 1
            if self._call_count % _BUCKET_GC_INTERVAL == 0:
                self._gc_empty_buckets(cutoff)

            return allowed

    def _gc_empty_buckets(self, cutoff: float) -> None:
        """Drop bucket entries with no timestamps left in the window.

        Caller must hold ``self._lock``. Called from inside
        :meth:`allow` on a fixed cadence; never invoked directly.
        """
        stale_keys = []
        for k, b in self._buckets.items():
            # Re-prune in case a bucket has gone stale since its last
            # touch -- otherwise a key that was active long ago and
            # never seen again would never be collected.
            while b and b[0] < cutoff:
                b.popleft()
            if not b:
                stale_keys.append(k)
        for k in stale_keys:
            del self._buckets[k]


class BoundedPool:
    """Bounded thread pool with non-blocking submit.

    A plain :class:`concurrent.futures.ThreadPoolExecutor` queues work
    indefinitely when ``max_workers`` is exceeded — that re-introduces the
    unbounded growth we are trying to prevent. We add a
    :class:`threading.BoundedSemaphore` of size ``2 * max_workers`` so
    submissions fail fast when both the worker threads and the small queue
    behind them are full.
    """

    def __init__(self, max_workers: int = _DEFAULT_POOL_SIZE):
        max_workers = max(1, int(max_workers))
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="odoopilot"
        )
        self._sem = threading.BoundedSemaphore(max_workers * 2)

    def submit(self, fn: Callable, *args, **kwargs) -> bool:
        if not self._sem.acquire(blocking=False):
            return False  # Saturated — drop the message.

        def _wrapper():
            try:
                fn(*args, **kwargs)
            finally:
                self._sem.release()

        try:
            self._executor.submit(_wrapper)
            return True
        except RuntimeError:
            # Pool shut down (e.g. during Odoo shutdown). Release and drop.
            self._sem.release()
            return False


# Module-level singletons. Initialised lazily from ir.config_parameter on
# first use; an Odoo restart re-reads the values.
_limiter: RateLimiter | None = None
_pool: BoundedPool | None = None
_init_lock = threading.Lock()


def _ensure_initialized(env) -> None:
    global _limiter, _pool
    if _limiter is not None and _pool is not None:
        return
    with _init_lock:
        cfg = env["ir.config_parameter"].sudo()
        if _limiter is None:
            limit = int(cfg.get_param("odoopilot.rate_limit_per_hour", _DEFAULT_LIMIT))
            window = int(
                cfg.get_param("odoopilot.rate_limit_window_seconds", _DEFAULT_WINDOW)
            )
            _limiter = RateLimiter(limit, window)
        if _pool is None:
            size = int(cfg.get_param("odoopilot.worker_pool_size", _DEFAULT_POOL_SIZE))
            _pool = BoundedPool(size)


def allow(env, channel: str, chat_id: str) -> bool:
    """Check the per-(channel, chat_id) rate limit. Returns False to drop."""
    _ensure_initialized(env)
    if _limiter is None:  # pragma: no cover -- _ensure_initialized guarantees
        raise RuntimeError("OdooPilot rate limiter not initialised")
    allowed = _limiter.allow(channel, chat_id)
    if not allowed:
        _logger.warning(
            "OdooPilot: rate-limited %s/%s — dropping message", channel, chat_id
        )
    return allowed


def submit(env, fn: Callable, *args, **kwargs) -> bool:
    """Submit work to the bounded pool. Returns False when saturated."""
    _ensure_initialized(env)
    if _pool is None:  # pragma: no cover -- _ensure_initialized guarantees
        raise RuntimeError("OdooPilot worker pool not initialised")
    ok = _pool.submit(fn, *args, **kwargs)
    if not ok:
        _logger.warning(
            "OdooPilot: worker pool saturated — dropping update for %s",
            fn.__name__ if hasattr(fn, "__name__") else fn,
        )
    return ok


# ── Test hooks ────────────────────────────────────────────────────────────────
# These are used by the regression tests to install a fresh limiter/pool with
# specific limits without restarting the Odoo process.


def _reset_for_tests(
    *,
    limit: int | None = None,
    window: int | None = None,
    pool_size: int | None = None,
) -> None:
    """Replace the module-level singletons. Tests only."""
    global _limiter, _pool
    with _init_lock:
        if limit is not None or window is not None:
            _limiter = RateLimiter(
                limit if limit is not None else _DEFAULT_LIMIT,
                window if window is not None else _DEFAULT_WINDOW,
            )
        if pool_size is not None:
            _pool = BoundedPool(pool_size)
