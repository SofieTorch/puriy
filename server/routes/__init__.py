from .detours import router as detours_router
from .devices import router as devices_router
from .directions import router as directions_router
from .fares import router as fares_router
from .lines import router as lines_router
from .ramal_descriptors import router as ramal_descriptors_router
from .recordings import router as recordings_router
from .voting import router as voting_router

__all__ = [
    "detours_router",
    "devices_router",
    "directions_router",
    "fares_router",
    "lines_router",
    "ramal_descriptors_router",
    "recordings_router",
    "voting_router",
]
