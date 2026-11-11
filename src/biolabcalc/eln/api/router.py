"""
Module: biolabcalc.eln.api.router
Component: Lightweight ASGI & REST Route Registry Engine
Agent: @agent: eln-api-agent
Architectural Role: Core routing utility providing method decorators (@router.get, @router.post, etc.),
path parameter extraction (e.g. /api/campaigns/{id}), JSON payload parsing, and standard ASGI 3.0 dispatch.
"""

from __future__ import annotations

import inspect
import json
import re
import urllib.parse
from typing import Any, Callable, Dict, List, Optional, Tuple

from .auth import AuthorizationError, UserSession, get_auth_service


class Route:
    """
    Representation of an individual HTTP endpoint route with regex path matching.

    Agent: @agent: eln-api-agent
    Architectural Role: Matches URI patterns and dispatches execution to handler.
    """

    def __init__(self, method: str, path_pattern: str, handler: Callable) -> None:
        """
        Initialize route definition.

        Agent: @agent: eln-api-agent
        Parameter method (str): HTTP verb (GET, POST, PUT, DELETE, OPTIONS).
        Parameter path_pattern (str): URI template (e.g. '/api/campaigns/{campaign_id}').
        Parameter handler (Callable): Function or coroutine executing business logic.
        """
        self.method = method.upper()
        self.path_pattern = path_pattern
        self.handler = handler

        # Convert /path/{param} to regex named capture group
        regex_str = re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", r"(?P<\1>[^/]+)", path_pattern)
        self.regex = re.compile(f"^{regex_str}$")

    def match(self, method: str, path: str) -> Optional[Dict[str, str]]:
        """
        Match request method and path, returning extracted path parameters if matched.

        Agent: @agent: eln-api-agent
        Parameter method (str): Request HTTP method.
        Parameter path (str): Request URL path.
        Return Type: Optional[Dict[str, str]]
        """
        if self.method != method.upper():
            return None
        m = self.regex.match(path)
        if m:
            return m.groupdict()
        return None


class Router:
    """
    Modular route collection coordinating endpoint registration and invocation.

    Agent: @agent: eln-api-agent
    Architectural Role: Organizes route groups with optional prefixes and mounts them into ASGI applications.
    """

    def __init__(self, prefix: str = "") -> None:
        """
        Initialize router.

        Agent: @agent: eln-api-agent
        Parameter prefix (str): URL path prefix (e.g. '/api/campaigns').
        """
        self.prefix = prefix.rstrip("/")
        self.routes: List[Route] = []

    def add_route(self, method: str, path: str, handler: Callable) -> None:
        """
        Register a new route endpoint.

        Agent: @agent: eln-api-agent
        Parameter method (str): HTTP method.
        Parameter path (str): Relative or absolute endpoint path.
        Parameter handler (Callable): Target handler function.
        """
        full_path = self.prefix + ("/" + path.lstrip("/") if path else "")
        if not full_path:
            full_path = "/"
        self.routes.append(Route(method=method, path_pattern=full_path, handler=handler))

    def get(self, path: str = "") -> Callable:
        """Decorator for HTTP GET endpoint. Agent: @agent: eln-api-agent"""
        def decorator(handler: Callable) -> Callable:
            self.add_route("GET", path, handler)
            return handler
        return decorator

    def post(self, path: str = "") -> Callable:
        """Decorator for HTTP POST endpoint. Agent: @agent: eln-api-agent"""
        def decorator(handler: Callable) -> Callable:
            self.add_route("POST", path, handler)
            return handler
        return decorator

    def put(self, path: str = "") -> Callable:
        """Decorator for HTTP PUT endpoint. Agent: @agent: eln-api-agent"""
        def decorator(handler: Callable) -> Callable:
            self.add_route("PUT", path, handler)
            return handler
        return decorator

    def delete(self, path: str = "") -> Callable:
        """Decorator for HTTP DELETE endpoint. Agent: @agent: eln-api-agent"""
        def decorator(handler: Callable) -> Callable:
            self.add_route("DELETE", path, handler)
            return handler
        return decorator

    def include_router(self, other_router: Router) -> None:
        """
        Mount routes from a sub-router.

        Agent: @agent: eln-api-agent
        Parameter other_router (Router): Sub-router to incorporate.
        """
        for r in other_router.routes:
            combined_path = self.prefix + r.path_pattern
            self.routes.append(Route(method=r.method, path_pattern=combined_path, handler=r.handler))
