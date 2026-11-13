"""
Package: biolabcalc.eln.web
Component: Frontend Web Application & Scientific Canvases Package
Architectural Role: Web package root for templates, static assets, and UI components.
"""

import os
import sys
from pathlib import Path


def get_web_dir() -> str:
    """
    Return absolute path to web directory containing templates and static assets.
    
    Resolves correctly both when running directly from a source checkout
    (e.g., `src/biolabcalc/eln/web`) and when installed as a package in `site-packages`.
    """
    # 1. Primary resolution: directory containing this __file__
    current_dir = os.path.dirname(os.path.abspath(__file__))
    templates_index = os.path.join(current_dir, "templates", "index.html")
    static_css = os.path.join(current_dir, "static", "styles.css")
    if os.path.exists(templates_index) and os.path.exists(static_css):
        return current_dir

    # 2. Modern importlib.resources resolution (Python 3.9+)
    try:
        from importlib.resources import files
        res_dir = str(files("biolabcalc.eln.web"))
        if os.path.exists(os.path.join(res_dir, "templates", "index.html")):
            return res_dir
    except Exception:
        pass

    # 3. Fallback resolution: inspect loaded module or repository root if running from source
    try:
        if "biolabcalc" in sys.modules and hasattr(sys.modules["biolabcalc"], "__file__"):
            pkg_root = os.path.dirname(os.path.abspath(sys.modules["biolabcalc"].__file__))
            candidate = os.path.join(pkg_root, "eln", "web")
            if os.path.exists(os.path.join(candidate, "templates", "index.html")):
                return candidate
    except Exception:
        pass

    # Default to current_dir
    return current_dir


def get_templates_dir() -> str:
    """Return absolute path to HTML templates directory."""
    return os.path.join(get_web_dir(), "templates")


def get_static_dir() -> str:
    """Return absolute path to static assets directory."""
    return os.path.join(get_web_dir(), "static")


def get_template_path(filename: str = "index.html") -> str:
    """Return absolute path to a specific template file, verifying existence."""
    path = os.path.join(get_templates_dir(), filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Template '{filename}' not found at {path}")
    return os.path.abspath(path)


def get_static_path(filename: str = "styles.css") -> str:
    """Return absolute path to a specific static asset file, verifying existence."""
    path = os.path.join(get_static_dir(), filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Static asset '{filename}' not found at {path}")
    return os.path.abspath(path)


__all__ = [
    "get_web_dir",
    "get_templates_dir",
    "get_static_dir",
    "get_template_path",
    "get_static_path",
]
