"""Pipeline step registry."""

from .deduplicate_lines import execute as deduplicate_lines
from .clean_traces import execute as clean_traces
from .reconstruct_routes import execute as reconstruct_routes
from .resolve_edge_votes import execute as resolve_edge_votes
from .resolve_line_votes import execute as resolve_line_votes
from .resolve_routes import execute as resolve_routes
from .resolve_fares import execute as resolve_fares
from .rebuild_graph import execute as rebuild_graph
from .cleanup import execute as cleanup
from .infer_schedules import execute as infer_schedules

STEPS: dict[str, dict] = {
    "cleanup": {
        "fn": cleanup,
        "label": "Cleanup",
        "description": "Mark stale sessions as abandoned, expire old detours",
    },
    "deduplicate_lines": {
        "fn": deduplicate_lines,
        "label": "Deduplicate lines",
        "description": "Auto-merge duplicate PENDING lines by name similarity and spatial overlap",
    },
    "clean_traces": {
        "fn": clean_traces,
        "label": "Clean traces",
        "description": "Map-match raw GPS recordings to road network via Valhalla",
    },
    "reconstruct_routes": {
        "fn": reconstruct_routes,
        "label": "Reconstruct routes",
        "description": "Build consensus routes from cleaned trips using reconstruction strategies",
    },
    "resolve_edge_votes": {
        "fn": resolve_edge_votes,
        "label": "Resolve edge votes",
        "description": "Accept or reject route edges based on community votes",
    },
    "resolve_routes": {
        "fn": resolve_routes,
        "label": "Resolve routes",
        "description": "Promote PENDING routes to CONFIRMED once a quorum of edges are confirmed",
    },
    "resolve_line_votes": {
        "fn": resolve_line_votes,
        "label": "Resolve line votes",
        "description": "Approve or reject transit lines based on community votes",
    },
    "resolve_fares": {
        "fn": resolve_fares,
        "label": "Resolve fares",
        "description": "Assign crowdsourced fare reports to fare zones (municipalities)",
    },
    "rebuild_graph": {
        "fn": rebuild_graph,
        "label": "Rebuild graph",
        "description": "Rebuild the transit directions graph from confirmed routes",
    },
    "infer_schedules": {
        "fn": infer_schedules,
        "label": "Infer schedules",
        "description": "Infer service hours and headway per line, bucketed by day type",
    },
}
