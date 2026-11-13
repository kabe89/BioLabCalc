"""
Module: biolabcalc.eln.api.routes.custom_experiments
Component: Dynamic No-Code Experiment Customization REST API
Architectural Role: REST endpoints exposing template management, schema introspection,
formula evaluation, and custom experiment entry logging for the BioLabCalc ELN.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

from ...services.custom_experiment_service import get_custom_experiment_service
from ..auth import UserSession, get_auth_service
from ..router import Router

router = Router(prefix="/api/v1/custom-experiments")
custom_service = get_custom_experiment_service()
auth_service = get_auth_service()


@router.get("/templates")
def list_templates(
    category: Optional[str] = None,
    current_user: Optional[UserSession] = None,
) -> Dict[str, Any]:
    """
    List all available experiment templates, optionally filtered by category.

    Parameter category (Optional[str]): Category filter (e.g. 'General', 'Molecular Biology').
    Parameter current_user (Optional[UserSession]): Authenticated session if available.
    Return Type: Dict[str, Any]
    """
    templates = custom_service.list_templates(category=category)
    return {
        "status": "success",
        "count": len(templates),
        "templates": [t.to_dict() for t in templates],
    }


@router.post("/templates")
def register_template(
    payload: Dict[str, Any],
    current_user: Optional[UserSession] = None,
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], int]]:
    """
    Register a new custom experiment template.

    Parameter payload (Dict[str, Any]): Template schema definition.
    Parameter current_user (Optional[UserSession]): Authenticated session if available.
    Return Type: Union[Dict[str, Any], Tuple[Dict[str, Any], int]]
    """
    if not isinstance(payload, dict):
        return {"status": "error", "message": "Payload must be a JSON object."}, 400

    if not payload.get("id") and not payload.get("name"):
        return {"status": "error", "message": "Template 'id' or 'name' is required."}, 400

    if current_user and not payload.get("created_by"):
        payload["created_by"] = current_user.username

    try:
        template = custom_service.register_template(payload)
        return {"status": "success", "template": template.to_dict()}, 201
    except ValueError as ve:
        return {"status": "error", "message": str(ve)}, 400


@router.get("/templates/{template_id}")
def get_template(
    template_id: str,
    current_user: Optional[UserSession] = None,
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], int]]:
    """
    Retrieve single custom experiment template schema by its unique identifier.

    Parameter template_id (str): Template ID (e.g. 'tpl_protein_expression').
    Parameter current_user (Optional[UserSession]): Authenticated session.
    Return Type: Union[Dict[str, Any], Tuple[Dict[str, Any], int]]
    """
    template = custom_service.get_template(template_id)
    if not template:
        return {"status": "error", "message": f"Template '{template_id}' not found."}, 404
    return {"status": "success", "template": template.to_dict()}


@router.get("/templates/{template_id}/export")
def export_template(
    template_id: str,
    fmt: Optional[str] = "json",
    current_user: Optional[UserSession] = None,
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], int]]:
    """
    Export a template in JSON or YAML format.
    """
    try:
        exported = custom_service.export_template(template_id, fmt=fmt or "json")
        return {"status": "success", "template_id": template_id, "format": fmt or "json", "data": exported}
    except KeyError:
        return {"status": "error", "message": f"Template '{template_id}' not found."}, 404
    except Exception as e:
        return {"status": "error", "message": str(e)}, 400


@router.post("/templates/import")
def import_template(
    payload: Dict[str, Any],
    current_user: Optional[UserSession] = None,
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], int]]:
    """
    Import a template from JSON or YAML payload.
    """
    raw_payload = payload.get("payload") or payload
    fmt = payload.get("format", "json") if "payload" in payload else "json"
    try:
        tpl = custom_service.import_template(raw_payload, fmt=fmt)
        return {"status": "success", "template": tpl.to_dict()}, 201
    except Exception as e:
        return {"status": "error", "message": f"Import failed: {e}"}, 400


@router.post("/entries")
def create_entry(
    payload: Dict[str, Any],
    current_user: Optional[UserSession] = None,
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], int]]:
    """
    Submit and validate a new custom experiment entry, computing all formula fields.

    Parameter payload (Dict[str, Any]): Entry payload containing template_id, title, form_data.
    Parameter current_user (Optional[UserSession]): Authenticated session.
    Return Type: Union[Dict[str, Any], Tuple[Dict[str, Any], int]]
    """
    if not isinstance(payload, dict):
        return {"status": "error", "message": "Payload must be a JSON object."}, 400

    template_id = payload.get("template_id")
    if not template_id:
        return {"status": "error", "message": "Field 'template_id' is required."}, 400

    title = payload.get("title", "Custom Experiment Entry")
    campaign_id = payload.get("campaign_id")
    form_data = payload.get("form_data", {})
    operator_id = payload.get("operator_id") or (current_user.username if current_user else "active_researcher")

    try:
        entry = custom_service.create_entry(
            template_id=template_id,
            campaign_id=campaign_id,
            title=title,
            form_data=form_data,
            operator_id=operator_id,
        )
        return {"status": "success", "entry": entry.to_dict()}, 201
    except KeyError as ke:
        return {"status": "error", "message": str(ke)}, 404
    except ValueError as ve:
        return {"status": "error", "message": str(ve)}, 400
    except ZeroDivisionError as zde:
        return {"status": "error", "message": f"Calculation error: {zde}"}, 400


@router.get("/entries")
def list_entries(
    campaign_id: Optional[str] = None,
    template_id: Optional[str] = None,
    current_user: Optional[UserSession] = None,
) -> Dict[str, Any]:
    """
    List custom experiment entries, optionally filtered by campaign or template.
    """
    entries = custom_service.list_entries(campaign_id=campaign_id, template_id=template_id)
    return {
        "status": "success",
        "count": len(entries),
        "entries": [e.to_dict() for e in entries],
    }


@router.get("/entries/{entry_id}")
def get_entry(
    entry_id: str,
    current_user: Optional[UserSession] = None,
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], int]]:
    """
    Retrieve custom experiment entry with calculated formula fields by entry ID.

    Parameter entry_id (str): Unique entry ID.
    Parameter current_user (Optional[UserSession]): Authenticated session.
    Return Type: Union[Dict[str, Any], Tuple[Dict[str, Any], int]]
    """
    entry = custom_service.get_entry(entry_id)
    if not entry:
        return {"status": "error", "message": f"Entry '{entry_id}' not found."}, 404
    return {"status": "success", "entry": entry.to_dict()}
