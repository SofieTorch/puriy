"""Route reconstruction based on Arman & Tampère (2021).

Implements a three-step algorithm adapted from:

    M.A. Arman, C.M.J. Tampère, "Lane-level routable digital map
    reconstruction for motorway networks using low-precision GPS data",
    Transportation Research Part C, 129, 103234, 2021.
    https://doi.org/10.1016/j.trc.2021.103234

The original paper targets lane-level motorway reconstruction.  This
adaptation focuses on extracting transit route centerlines from GPS
traces in an urban network without official route maps.

Pipeline overview
-----------------
1. **Network segmentation** (``segment.py``)
   - Bundle trajectories using QuickBundles-like clustering.
   - Identify nodes where bundles merge or diverge.
   - Cut the network into homogeneous, unidirectional segments.

2. **Centerline construction** (``centerline.py``)
   - Compute pairwise Fréchet distance between trajectories in each segment.
   - Select the most dissimilar (outermost) trajectory pairs.
   - Compute midpoints at regular intervals → initial centerline.
   - Smooth the centerline iteratively.

3. **Route estimation** (``estimate.py``)
   - Combine segments into a full route estimation.
   - Persist as RouteEstimation + RouteSegments (same DB schema
     used by the DBSCAN approach).
"""

from .estimate import ArmanTampereResult, reconstruct_route
from ..base import ApproachInfo, ParamSpec, register

__all__ = [
    "ArmanTampereResult",
    "reconstruct_route",
]

_INFO = ApproachInfo(
    key="arman_tampere",
    label="Frechet Centerline (Arman & Tampere)",
    description=(
        "Segments the trajectory network, builds centerlines via "
        "Frechet distance and lateral midpoints, then smooths."
    ),
    params=(
        ParamSpec(
            "distance_threshold", "Bundle distance (m)", default=50.0,
            min_val=10, max_val=200, step=10,
        ),
        ParamSpec(
            "f_q", "Diverge fraction (f_q)", default=0.035,
            min_val=0.001, max_val=0.2, step=0.005,
        ),
        ParamSpec(
            "f_q_prime", "Merge fraction (f_q')", default=0.027,
            min_val=0.001, max_val=0.2, step=0.005,
        ),
        ParamSpec(
            "z_threshold", "Outlier z-threshold", default=1.96,
            min_val=0.5, max_val=4.0, step=0.1,
        ),
        ParamSpec(
            "s_prime", "Min dissimilarity (S')", default=0.60,
            min_val=0.1, max_val=1.0, step=0.05,
        ),
        ParamSpec(
            "dx_meters", "Sample interval (m)", default=10.0,
            min_val=1, max_val=100, step=1,
        ),
    ),
)

register(_INFO, reconstruct_route)
