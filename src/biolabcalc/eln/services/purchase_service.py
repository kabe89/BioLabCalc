"""
Module: biolabcalc.eln.services.purchase_service
Component: Laboratory Reagent, Consumable & Equipment Purchase Order Service
Architectural Role: Core ELN service governing the complete procurement lifecycle
(REQUESTED -> APPROVED -> ORDERED -> RECEIVED -> STOCKED), grant spend tracking, and 1-click inventory stocking.
"""

from __future__ import annotations

import csv
import io
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..storage.sqlite_store import SQLiteStore, get_sqlite_store

logger = logging.getLogger("biolabcalc.eln.services.purchase_service")

VALID_STATUSES = ("REQUESTED", "APPROVED", "ORDERED", "RECEIVED", "STOCKED", "CANCELLED")


class PurchaseService:
    """Thread-safe persistent service managing lab purchasing, budget tracking, and receipt handoff."""

    def __init__(self, store: Optional[SQLiteStore] = None) -> None:
        self._store = store or get_sqlite_store()
        self._lock = threading.RLock()

    def create_order(
        self,
        item_name: str,
        vendor: str,
        quantity: float = 1.0,
        unit: str = "unit",
        unit_price_usd: float = 0.0,
        catalog_number: str = "",
        lot_number: str = "",
        category: str = "consumable",
        grant_code: str = "",
        requested_by: str = "active_researcher",
        notes: str = "",
    ) -> Dict[str, Any]:
        """Create a new purchase requisition."""
        with self._lock:
            order_id = f"po_{uuid.uuid4().hex[:10]}"
            now_iso = datetime.now(timezone.utc).isoformat()
            qty = max(0.01, float(quantity))
            price = max(0.0, float(unit_price_usd))
            total = round(qty * price, 2)

            data = {
                "order_id": order_id,
                "item_name": item_name.strip(),
                "vendor": vendor.strip(),
                "catalog_number": catalog_number.strip(),
                "lot_number": lot_number.strip(),
                "category": category.strip().lower(),
                "quantity": qty,
                "unit": unit.strip(),
                "unit_price_usd": price,
                "total_cost_usd": total,
                "grant_code": grant_code.strip() or "UNASSIGNED",
                "requested_by": requested_by.strip(),
                "status": "REQUESTED",
                "ordered_at": None,
                "received_at": None,
                "linked_inventory_id": None,
                "notes": notes.strip(),
                "created_at": now_iso,
            }
            self._store.put_entity("purchase_order", order_id, data)
            logger.info(f"Created purchase order '{item_name}' ({order_id}) - ${total:.2f}")
            return data

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve purchase order by identifier."""
        return self._store.get_entity("purchase_order", order_id)

    def list_orders(
        self,
        status: Optional[str] = None,
        vendor: Optional[str] = None,
        grant_code: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List purchase orders with optional status, vendor, or grant filters."""
        orders = self._store.list_entities("purchase_order")
        if status:
            norm_st = status.strip().upper()
            orders = [o for o in orders if o.get("status") == norm_st]
        if vendor:
            orders = [o for o in orders if vendor.lower() in o.get("vendor", "").lower()]
        if grant_code:
            orders = [o for o in orders if o.get("grant_code") == grant_code]
        return sorted(orders, key=lambda x: x.get("created_at", ""), reverse=True)

    def update_order_status(
        self,
        order_id: str,
        new_status: str,
        lot_number: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update procurement status along lifecycle: REQUESTED -> APPROVED -> ORDERED -> RECEIVED -> STOCKED."""
        with self._lock:
            order = self.get_order(order_id)
            if not order:
                raise ValueError(f"Purchase order '{order_id}' not found.")

            st = new_status.strip().upper()
            if st not in VALID_STATUSES:
                raise ValueError(f"Invalid status '{st}'. Must be one of: {', '.join(VALID_STATUSES)}")

            now_iso = datetime.now(timezone.utc).isoformat()
            order["status"] = st

            if st == "ORDERED" and not order.get("ordered_at"):
                order["ordered_at"] = now_iso
            elif st in ("RECEIVED", "STOCKED") and not order.get("received_at"):
                order["received_at"] = now_iso

            if lot_number:
                order["lot_number"] = lot_number.strip()
            if notes:
                prev = order.get("notes", "")
                order["notes"] = f"{prev}\n{notes}".strip() if prev else notes.strip()

            self._store.put_entity("purchase_order", order_id, order)
            logger.info(f"Updated purchase order {order_id} status to '{st}'")
            return order

    update_status = update_order_status

    def receive_and_stock(
        self,
        order_id: str,
        box_id: str = "BOX-DEFAULT",
        slot: str = "A1",
        lot_number: Optional[str] = None,
        concentration: Optional[str] = None,
        location_id: Optional[str] = None,
        aliquot_count: int = 1,
    ) -> Dict[str, Any]:
        """Receive item and stock directly into LIMS inventory, creating linked freezer tube(s)."""
        with self._lock:
            order = self.get_order(order_id)
            if not order:
                raise ValueError(f"Purchase order '{order_id}' not found.")

            target_box = location_id or box_id
            now_iso = datetime.now(timezone.utc).isoformat()
            if lot_number:
                order["lot_number"] = lot_number.strip()

            tubes: List[Dict[str, Any]] = []
            count = max(1, int(aliquot_count))
            for i in range(count):
                tube_id = f"TUBE-PO-{uuid.uuid4().hex[:8].upper()}"
                tube_record = {
                    "tube_id": tube_id,
                    "barcode": f"BC-{tube_id}",
                    "sample_name": f"{order['item_name']} (Lot: {order.get('lot_number') or 'N/A'}" + (f" #{i+1})" if count > 1 else ")"),
                    "box_id": target_box,
                    "slot": f"A{i+1}" if count > 1 else slot,
                    "volume_ul": 1000.0,
                    "concentration": concentration or "Stock",
                    "vendor": order["vendor"],
                    "catalog_number": order.get("catalog_number", ""),
                    "lot_number": order.get("lot_number", ""),
                    "linked_order_id": order_id,
                    "received_at": now_iso,
                    "created_at": now_iso,
                }
                # Persist tube in entity store
                self._store.put_entity("inventory_tube", tube_id, tube_record)
                tubes.append(tube_record)

            order["status"] = "STOCKED"
            order["received_at"] = now_iso
            order["linked_inventory_id"] = tubes[0]["tube_id"] if tubes else None
            self._store.put_entity("purchase_order", order_id, order)
            logger.info(f"Received order {order_id} and stocked {len(tubes)} tube(s) in {target_box}")

            result = dict(order)
            result["order"] = order
            result["tubes"] = tubes
            return result

    def get_spend_summary(
        self,
        grant_code: Optional[str] = None,
        month: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Calculate spend breakdown by grant, category, and order lifecycle counts."""
        orders = self.list_orders(grant_code=grant_code)
        if month:
            # month in YYYY-MM format
            orders = [o for o in orders if o.get("created_at", "").startswith(month)]

        total_spend = sum(float(o.get("total_cost_usd", 0.0)) for o in orders if o.get("status") != "CANCELLED")
        spend_by_grant: Dict[str, float] = {}
        spend_by_category: Dict[str, float] = {}
        status_counts: Dict[str, int] = {}

        for o in orders:
            st = o.get("status", "REQUESTED")
            status_counts[st] = status_counts.get(st, 0) + 1

            if st != "CANCELLED":
                cost = float(o.get("total_cost_usd", 0.0))
                g = o.get("grant_code") or "UNASSIGNED"
                spend_by_grant[g] = round(spend_by_grant.get(g, 0.0) + cost, 2)

                cat = o.get("category") or "consumable"
                spend_by_category[cat] = round(spend_by_category.get(cat, 0.0) + cost, 2)

        return {
            "total_orders": len(orders),
            "total_spend_usd": round(total_spend, 2),
            "status_counts": status_counts,
            "spend_by_grant": spend_by_grant,
            "spend_by_category": spend_by_category,
        }

    def export_csv(self, grant_code: Optional[str] = None) -> str:
        """Export orders into CSV table."""
        orders = self.list_orders(grant_code=grant_code)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "Order ID", "Item Name", "Vendor", "Catalog #", "Lot #",
            "Category", "Quantity", "Unit", "Unit Price ($)", "Total Cost ($)",
            "Grant Code", "Requested By", "Status", "Ordered At", "Received At", "Linked Tube ID"
        ])
        for o in orders:
            writer.writerow([
                o["order_id"], o["item_name"], o["vendor"], o.get("catalog_number", ""),
                o.get("lot_number", ""), o.get("category", ""), o.get("quantity", 1),
                o.get("unit", ""), o.get("unit_price_usd", 0), o.get("total_cost_usd", 0),
                o.get("grant_code", ""), o.get("requested_by", ""), o.get("status", ""),
                o.get("ordered_at") or "", o.get("received_at") or "", o.get("linked_inventory_id") or ""
            ])
        return buf.getvalue()

    export_orders_csv = export_csv


_purchase_service_instance: Optional[PurchaseService] = None
_purchase_service_lock = threading.Lock()


def get_purchase_service() -> PurchaseService:
    """Retrieve singleton instance of PurchaseService."""
    global _purchase_service_instance
    if _purchase_service_instance is None:
        with _purchase_service_lock:
            if _purchase_service_instance is None:
                _purchase_service_instance = PurchaseService()
    return _purchase_service_instance
