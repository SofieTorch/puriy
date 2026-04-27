"""Re-export of geodata.edge_overlap for backward compatibility."""

from geodata.edge_overlap import (
    DEFAULT_MIN_TRIPS,
    count_device_trips_for_line,
    find_lines_near_device_trips,
    find_overlapping_edges,
    find_unvoted_overlapping_edges,
    get_active_route,
    get_device_trips_for_line,
)

__all__ = [
    "DEFAULT_MIN_TRIPS",
    "count_device_trips_for_line",
    "find_lines_near_device_trips",
    "find_overlapping_edges",
    "find_unvoted_overlapping_edges",
    "get_active_route",
    "get_device_trips_for_line",
]
