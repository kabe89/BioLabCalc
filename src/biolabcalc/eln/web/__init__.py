"""
Package: biolabcalc.eln.web
Component: Frontend Web Application & Scientific Canvases Package
Agent: @agent: eln-frontend-agent
Architectural Role: Web package root for templates, static assets, and UI components.
"""

import os

def get_web_dir() -> str:
    """Return absolute path to web directory containing templates and static assets."""
    return os.path.dirname(os.path.abspath(__file__))

__all__ = ["get_web_dir"]
