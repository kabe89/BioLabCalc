"""
Module: biolabcalc.eln.server
Component: State-of-the-Art Electronic Lab Notebook (ELN) & Multi-Modal LIMS Server
Architectural Role: Server launcher and runtime coordinator. Provides dual-engine execution:
uses Uvicorn / FastAPI ASGI when available, with an automatic pure-Python multi-threaded
HTTP/REST server fallback for zero-dependency bench environments.
"""

from __future__ import annotations
import os
import sys
import json
import logging
import threading
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Optional, Dict, Any

logger = logging.getLogger("biolabcalc.eln.server")


def get_default_storage_dir() -> str:
    """Return default root directory for ELN data, database, and CAS blobs."""
    env_dir = os.environ.get("BIOLABCALC_STORAGE_DIR")
    if env_dir:
        os.makedirs(env_dir, exist_ok=True)
        return env_dir
    # Try local workspace directory first to ensure sandbox compatibility
    local_dir = os.path.join(os.getcwd(), ".biolabcalc_data")
    try:
        os.makedirs(local_dir, exist_ok=True)
        return local_dir
    except Exception:
        # Fallback to home or tempdir
        try:
            home = os.path.expanduser("~")
            base_dir = os.path.join(home, ".biolabcalc_eln")
            os.makedirs(base_dir, exist_ok=True)
            return base_dir
        except Exception:
            import tempfile
            tmp_dir = os.path.join(tempfile.gettempdir(), ".biolabcalc_eln")
            os.makedirs(tmp_dir, exist_ok=True)
            return tmp_dir


def launch_eln_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    db_url: Optional[str] = None,
    open_browser: bool = True,
    blocking: bool = True,
) -> str:
    """
    Launch the State-of-the-Art ELN & LIMS application server.

    Args:
        host: Host IP or hostname (default: '127.0.0.1').
        port: Listening TCP port (default: 8080).
        db_url: Database connection string (defaults to local SQLite database in ~/.biolabcalc_eln).
        open_browser: Whether to automatically launch the default web browser.
        blocking: If True, blocks the calling thread until interrupted; if False, runs in daemon thread.

    Returns:
        The accessible server URL (e.g. 'http://127.0.0.1:8080').
    """
    storage_dir = get_default_storage_dir()
    db_path = os.path.join(storage_dir, "eln_lims.db")
    effective_db_url = db_url or f"sqlite:///{db_path}"

    print("=" * 80)
    print("  BIOLABCALC STATE-OF-THE-ART ELECTRONIC LAB NOTEBOOK (ELN) & MULTI-MODAL LIMS")
    print("=" * 80)
    print(f"[*] Engine:           Multi-Modal Hybrid Architecture")
    print(f"[*] Database:         {effective_db_url}")
    print(f"[*] CAS Blob Storage: {os.path.join(storage_dir, 'blobs')}")
    print(f"[*] Host Address:     http://{host}:{port}")
    print("=" * 80)

    # Initialize database schema
    try:
        from .schema.database import init_db, get_engine
        engine = get_engine(effective_db_url)
        init_db(engine)
        print("[+] Database schema verified.")
    except Exception as e:
        logger.warning(f"Database initialization notice: {e}")

    server_url = f"http://{host}:{port}"

    # Check if uvicorn & FastAPI app are available
    try:
        import uvicorn
        from .api.app import create_app
        from .web import get_web_dir
        web_dir = get_web_dir()
        static_dir = os.path.join(web_dir, "static")
        app = create_app(static_dir=static_dir)

        def run_uvicorn():
            uvicorn.run(app, host=host, port=port, log_level="info")

        if blocking:
            if open_browser:
                threading.Timer(1.0, lambda: webbrowser.open(server_url)).start()
            print(f"[+] Launching Uvicorn ASGI server on {server_url} (Press Ctrl+C to stop)...")
            run_uvicorn()
        else:
            t = threading.Thread(target=run_uvicorn, daemon=True)
            t.start()
            if open_browser:
                threading.Timer(1.0, lambda: webbrowser.open(server_url)).start()

        return server_url
    except ImportError:
        # Pure-Python Fallback Server using http.server and embedded API dispatcher
        return _launch_fallback_server(
            host=host,
            port=port,
            storage_dir=storage_dir,
            open_browser=open_browser,
            blocking=blocking,
        )


def _launch_fallback_server(
    host: str,
    port: int,
    storage_dir: str,
    open_browser: bool,
    blocking: bool,
) -> str:
    """Fallback standard library HTTP server when Uvicorn is not installed."""
    from .web import get_web_dir
    from .api.app import create_app

    web_root = get_web_dir()
    templates_dir = os.path.join(web_root, "templates")
    static_dir = os.path.join(web_root, "static")
    asgi_app = create_app(static_dir=static_dir)

    class ELNRequestHandler(SimpleHTTPRequestHandler):
        def _handle_api(self, method: str):
            headers = {k: v for k, v in self.headers.items()}
            payload = None
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                body_bytes = self.rfile.read(content_length)
                try:
                    payload = json.loads(body_bytes.decode("utf-8"))
                except Exception:
                    payload = {}
            res = asgi_app.dispatch_sync(method, self.path, payload=payload, headers=headers)
            self.send_response(res.get("status_code", 200))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.end_headers()
            self.wfile.write(res.get("body", b"{}"))

        def do_OPTIONS(self):
            if self.path.startswith("/api/"):
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
                self.end_headers()
            else:
                self.send_response(204)
                self.end_headers()

        def do_GET(self):
            parsed_path = self.path.split("?")[0]
            if parsed_path in ("/", "/index.html"):
                index_path = os.path.join(templates_dir, "index.html")
                if os.path.exists(index_path):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    with open(index_path, "rb") as f:
                        self.wfile.write(f.read())
                    return
            elif parsed_path.startswith("/static/"):
                rel_path = parsed_path[len("/static/"):].lstrip("/")
                real_static = os.path.realpath(static_dir)
                target = os.path.realpath(os.path.join(static_dir, rel_path))
                if os.path.commonpath([real_static, target]) == real_static and os.path.isfile(target):
                    self.send_response(200)
                    if target.endswith(".css"):
                        self.send_header("Content-Type", "text/css; charset=utf-8")
                    elif target.endswith(".js"):
                        self.send_header("Content-Type", "application/javascript; charset=utf-8")
                    elif target.endswith(".svg"):
                        self.send_header("Content-Type", "image/svg+xml")
                    self.end_headers()
                    with open(target, "rb") as f:
                        self.wfile.write(f.read())
                    return
            elif parsed_path.startswith("/api/"):
                self._handle_api("GET")
                return

            super().do_GET()

        def do_POST(self):
            if self.path.startswith("/api/"):
                self._handle_api("POST")
                return
            self.send_response(404)
            self.end_headers()

        def do_PUT(self):
            if self.path.startswith("/api/"):
                self._handle_api("PUT")
                return
            self.send_response(404)
            self.end_headers()

        def do_DELETE(self):
            if self.path.startswith("/api/"):
                self._handle_api("DELETE")
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format, *args):
            pass

    server = HTTPServer((host, port), ELNRequestHandler)
    actual_port = server.server_address[1]
    server_url = f"http://{host}:{actual_port}"
    print(f"[+] Fallback pure-Python server running at {server_url} (Press Ctrl+C to stop)")

    if blocking:
        if open_browser:
            threading.Timer(1.0, lambda: webbrowser.open(server_url)).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.server_close()
    else:
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        if open_browser:
            threading.Timer(1.0, lambda: webbrowser.open(server_url)).start()

    return server_url
