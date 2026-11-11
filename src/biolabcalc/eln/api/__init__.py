"""
Module: biolabcalc.eln.api
Component: API & Real-Time Concurrency Package for Electronic Lab Notebook & LIMS Pipeline
Architectural Role: Central export module providing the ASGI application factory `create_app`,
the in-process `TestClient`, role-based access control authentication, and real-time WebSocket connection manager.
"""

from .app import ASGIApplication, TestClient, create_app
from .auth import (
    ROLE_ACTIVE_RESEARCHER,
    ROLE_ALUMNI_READONLY,
    ROLE_PI_ADMIN,
    ROLE_ROTATION_STUDENT,
    AuthService,
    AuthorizationError,
    UserSession,
    get_auth_service,
)
from .websocket_manager import WebSocketConnection, WebSocketManager, get_websocket_manager

__all__ = [
    "create_app",
    "ASGIApplication",
    "TestClient",
    "AuthService",
    "UserSession",
    "AuthorizationError",
    "get_auth_service",
    "WebSocketManager",
    "WebSocketConnection",
    "get_websocket_manager",
    "ROLE_PI_ADMIN",
    "ROLE_ACTIVE_RESEARCHER",
    "ROLE_ROTATION_STUDENT",
    "ROLE_ALUMNI_READONLY",
]
