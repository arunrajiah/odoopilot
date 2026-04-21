"""Typed wrappers over common Odoo model shapes returned by search_read/read."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Many2oneField(BaseModel):
    id: int
    name: str

    @classmethod
    def from_tuple(cls, value: list[Any] | bool) -> Many2oneField | None:
        if not isinstance(value, list) or not value:
            return None
        return cls(id=value[0], name=value[1])


class OdooProduct(BaseModel):
    id: int
    name: str
    default_code: str | None = Field(default=None)
    barcode: str | None = Field(default=None)
    qty_available: float = Field(default=0.0)
    uom_name: str = Field(default="Units")

    @classmethod
    def from_record(cls, rec: dict[str, Any]) -> OdooProduct:
        uom = rec.get("uom_id")
        return cls(
            id=rec["id"],
            name=rec["name"],
            default_code=rec.get("default_code") or None,
            barcode=rec.get("barcode") or None,
            qty_available=float(rec.get("qty_available", 0)),
            uom_name=uom[1] if isinstance(uom, list) else "Units",
        )


class OdooSaleOrder(BaseModel):
    id: int
    name: str
    partner_name: str
    amount_total: float
    state: str
    date_order: str | None = None

    @classmethod
    def from_record(cls, rec: dict[str, Any]) -> OdooSaleOrder:
        partner = rec.get("partner_id")
        return cls(
            id=rec["id"],
            name=rec["name"],
            partner_name=partner[1] if isinstance(partner, list) else "",
            amount_total=float(rec.get("amount_total", 0)),
            state=rec.get("state", ""),
            date_order=rec.get("date_order"),
        )


class OdooTask(BaseModel):
    id: int
    name: str
    project_name: str
    stage_name: str
    date_deadline: str | None = None

    @classmethod
    def from_record(cls, rec: dict[str, Any]) -> OdooTask:
        project = rec.get("project_id")
        stage = rec.get("stage_id")
        return cls(
            id=rec["id"],
            name=rec["name"],
            project_name=project[1] if isinstance(project, list) else "",
            stage_name=stage[1] if isinstance(stage, list) else "",
            date_deadline=rec.get("date_deadline"),
        )


class OdooLeave(BaseModel):
    id: int
    employee_name: str
    holiday_status_name: str
    date_from: str
    date_to: str
    state: str
    number_of_days: float

    @classmethod
    def from_record(cls, rec: dict[str, Any]) -> OdooLeave:
        employee = rec.get("employee_id")
        leave_type = rec.get("holiday_status_id")
        return cls(
            id=rec["id"],
            employee_name=employee[1] if isinstance(employee, list) else "",
            holiday_status_name=leave_type[1] if isinstance(leave_type, list) else "",
            date_from=rec.get("date_from", ""),
            date_to=rec.get("date_to", ""),
            state=rec.get("state", ""),
            number_of_days=float(rec.get("number_of_days", 0)),
        )
