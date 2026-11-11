"""
Module: biolabcalc.eln
Component: State-of-the-Art Electronic Lab Notebook (ELN) & Multi-Modal LIMS Package
Agent: @agent: eln-orchestrator
Architectural Role: Core package initialization for ELN and LIMS suite.
"""

from . import parsers, storage

__version__ = "1.0.0"

__all__ = [
    "__version__",
    "storage",
    "parsers",
]

try:
    from . import rag
    __all__.append("rag")
except ImportError:
    pass
