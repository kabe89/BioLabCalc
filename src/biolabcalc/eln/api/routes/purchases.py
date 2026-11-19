"""
Module: biolabcalc.eln.api.routes.purchases
Component: Purchase Requisition & Procurement REST Endpoints
Architectural Role: REST routes for reagent/consumable procurement lifecycle,
grant spend summaries, CSV export, and 1-click receiving into freezer inventory.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ...services.purchase_service import get_purchase_service
from ..auth import UserSession, get_auth_service
from ..router import Router

router = Router(prefix="/api/v1/purchases")
purchase_service = get_purchase_service()
auth_service = get_auth_service()


@router.get("")
def list_purchases(
    status: Optional[str] = None,
    vendor: Optional[str] = None,
    grant_code: Optional[str] = None,
    current_user: Optional[UserSession] = None,
) -> Dict[str, Any]:
    """List purchase orders with optional status, vendor, or grant filter."""
    orders = purchase_service.list_orders(status=status, vendor=vendor, grant_code=grant_code)
    return {"status": "success", "count": len(orders), "orders": orders}


@router.post("")
def create_purchase(payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """Create a new purchase order requisition."""
    user = current_user.username if current_user else payload.get("requested_by", "active_researcher")
    order = purchase_service.create_order(
        item_name=payload["item_name"],
        vendor=payload["vendor"],
        quantity=float(payload.get("quantity", 1.0)),
        unit=payload.get("unit", "unit"),
        unit_price_usd=float(payload.get("unit_price_usd", 0.0)),
        catalog_number=payload.get("catalog_number", ""),
        lot_number=payload.get("lot_number", ""),
        category=payload.get("category", "consumable"),
        grant_code=payload.get("grant_code", ""),
        requested_by=user,
        notes=payload.get("notes", ""),
    )
    return {"status": "success", "order": order}


@router.get("/summary")
def get_purchase_summary(
    grant_code: Optional[str] = None,
    month: Optional[str] = None,
    current_user: Optional[UserSession] = None,
) -> Dict[str, Any]:
    """Get grant and category expenditure analytics."""
    summary = purchase_service.get_spend_summary(grant_code=grant_code, month=month)
    return {"status": "success", "summary": summary}


@router.get("/export")
def export_purchases_csv(grant_code: Optional[str] = None, current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """Export purchase orders to CSV format."""
    csv_text = purchase_service.export_csv(grant_code=grant_code)
    return {"status": "success", "format": "csv", "csv": csv_text}


@router.get("/{order_id}")
def get_purchase(order_id: str, current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """Retrieve details for a single purchase order."""
    order = purchase_service.get_order(order_id)
    if not order:
        return {"status": "error", "message": f"Order '{order_id}' not found"}
    return {"status": "success", "order": order}


@router.put("/{order_id}")
def update_purchase_status(
    order_id: str, payload: Dict[str, Any], current_user: Optional[UserSession] = None
) -> Dict[str, Any]:
    """Transition purchase order status along procurement lifecycle."""
    try:
        updated = purchase_service.update_order_status(
            order_id=order_id,
            new_status=payload["status"],
            lot_number=payload.get("lot_number"),
            notes=payload.get("notes"),
        )
        return {"status": "success", "order": updated}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@router.post("/{order_id}/receive")
def receive_and_stock(
    order_id: str, payload: Optional[Dict[str, Any]] = None, current_user: Optional[UserSession] = None
) -> Dict[str, Any]:
    """1-click receive item and stock directly into LIMS inventory."""
    params = payload or {}
    try:
        stocked = purchase_service.receive_and_stock(
            order_id=order_id,
            box_id=params.get("box_id", "BOX-DEFAULT"),
            slot=params.get("slot", "A1"),
            lot_number=params.get("lot_number"),
            concentration=params.get("concentration"),
        )
        return {"status": "success", "order": stocked}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
