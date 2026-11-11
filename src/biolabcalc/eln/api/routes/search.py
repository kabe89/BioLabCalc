"""
Module: biolabcalc.eln.api.routes.search
Component: Unified Multi-Modal Search REST Endpoints
Architectural Role: REST routes exposing cross-cutting search across campaigns, daily notebook entries,
sequence constructs, cryogenic inventory tubes, FPLC fraction pools, gel records, and immutable audit logs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ...services.audit_service import get_audit_service
from ...services.campaign_service import get_campaign_service
from ...services.fplc_service import get_fplc_service
from ...services.gel_service import get_gel_service
from ...services.inventory_service import get_inventory_service
from ...services.sequence_service import get_sequence_service
from ..auth import UserSession, get_auth_service
from ..router import Router

router = Router(prefix="/api/search")
campaign_service = get_campaign_service()
sequence_service = get_sequence_service()
inventory_service = get_inventory_service()
fplc_service = get_fplc_service()
gel_service = get_gel_service()
audit_service = get_audit_service()
auth_service = get_auth_service()


@router.get("")
def search(
    q: Optional[str] = None,
    entity_type: Optional[str] = None,
    limit: int = 50,
    current_user: Optional[UserSession] = None,
) -> Dict[str, Any]:
    """
    Execute unified keyword search across all ELN/LIMS entities.

    Parameter q (Optional[str]): Search query term (case-insensitive substring match).
    Parameter entity_type (Optional[str]): Optional filter ('campaign', 'sequence', 'tube', 'fplc', 'gel', 'audit').
    Parameter limit (int): Maximum items per category (default: 50).
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    query = (q or "").strip().lower()
    results: Dict[str, List[Dict[str, Any]]] = {
        "campaigns": [],
        "sequences": [],
        "tubes": [],
        "fraction_pools": [],
        "gels": [],
        "audit_events": [],
    }

    if not query:
        return {"status": "success", "query": "", "total_hits": 0, "results": results}

    # 1. Search Campaigns
    if entity_type is None or entity_type in ("campaign", "campaigns"):
        for cmp in campaign_service.list_campaigns():
            if (
                query in cmp.campaign_id.lower()
                or query in cmp.title.lower()
                or query in cmp.description.lower()
                or query in cmp.construct_id.lower()
            ):
                results["campaigns"].append(cmp.to_dict())

    # 2. Search Sequences
    if entity_type is None or entity_type in ("sequence", "sequences", "construct"):
        for seq in sequence_service.list_sequences():
            if (
                query in seq.entity_id.lower()
                or query in seq.name.lower()
                or query in seq.description.lower()
                or any(query in t.lower() for t in seq.tags)
            ):
                results["sequences"].append(seq.to_dict())

    # 3. Search Inventory Tubes
    if entity_type is None or entity_type in ("tube", "tubes", "inventory"):
        with inventory_service._lock:
            for tube in inventory_service._tubes.values():
                if (
                    query in tube.tube_id.lower()
                    or query in tube.barcode.lower()
                    or query in tube.sample_name.lower()
                    or (tube.construct_id and query in tube.construct_id.lower())
                ):
                    results["tubes"].append(tube.to_dict())

    # 4. Search FPLC Fraction Pools
    if entity_type is None or entity_type in ("fplc", "pool", "fraction_pools"):
        with fplc_service._lock:
            for pool in fplc_service._pools.values():
                if (
                    query in pool.pool_id.lower()
                    or query in pool.run_id.lower()
                    or query in pool.construct_id.lower()
                ):
                    results["fraction_pools"].append(pool.to_dict())

    # 5. Search Gels
    if entity_type is None or entity_type in ("gel", "gels"):
        with gel_service._lock:
            for gel in gel_service._gels.values():
                if query in gel.gel_id.lower() or query in gel.title.lower():
                    results["gels"].append(gel.to_dict())

    # 6. Search Audit Trail
    if entity_type is None or entity_type in ("audit", "audit_trail"):
        for evt in audit_service.get_trail(limit=limit):
            if (
                query in evt.entity_type.lower()
                or query in evt.entity_id.lower()
                or query in evt.action.lower()
                or query in evt.performed_by.lower()
            ):
                results["audit_events"].append(evt.to_dict())

    total_hits = sum(len(v) for v in results.values())
    return {
        "status": "success",
        "query": query,
        "total_hits": total_hits,
        "results": results,
    }
