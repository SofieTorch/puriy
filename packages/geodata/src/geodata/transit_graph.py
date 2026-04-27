"""Transit graph builder and A* pathfinder for Cochabamba's bus network."""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from uuid import UUID

from geoalchemy2.shape import to_shape
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from database.models import (
    RouteStatus,
    Line,
    LineStatus,
    Route,
)

from .geo_math import haversine_m

# ---------------------------------------------------------------------------
# Speed constants (metres per second)
# ---------------------------------------------------------------------------

BUS_SPEED_MPS = 4.17  # ~15 km/h
WALK_SPEED_MPS = 1.39  # ~5 km/h

# Graph construction parameters
NODE_DEDUP_M = 20.0  # merge endpoints closer than this
TRANSFER_RADIUS_M = 400.0  # max walking transfer distance


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class GraphNode:
    """A node in the transit graph."""

    id: int
    lon: float
    lat: float
    lines: set[tuple[UUID, str]] = field(default_factory=set)  # (line_id, line_name)


@dataclass
class GraphEdge:
    """An edge in the transit graph."""

    from_node: int
    to_node: int
    weight: float  # seconds
    mode: str  # "bus" or "walk"
    line_id: UUID | None = None
    line_name: str | None = None
    line_approved: bool = True
    route_confirmed: bool = True
    geometry: list[list[float]] = field(default_factory=list)  # [[lon, lat], ...]


@dataclass
class TransitGraph:
    """Weighted graph representing the bus network."""

    nodes: dict[int, GraphNode] = field(default_factory=dict)
    adjacency: dict[int, list[GraphEdge]] = field(default_factory=dict)
    _next_id: int = 0

    def add_node(self, lon: float, lat: float) -> int:
        nid = self._next_id
        self._next_id += 1
        self.nodes[nid] = GraphNode(id=nid, lon=lon, lat=lat)
        self.adjacency[nid] = []
        return nid

    def add_edge(self, edge: GraphEdge) -> None:
        self.adjacency[edge.from_node].append(edge)

    def find_nearest(self, lon: float, lat: float, radius_m: float) -> list[int]:
        """Return node ids within *radius_m* of (lon, lat)."""
        result = []
        for node in self.nodes.values():
            if haversine_m(lon, lat, node.lon, node.lat) <= radius_m:
                result.append(node.id)
        return result


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def _find_or_create_node(
    graph: TransitGraph,
    lon: float,
    lat: float,
    coord_to_node: dict[tuple[float, float], int],
) -> int:
    """Find an existing node within NODE_DEDUP_M or create a new one."""
    for (ex_lon, ex_lat), nid in coord_to_node.items():
        if haversine_m(lon, lat, ex_lon, ex_lat) <= NODE_DEDUP_M:
            return nid
    nid = graph.add_node(lon, lat)
    coord_to_node[(lon, lat)] = nid
    return nid


def build_transit_graph(db: Session) -> TransitGraph:
    """Build a transit graph from all non-superseded routes.

    Includes both approved and pending lines/routes. Each edge is tagged
    with `line_approved` and `route_confirmed` so the pathfinder can
    filter at search time based on user preferences.

    If the ``ROUTE_STRATEGY_FILTER`` environment variable is set, only
    routes whose ``strategy_key`` matches the value are included.
    """
    import os

    strategy_filter = os.environ.get("ROUTE_STRATEGY_FILTER")

    graph = TransitGraph()
    coord_to_node: dict[tuple[float, float], int] = {}

    stmt = (
        select(Line)
        .where(Line.status.in_([LineStatus.APPROVED, LineStatus.PENDING]))
        .options(
            selectinload(Line.routes).selectinload(
                Route.edges
            )
        )
    )
    lines = db.execute(stmt).scalars().all()

    for line in lines:
        is_approved = line.status == LineStatus.APPROVED
        for route in line.routes:
            if route.status == RouteStatus.SUPERSEDED:
                continue
            if strategy_filter and route.strategy_key != strategy_filter:
                continue
            is_confirmed = route.status == RouteStatus.CONFIRMED

            segments = sorted(route.edges, key=lambda s: s.sequence)

            prev_node_id: int | None = None
            for segment in segments:
                if segment.path is None:
                    continue

                shape = to_shape(segment.path)
                coords = list(shape.coords)
                if len(coords) < 2:
                    continue

                start_lon, start_lat = coords[0][0], coords[0][1]
                end_lon, end_lat = coords[-1][0], coords[-1][1]

                start_node = _find_or_create_node(
                    graph, start_lon, start_lat, coord_to_node
                )
                end_node = _find_or_create_node(
                    graph, end_lon, end_lat, coord_to_node
                )

                graph.nodes[start_node].lines.add((line.id, line.name))
                graph.nodes[end_node].lines.add((line.id, line.name))

                distance_m = 0.0
                for i in range(len(coords) - 1):
                    distance_m += haversine_m(
                        coords[i][0], coords[i][1],
                        coords[i + 1][0], coords[i + 1][1],
                    )

                geometry = [[c[0], c[1]] for c in coords]
                weight = distance_m / BUS_SPEED_MPS

                graph.add_edge(
                    GraphEdge(
                        from_node=start_node,
                        to_node=end_node,
                        weight=weight,
                        mode="bus",
                        line_id=line.id,
                        line_name=line.name,
                        line_approved=is_approved,
                        route_confirmed=is_confirmed,
                        geometry=geometry,
                    )
                )

                # Bridge gap when node dedup pulled consecutive segment endpoints apart
                if prev_node_id is not None and prev_node_id != start_node:
                    gap_m = haversine_m(
                        graph.nodes[prev_node_id].lon,
                        graph.nodes[prev_node_id].lat,
                        graph.nodes[start_node].lon,
                        graph.nodes[start_node].lat,
                    )
                    graph.add_edge(
                        GraphEdge(
                            from_node=prev_node_id,
                            to_node=start_node,
                            weight=gap_m / BUS_SPEED_MPS,
                            mode="bus",
                            line_id=line.id,
                            line_name=line.name,
                            line_approved=is_approved,
                            route_confirmed=is_confirmed,
                            geometry=[
                                [
                                    graph.nodes[prev_node_id].lon,
                                    graph.nodes[prev_node_id].lat,
                                ],
                                [
                                    graph.nodes[start_node].lon,
                                    graph.nodes[start_node].lat,
                                ],
                            ],
                        )
                    )

                prev_node_id = end_node

    node_list = list(graph.nodes.values())
    node_line_ids = {
        n.id: frozenset(lid for lid, _ in n.lines) for n in node_list
    }
    for i, a in enumerate(node_list):
        a_lids = node_line_ids[a.id]
        if not a_lids:
            continue
        for b in node_list[i + 1 :]:
            b_lids = node_line_ids[b.id]
            if not b_lids or not a_lids.isdisjoint(b_lids):
                continue
            dist = haversine_m(a.lon, a.lat, b.lon, b.lat)
            if dist <= TRANSFER_RADIUS_M:
                weight = dist / WALK_SPEED_MPS
                walk_geom = [[a.lon, a.lat], [b.lon, b.lat]]
                graph.add_edge(
                    GraphEdge(
                        from_node=a.id,
                        to_node=b.id,
                        weight=weight,
                        mode="walk",
                        geometry=walk_geom,
                    )
                )
                graph.add_edge(
                    GraphEdge(
                        from_node=b.id,
                        to_node=a.id,
                        weight=weight,
                        mode="walk",
                        geometry=list(reversed(walk_geom)),
                    )
                )

    return graph


# ---------------------------------------------------------------------------
# A* pathfinder
# ---------------------------------------------------------------------------


def find_route(
    graph: TransitGraph,
    origin: tuple[float, float],  # (lon, lat)
    destination: tuple[float, float],  # (lon, lat)
    max_walk_m: float = 800.0,
    include_pending_lines: bool = False,
    include_pending_routes: bool = False,
) -> list[dict] | None:
    """Find a multi-modal route from *origin* to *destination*.

    Parameters
    ----------
    include_pending_lines:
        If False, skip bus edges from unapproved lines.
    include_pending_routes:
        If False, skip bus edges from unconfirmed routes.

    Returns a list of leg dicts or None if no route is found.
    """
    origin_id = graph.add_node(origin[0], origin[1])
    dest_id = graph.add_node(destination[0], destination[1])

    for nid in graph.find_nearest(origin[0], origin[1], max_walk_m):
        if nid == origin_id:
            continue
        node = graph.nodes[nid]
        dist = haversine_m(origin[0], origin[1], node.lon, node.lat)
        graph.add_edge(
            GraphEdge(
                from_node=origin_id,
                to_node=nid,
                weight=dist / WALK_SPEED_MPS,
                mode="walk",
                geometry=[[origin[0], origin[1]], [node.lon, node.lat]],
            )
        )

    for nid in graph.find_nearest(destination[0], destination[1], max_walk_m):
        if nid == dest_id:
            continue
        node = graph.nodes[nid]
        dist = haversine_m(node.lon, node.lat, destination[0], destination[1])
        graph.add_edge(
            GraphEdge(
                from_node=nid,
                to_node=dest_id,
                weight=dist / WALK_SPEED_MPS,
                mode="walk",
                geometry=[[node.lon, node.lat], [destination[0], destination[1]]],
            )
        )

    dest_lon, dest_lat = destination

    def heuristic(nid: int) -> float:
        n = graph.nodes[nid]
        return haversine_m(n.lon, n.lat, dest_lon, dest_lat) / BUS_SPEED_MPS

    counter = 0
    open_set: list[tuple[float, int, int]] = [(heuristic(origin_id), counter, origin_id)]
    g_score: dict[int, float] = {origin_id: 0.0}
    came_from: dict[int, tuple[int, GraphEdge]] = {}
    closed: set[int] = set()

    while open_set:
        _, _, current = heapq.heappop(open_set)
        if current == dest_id:
            break
        if current in closed:
            continue
        closed.add(current)

        for edge in graph.adjacency.get(current, []):
            if edge.mode == "bus":
                if not edge.line_approved and not include_pending_lines:
                    continue
                if not edge.route_confirmed and not include_pending_routes:
                    continue
            neighbor = edge.to_node
            if neighbor in closed:
                continue
            tentative = g_score[current] + edge.weight
            if tentative < g_score.get(neighbor, float("inf")):
                g_score[neighbor] = tentative
                came_from[neighbor] = (current, edge)
                f = tentative + heuristic(neighbor)
                counter += 1
                heapq.heappush(open_set, (f, counter, neighbor))
    else:
        _remove_virtual_nodes(graph, origin_id, dest_id)
        return None

    if dest_id not in came_from and dest_id != origin_id:
        _remove_virtual_nodes(graph, origin_id, dest_id)
        return None

    raw_legs: list[dict] = []
    current = dest_id
    while current in came_from:
        prev, edge = came_from[current]
        from_node = graph.nodes[edge.from_node]
        to_node = graph.nodes[edge.to_node]
        dist = 0.0
        coords = edge.geometry
        for i in range(len(coords) - 1):
            dist += haversine_m(
                coords[i][0], coords[i][1], coords[i + 1][0], coords[i + 1][1]
            )
        raw_legs.append(
            {
                "mode": edge.mode,
                "line_name": edge.line_name,
                "line_id": edge.line_id,
                "from_coord": (from_node.lon, from_node.lat),
                "to_coord": (to_node.lon, to_node.lat),
                "geometry": coords,
                "distance_m": dist,
                "duration_s": edge.weight,
            }
        )
        current = prev

    raw_legs.reverse()

    merged = _merge_legs(raw_legs)

    _remove_virtual_nodes(graph, origin_id, dest_id)

    return merged


def _merge_legs(legs: list[dict]) -> list[dict]:
    """Merge consecutive legs that use the same bus line."""
    if not legs:
        return legs

    merged: list[dict] = [legs[0]]
    for leg in legs[1:]:
        prev = merged[-1]
        if (
            prev["mode"] == "bus"
            and leg["mode"] == "bus"
            and prev["line_id"] is not None
            and prev["line_id"] == leg["line_id"]
        ):
            prev["to_coord"] = leg["to_coord"]
            if prev["geometry"] and leg["geometry"]:
                prev["geometry"] = prev["geometry"] + leg["geometry"][1:]
            else:
                prev["geometry"] = prev["geometry"] + leg["geometry"]
            prev["distance_m"] += leg["distance_m"]
            prev["duration_s"] += leg["duration_s"]
        else:
            merged.append(leg)

    return merged


def _remove_virtual_nodes(graph: TransitGraph, *node_ids: int) -> None:
    """Remove virtual nodes and their edges from the graph."""
    to_remove = set(node_ids)
    for nid in to_remove:
        graph.nodes.pop(nid, None)
        graph.adjacency.pop(nid, None)
    for nid in graph.adjacency:
        graph.adjacency[nid] = [
            e for e in graph.adjacency[nid] if e.to_node not in to_remove
        ]


# ---------------------------------------------------------------------------
# Module-level cache
# ---------------------------------------------------------------------------

_cached_graph: TransitGraph | None = None


def get_or_build_graph(db: Session) -> TransitGraph:
    """Return the cached transit graph, building it if needed."""
    global _cached_graph
    if _cached_graph is None:
        _cached_graph = build_transit_graph(db)
    return _cached_graph


def invalidate_graph() -> None:
    """Clear the cached transit graph."""
    global _cached_graph
    _cached_graph = None
