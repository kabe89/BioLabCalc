"""
Module: biolabcalc.eln
Component: State-of-the-Art Electronic Lab Notebook (ELN) & Multi-Modal LIMS Package
Architectural Role: Core package initialization for ELN and LIMS suite.
"""

from . import config, parsers, storage

__version__ = "1.0.0"

__all__ = [
    "__version__",
    "config",
    "storage",
    "parsers",
]

try:
    from . import rag
    __all__.append("rag")
except ImportError:
    pass
