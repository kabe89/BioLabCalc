"""
Module: biolabcalc.eln.api.routes
Component: Route Registry Aggregator
Architectural Role: Central export aggregator mounting all sub-routers for campaigns, timepoints,
files (CAS/OCR), FPLC, NanoDrop, gels, inventory, sequences, SOPs, and unified search.
"""

from .campaigns import router as campaigns_router
from .files import router as files_router
from .fplc import router as fplc_router
from .gels import router as gels_router
from .inventory import router as inventory_router
from .nanodrop import router as nanodrop_router
from .search import router as search_router
from .sequences import router as sequences_router
from .sops import router as sops_router
from .timepoints import router as timepoints_router

ALL_ROUTERS = [
    campaigns_router,
    timepoints_router,
    files_router,
    fplc_router,
    nanodrop_router,
    gels_router,
    inventory_router,
    sequences_router,
    sops_router,
    search_router,
]

# Dynamically mount custom experiments and approvals routers when available
try:
    from .custom_experiments import router as custom_experiments_router
    ALL_ROUTERS.append(custom_experiments_router)
except ImportError:
    custom_experiments_router = None

try:
    from .approvals import router as approvals_router
    ALL_ROUTERS.append(approvals_router)
except ImportError:
    approvals_router = None


__all__ = [
    "ALL_ROUTERS",
    "campaigns_router",
    "timepoints_router",
    "files_router",
    "fplc_router",
    "nanodrop_router",
    "gels_router",
    "inventory_router",
    "sequences_router",
    "sops_router",
    "search_router",
]
