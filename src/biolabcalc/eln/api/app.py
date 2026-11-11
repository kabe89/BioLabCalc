"""
Module: biolabcalc.eln.api.app
Component: FastAPI & Standalone ASGI Application Factory
Agent: @agent: eln-api-agent
Architectural Role: ASGI application factory mounting all REST routes (campaigns, timepoints, files,
fplc, nanodrop, gels, inventory, sequences, sops, search), WebSocket real-time connections,
CORS middleware, error handling, and in-process testing harness.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .auth import AuthorizationError, UserSession, get_auth_service
from .router import Router
from .routes import ALL_ROUTERS
from .websocket_manager import get_websocket_manager

logger = logging.getLogger("biolabcalc.eln.api")


class ASGIApplication:
    """
    Standard ASGI 3.0 application supporting REST routing, JSON serializing, and WebSocket messaging.

    Agent: @agent: eln-api-agent
    Architectural Role: Pure-Python ASGI 3.0 compliant dispatcher capable of executing standalone
    or running inside uvicorn, hypercorn, or in-memory TestClient.
    """

    def __init__(
        self,
        title: str = "BioLabCalc ELN & LIMS Pipeline API",
        version: str = "1.0.0",
        static_dir: Optional[str] = None,
    ) -> None:
        """
        Initialize ASGI application.

        Agent: @agent: eln-api-agent
        Parameter title (str): API title.
        Parameter version (str): Semantic version.
        Parameter static_dir (Optional[str]): Optional static directory to serve assets from.
        """
        self.title = title
        self.version = version
        self.static_dir = static_dir
        self.router = Router()
        self.auth_service = get_auth_service()
        self.ws_manager = get_websocket_manager()

        # Mount all route handlers
        for sub_router in ALL_ROUTERS:
            self.router.include_router(sub_router)

        # Healthcheck endpoint
        @self.router.get("/health")
        def health_check(current_user: Optional[UserSession] = None) -> Dict[str, Any]:
            return {
                "status": "healthy",
                "service": self.title,
                "version": self.version,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def __call__(self, scope: Dict[str, Any], receive: Callable, send: Callable) -> None:
        """
        ASGI 3.0 entry point.

        Agent: @agent: eln-api-agent
        Parameter scope (Dict[str, Any]): ASGI connection scope.
        Parameter receive (Callable): Inbound event receiver.
        Parameter send (Callable): Outbound event transmitter.
        """
        scope_type = scope.get("type")
        if scope_type == "http":
            await self._handle_http(scope, receive, send)
        elif scope_type == "websocket":
            await self._handle_websocket(scope, receive, send)
        elif scope_type == "lifespan":
            await self._handle_lifespan(scope, receive, send)
        else:
            raise ValueError(f"Unsupported ASGI scope type: '{scope_type}'")

    def dispatch_sync(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Execute synchronous in-process request dispatch without requiring an active event loop.

        Agent: @agent: eln-api-agent
        Parameter method (str): HTTP method verb.
        Parameter path (str): Target path including optional query string.
        Parameter payload (Optional[Dict[str, Any]]): JSON body dictionary.
        Parameter headers (Optional[Dict[str, str]]): HTTP headers dictionary.
        Return Type: Dict[str, Any]
        """
        parsed = urllib.parse.urlparse(path)
        path_only = parsed.path
        query_params = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
        req_headers = {k.lower(): v for k, v in (headers or {}).items()}

        if method.upper() == "OPTIONS":
            return {"status_code": 204, "json": {}, "body": b""}

        auth_header = req_headers.get("authorization")
        try:
            current_user = self.auth_service.authenticate_token(auth_header)
        except Exception:
            current_user = None

        matched_route: Optional[Tuple[Callable, Dict[str, str]]] = None
        for r in self.router.routes:
            path_params = r.match(method, path_only)
            if path_params is not None:
                matched_route = (r.handler, path_params)
                break

        if not matched_route:
            return {
                "status_code": 404,
                "json": {"status": "error", "message": f"Endpoint '{method} {path_only}' not found."},
                "body": b'{"status": "error"}',
            }

        handler, path_params = matched_route

        sig = inspect.signature(handler)
        kwargs: Dict[str, Any] = {}
        for param_name, param in sig.parameters.items():
            if param_name in path_params:
                kwargs[param_name] = path_params[param_name]
            elif param_name == "payload":
                kwargs["payload"] = payload or {}
            elif param_name == "current_user":
                kwargs["current_user"] = current_user
            elif param_name in query_params:
                kwargs[param_name] = query_params[param_name]
            elif param.default is not inspect.Parameter.empty:
                kwargs[param_name] = param.default

        try:
            if inspect.iscoroutinefunction(handler):
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                if loop and loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        result = pool.submit(lambda: asyncio.run(handler(**kwargs))).result()
                else:
                    result = asyncio.run(handler(**kwargs))
            else:
                result = handler(**kwargs)

            status_code = 200
            if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], int):
                data, status_code = result
            else:
                data = result

            body_bytes = json.dumps(data, default=str).encode("utf-8")
            return {"status_code": status_code, "json": data, "body": body_bytes}

        except AuthorizationError as ae:
            err = {"status": "error", "message": str(ae)}
            return {"status_code": 403, "json": err, "body": json.dumps(err).encode("utf-8")}
        except KeyError as ke:
            err = {"status": "error", "message": str(ke)}
            return {"status_code": 404, "json": err, "body": json.dumps(err).encode("utf-8")}
        except ValueError as ve:
            err = {"status": "error", "message": str(ve)}
            return {"status_code": 400, "json": err, "body": json.dumps(err).encode("utf-8")}
        except Exception as ex:
            err = {"status": "error", "message": f"Internal server error: {ex}"}
            return {"status_code": 500, "json": err, "body": json.dumps(err).encode("utf-8")}
    async def _handle_http(self, scope: Dict[str, Any], receive: Callable, send: Callable) -> None:
        """Dispatch HTTP request. Agent: @agent: eln-api-agent"""
        method = scope.get("method", "GET").upper()
        path = scope.get("path", "/")
        query_string = scope.get("query_string", b"").decode("utf-8")
        full_path = path + ("?" + query_string if query_string else "")

        if method == "OPTIONS":
            await self._send_cors_preflight(send)
            return

        headers_raw = scope.get("headers", [])
        headers = {k.decode("latin1").lower(): v.decode("latin1") for k, v in headers_raw}

        body_bytes = b""
        more_body = True
        while more_body:
            message = await receive()
            body_bytes += message.get("body", b"")
            more_body = message.get("more_body", False)

        payload: Optional[Dict[str, Any]] = None
        if body_bytes:
            content_type = headers.get("content-type", "")
            if "application/json" in content_type or body_bytes.startswith(b"{"):
                try:
                    payload = json.loads(body_bytes.decode("utf-8"))
                except Exception as e:
                    await self._send_json_response(send, 400, {"status": "error", "message": f"Malformed JSON: {e}"})
                    return

        # Check static files (safeguarded against directory traversal)
        if self.static_dir and os.path.isdir(self.static_dir) and method == "GET":
            real_static = os.path.realpath(self.static_dir)
            target = os.path.realpath(os.path.join(self.static_dir, path.lstrip("/")))
            if os.path.commonpath([real_static, target]) == real_static and os.path.isfile(target):
                await self._serve_static(send, target)
                return

        res = self.dispatch_sync(method=method, path=full_path, payload=payload, headers=headers)
        await self._send_json_response(send, res["status_code"], res["json"])

    async def _handle_websocket(self, scope: Dict[str, Any], receive: Callable, send: Callable) -> None:
        """Dispatch WebSocket connection. Agent: @agent: eln-api-agent"""
        path = scope.get("path", "/ws")
        client_id = path.split("/")[-1] if path not in ("/ws", "/ws/") else f"client-{id(scope)}"

        # Accept connection
        await send({"type": "websocket.accept"})
        conn = self.ws_manager.connect(client_id=client_id)

        try:
            while True:
                msg = await receive()
                msg_type = msg.get("type")
                if msg_type == "websocket.disconnect":
                    break
                elif msg_type == "websocket.receive":
                    text = msg.get("text", "")
                    if text:
                        try:
                            data = json.loads(text)
                            action = data.get("action")
                            topic = data.get("topic")
                            if action == "subscribe" and topic:
                                self.ws_manager.subscribe(client_id, topic)
                                await send(
                                    {
                                        "type": "websocket.send",
                                        "text": json.dumps({"event": "SUBSCRIBED", "topic": topic}),
                                    }
                                )
                            elif action == "unsubscribe" and topic:
                                self.ws_manager.unsubscribe(client_id, topic)
                            elif action == "ping":
                                await send({"type": "websocket.send", "text": json.dumps({"event": "PONG"})})
                        except Exception as e:
                            logger.warning(f"Error handling WebSocket message: {e}")
        finally:
            self.ws_manager.disconnect(client_id)

    async def _handle_lifespan(self, scope: Dict[str, Any], receive: Callable, send: Callable) -> None:
        """ASGI lifespan startup/shutdown. Agent: @agent: eln-api-agent"""
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                break

    async def _send_cors_preflight(self, send: Callable) -> None:
        """Send 204 response with CORS headers. Agent: @agent: eln-api-agent"""
        headers = [
            (b"access-control-allow-origin", b"*"),
            (b"access-control-allow-methods", b"GET, POST, PUT, DELETE, OPTIONS"),
            (b"access-control-allow-headers", b"Content-Type, Authorization, X-Requested-With"),
            (b"access-control-max-age", b"86400"),
        ]
        await send({"type": "http.response.start", "status": 204, "headers": headers})
        await send({"type": "http.response.body", "body": b""})

    async def _send_json_response(self, send: Callable, status_code: int, data: Any) -> None:
        """Send JSON response with CORS headers. Agent: @agent: eln-api-agent"""
        body_bytes = json.dumps(data, default=str).encode("utf-8")
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body_bytes)).encode("ascii")),
            (b"access-control-allow-origin", b"*"),
        ]
        await send({"type": "http.response.start", "status": status_code, "headers": headers})
        await send({"type": "http.response.body", "body": body_bytes})

    async def _serve_static(self, send: Callable, filepath: str) -> None:
        """Serve static file bytes. Agent: @agent: eln-api-agent"""
        with open(filepath, "rb") as f:
            content = f.read()
        headers = [
            (b"content-type", b"text/plain"),
            (b"content-length", str(len(content)).encode("ascii")),
            (b"access-control-allow-origin", b"*"),
        ]
        await send({"type": "http.response.start", "status": 200, "headers": headers})
        await send({"type": "http.response.body", "body": content})


class TestClient:
    """
    Synchronous and asynchronous in-process test client for ASGI application.

    Agent: @agent: eln-api-agent
    Architectural Role: Executes HTTP requests directly against ASGI application without opening network ports.
    """

    def __init__(self, app: ASGIApplication) -> None:
        """
        Initialize TestClient with ASGI application.

        Agent: @agent: eln-api-agent
        Parameter app (ASGIApplication): Application instance.
        """
        self.app = app

    async def async_request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Execute an asynchronous request through the ASGI pipeline.

        Agent: @agent: eln-api-agent
        Parameter method (str): HTTP method.
        Parameter path (str): Target path.
        Parameter payload (Optional[Dict[str, Any]]): JSON body.
        Parameter headers (Optional[Dict[str, str]]): HTTP headers.
        Return Type: Dict[str, Any]
        """
        print(f"[DEBUG] Inside async_request for {method} {path}", flush=True)
        req_headers = headers or {}
        body_bytes = json.dumps(payload).encode("utf-8") if payload is not None else b""
        if payload is not None and "content-type" not in [k.lower() for k in req_headers]:
            req_headers["content-type"] = "application/json"

        scope_headers = [(k.lower().encode("latin1"), v.encode("latin1")) for k, v in req_headers.items()]

        # Split path and query
        parsed = urllib.parse.urlparse(path)
        scope = {
            "type": "http",
            "method": method.upper(),
            "path": parsed.path,
            "query_string": parsed.query.encode("utf-8"),
            "headers": scope_headers,
        }

        response_status = 200
        response_body = b""

        async def receive() -> Dict[str, Any]:
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        async def send(message: Dict[str, Any]) -> None:
            nonlocal response_status, response_body
            if message["type"] == "http.response.start":
                response_status = message["status"]
            elif message["type"] == "http.response.body":
                response_body += message.get("body", b"")

        await self.app(scope, receive, send)

        parsed_json: Optional[Dict[str, Any]] = None
        if response_body:
            try:
                parsed_json = json.loads(response_body.decode("utf-8"))
            except Exception:
                parsed_json = None

        return {
            "status_code": response_status,
            "json": parsed_json,
            "body": response_body,
        }

    def request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Synchronous request wrapper.

        Agent: @agent: eln-api-agent
        Parameter method (str): HTTP method.
        Parameter path (str): Path.
        Parameter payload (Optional[Dict[str, Any]]): JSON body.
        Parameter headers (Optional[Dict[str, str]]): HTTP headers.
        Return Type: Dict[str, Any]
        """
        effective_headers = dict(headers) if headers is not None else {"Authorization": "Bearer token-active-researcher"}
        return self.app.dispatch_sync(method, path, payload, effective_headers)

    def get(self, path: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """GET shortcut. Agent: @agent: eln-api-agent"""
        return self.request("GET", path, headers=headers)

    def post(self, path: str, payload: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """POST shortcut. Agent: @agent: eln-api-agent"""
        return self.request("POST", path, payload=payload, headers=headers)

    def put(self, path: str, payload: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """PUT shortcut. Agent: @agent: eln-api-agent"""
        return self.request("PUT", path, payload=payload, headers=headers)

    def delete(self, path: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """DELETE shortcut. Agent: @agent: eln-api-agent"""
        return self.request("DELETE", path, headers=headers)


def create_app(
    title: str = "BioLabCalc ELN & LIMS Pipeline",
    version: str = "1.0.0",
    static_dir: Optional[str] = None,
) -> ASGIApplication:
    """
    Factory function creating and configuring the ELN & LIMS ASGI application.

    Agent: @agent: eln-api-agent
    Parameter title (str): Application title.
    Parameter version (str): Application version.
    Parameter static_dir (Optional[str]): Path to static assets.
    Return Type: ASGIApplication
    """
    return ASGIApplication(title=title, version=version, static_dir=static_dir)
