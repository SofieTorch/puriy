"""Route reconstruction approaches.

Each subpackage implements a different strategy for reconstructing
transit route geometry from cleaned GPS traces.

Use :func:`get_approaches` to discover registered approaches and
:func:`get_approach` to look one up by key.
"""

from .base import (  # noqa: F401
    ApproachInfo,
    ParamSpec,
    ReconstructFn,
    ReconstructionResult,
    get_approach,
    get_approaches,
    register,
    resolve_params,
)

# Import subpackages so they self-register at import time.
from . import arman_tampere as arman_tampere  # noqa: F401
from . import dbscan as dbscan  # noqa: F401

__all__ = [
    "ApproachInfo",
    "ParamSpec",
    "ReconstructFn",
    "ReconstructionResult",
    "get_approach",
    "get_approaches",
    "register",
    "resolve_params",
]
