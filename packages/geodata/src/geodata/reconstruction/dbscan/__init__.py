"""DBSCAN-based route reconstruction.

Pools all trip vertices, clusters them with DBSCAN, selects the largest
cluster as the main road, and orders the points via PCA + greedy
nearest-neighbour to form the route centerline.
"""

from .cluster import ClusterSegment, FilteredRouteResult, filter_cluster_route
from ..base import ApproachInfo, ParamSpec, register

__all__ = [
    "ClusterSegment",
    "FilteredRouteResult",
    "filter_cluster_route",
]

_INFO = ApproachInfo(
    key="dbscan",
    label="DBSCAN Clustering",
    description=(
        "Pools all trip vertices, clusters with DBSCAN, selects the "
        "largest cluster as the main road, orders via PCA + greedy NN."
    ),
    params=(
        ParamSpec(
            "eps_meters", "Epsilon (m)", default=30.0,
            min_val=5, max_val=200, step=5,
        ),
        ParamSpec(
            "min_samples", "Min samples (0=auto)", default=0,
            min_val=0, max_val=50, step=1, none_value=0,
        ),
        ParamSpec(
            "min_cluster_segments", "Min cluster segs", default=0,
            min_val=0, max_val=200, step=1,
        ),
        ParamSpec(
            "thin_meters", "Thin spacing (m, 0=auto)", default=0,
            min_val=0, max_val=200, step=5, none_value=0,
        ),
    ),
)

register(_INFO, filter_cluster_route)
