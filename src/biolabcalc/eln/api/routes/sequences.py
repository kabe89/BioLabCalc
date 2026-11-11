"""
Module: biolabcalc.eln.api.routes.sequences
Component: Sequence Registry & Biophysical Property REST Endpoints
Agent: @agent: eln-api-agent
Architectural Role: REST routes exposing primer/plasmid/aptamer/protein construct registration,
physicochemical property calculations (Tm, GC%, MW, pI, e280, A0.1%), and construct lookups.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ...services.sequence_service import get_sequence_service
from ..auth import UserSession, get_auth_service
from ..router import Router

router = Router(prefix="/api/sequences")
sequence_service = get_sequence_service()
auth_service = get_auth_service()


@router.get("")
def list_sequences(entity_type: Optional[str] = None, current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    List all registered biological sequences, optionally filtered by type.

    Agent: @agent: eln-api-agent
    Parameter entity_type (Optional[str]): Filter ('primer', 'plasmid', 'aptamer', 'protein_construct').
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    seqs = sequence_service.list_sequences(entity_type=entity_type)
    return {"status": "success", "count": len(seqs), "sequences": [s.to_dict() for s in seqs]}


@router.post("")
def register_sequence(payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Register a biological sequence entity and compute its thermodynamic and biophysical profile.

    Agent: @agent: eln-api-agent
    Parameter payload (Dict[str, Any]): Sequence entity definition (entity_id, name, entity_type, sequence, description, tags, metadata).
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    user_id = current_user.username if current_user else "active_researcher"
    entity = sequence_service.register_sequence(
        entity_id=payload["entity_id"],
        name=payload["name"],
        entity_type=payload["entity_type"],
        sequence=payload["sequence"],
        description=payload.get("description", ""),
        tags=payload.get("tags"),
        metadata=payload.get("metadata"),
        created_by=user_id,
    )
    return {"status": "success", "sequence": entity.to_dict()}


@router.get("/{entity_id}")
def get_sequence(entity_id: str, current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Retrieve single sequence entity and biophysical properties by ID.

    Agent: @agent: eln-api-agent
    Parameter entity_id (str): Construct or primer ID.
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    entity = sequence_service.get_sequence(entity_id)
    if not entity:
        return {"status": "error", "message": f"Sequence entity '{entity_id}' not found."}, 404
    return {"status": "success", "sequence": entity.to_dict()}


@router.post("/calculate")
def calculate_properties(payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Calculate biophysical properties (Tm, GC%, MW, pI, e280, A0.1%) on arbitrary sequence.

    Agent: @agent: eln-api-agent
    Parameter payload (Dict[str, Any]): Calculation payload ('sequence': str, 'entity_type': str).
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    seq = payload["sequence"]
    entity_type = payload.get("entity_type", "protein_construct")
    props = sequence_service.calculate_properties(sequence=seq, entity_type=entity_type)
    return {"status": "success", "properties": props}
