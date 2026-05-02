"""Rebuild the transit directions graph from confirmed routes."""

from sqlalchemy.orm import Session

from geodata.transit_graph import build_transit_graph, invalidate_graph


def execute(db: Session) -> dict:
    invalidate_graph()
    graph = build_transit_graph(db)

    bus_edges = 0
    transfer_edges = 0
    for edges in graph.adjacency.values():
        for e in edges:
            if e.mode == "bus":
                bus_edges += 1
            else:
                transfer_edges += 1

    return {
        "nodes": len(graph.nodes),
        "bus_edges": bus_edges,
        "transfer_edges": transfer_edges,
    }
