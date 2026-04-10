from sqlmodel import SQLModel


class DirectionsRequest(SQLModel):
    origin: list[float]  # [lon, lat]
    destination: list[float]  # [lon, lat]
    include_pending_lines: bool = False
    include_pending_routes: bool = False


class DirectionsLeg(SQLModel):
    mode: str  # "bus" or "walk"
    line_name: str | None = None
    line_id: str | None = None  # UUID as string
    geometry: list[list[float]]  # [[lon, lat], ...]
    distance_m: float
    duration_s: float


class DirectionsResponse(SQLModel):
    legs: list[DirectionsLeg]
    total_distance_m: float
    total_duration_s: float


class GraphRebuildResponse(SQLModel):
    nodes: int
    bus_edges: int
    transfer_edges: int
    lines: int
