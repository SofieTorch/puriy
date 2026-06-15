"""Scenario configuration: everything a run needs, in one YAML file.

Scenarios are checked into ``scenarios/`` so every thesis experiment
is reproducible: same scenario + same seed → same artifacts.

A scenario carries one or more *base routes* (main line, ramal
variants, detour geometries — each its own geojson). Rider groups are
assigned to one base route; their travel window and fare areas are
arc-length fractions along that route.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import AliasChoices, BaseModel, Field, model_validator


class SpeedModel(BaseModel):
    base_speed_mps: float = 8.0          # ~29 km/h cruise
    speed_stddev_mps: float = 1.5
    min_speed_mps: float = 4.0
    max_speed_mps: float = 14.0
    stop_spacing_m: float = 400.0        # trufis stop on demand
    stop_dwell_min_s: float = 8.0
    stop_dwell_max_s: float = 45.0
    intersection_spacing_m: float = 600.0
    intersection_dwell_max_s: float = 30.0


class NoiseModel(BaseModel):
    """GPS error layers, mirroring the old transit-lab simulator's
    vocabulary: each layer can be switched off independently. Defaults
    are calm — real phone recordings are cleaner than worst-case noise.
    """

    gaussian_enabled: bool = True        # isotropic receiver noise
    gaussian_sigma_m: float = 3.0
    perpendicular_enabled: bool = True   # cross-track (multipath) noise
    perpendicular_sigma_m: float = 1.5
    # Temporal correlation of the receiver error (seconds). Real GPS
    # error drifts slowly rather than re-randomizing every fix, so a
    # trace wanders smoothly instead of scattering perpendicular each
    # sample. 0 = white noise (old behaviour); ~20s ≈ a real phone.
    gps_correlation_time_s: float = 20.0
    zigzag_enabled: bool = False         # periodic oscillation artefact
    zigzag_amplitude_m: float = 1.5
    zigzag_period_points: int = 8
    jumps_enabled: bool = False          # rare teleports
    jump_probability: float = 0.01
    jump_distance_m: float = 30.0
    missing_enabled: bool = True         # dropped fixes
    missing_probability: float = 0.02
    biased_drift_enabled: bool = False   # slow systematic offset
    biased_drift_m_per_point: float = 0.05
    biased_drift_bearing_deg: float = 70.0
    lateral_drift_enabled: bool = False  # cumulative cross-track trend
    lateral_drift_total_m: float = 3.0
    timestamp_jitter_enabled: bool = True
    timestamp_jitter_s: float = 0.15


class RouteSpec(BaseModel):
    """One base (ground-truth) route of the scenario.

    Routes are directional: trips always travel forward along the
    geometry. A line's return leg — which in practice takes different
    streets — is modelled as its own route (with its own geojson and
    rider groups), not as reversed trips.

    Roles:
    - "main": the line's primary path.
    - "ramal": a permanent variant — groups assigned to it always
      ride it; the reconstruction should emit it as its own ramal.
    - "detour": a temporary replacement for another route. During
      [from_day, to_day), a fraction of the trips of groups riding
      ``replaces`` follow this geometry instead.
    """

    name: str = "main"
    path: str = ""                       # geojson path relative to repo root
    role: Literal["main", "ramal", "detour"] = "main"
    # detour-only:
    replaces: str | None = None          # route name this detour overrides
    from_day: int = 0
    to_day: int | None = None            # None = until end of simulation
    fraction_of_trips: float = 1.0


class FareArea(BaseModel):
    """A stretch of a group's route with its own fare. A trip pays the
    most expensive area it traverses (peripheral stretches cost more)."""

    name: str = "area"
    start_fraction: float = 0.0
    end_fraction: float = 1.0
    amount_bob: float = 2.40


class PersonaSpec(BaseModel):
    name: str = "commuter"
    # Number of independent GPS traces this group contributes — the
    # reconstruction volume. Each trace is one ride; by default one device per
    # trace (accepts the legacy key `count`).
    traces: int = Field(3, validation_alias=AliasChoices("traces", "count"))
    # Which base route this group rides (RouteSpec.name). None = the
    # scenario's first main route.
    route: str | None = None
    # Travel direction along that route's geometry. "forward" follows
    # the drawn order; "backward" traverses it in reverse (e.g. the
    # return leg when you model both directions on one geometry).
    direction: Literal["forward", "backward"] = "forward"
    # The stretch of the group's route (arc-length fractions) it
    # rides: all its trips board and alight inside this window, so its
    # votes later apply to exactly these segments.
    travel_window: tuple[float, float] = (0.0, 1.0)
    # Per-trip distance (board→alight span) distribution. Each trip's length is
    # drawn ~ Normal(mean, std), clamped to the zone — set the average trace
    # length and its spread directly. When mean_trip_distance_m is unset (None
    # or 0), every trip rides the group's whole zone.
    mean_trip_distance_m: float | None = None
    trip_distance_std_m: float = 0.0
    # Where trips concentrate along the zone, as a density profile: a list of
    # non-negative bin weights from the zone start to its end (e.g. 12 bins).
    # A trip's centre is sampled from this distribution. Empty = uniform.
    # Edited graphically in the builder (drag the bars).
    trip_position_weights: list[float] = Field(default_factory=list)
    # Voting. `voters` is the number of *actual* voters in this group — each a
    # "regular" formed by aggregating `votes.eligibility_min_trips` of this
    # group's own traces onto one device, so it has the trip history to vote.
    # Voters are *carved from* `traces` (clamped to traces // min_trips), never
    # added, so reconstruction volume is unchanged. Turnout is a measured output.
    voters: int = 0
    # Where along the zone the group's regulars concentrate — a density profile
    # like `trip_position_weights`, used to pick *which* traces become voters.
    # Empty = uniform (follow trace availability). Lets voting concentrate in a
    # zone independently of the trace distribution.
    vote_position_weights: list[float] = Field(default_factory=list)
    noise_multiplier: float = 1.0        # cheap-phone persona: > 1
    fare_report_prob: float = 0.3
    sampling_rate_s: float = 2.0
    # Fare areas along this group's route.
    fare_areas: list[FareArea] = Field(default_factory=list)
    # Display color for this group's traces on the map (hex). None =
    # assigned from a palette by position.
    color: str | None = None


class VoteModel(BaseModel):
    # Trips a device needs to be an eligible voter. Voters are built to meet
    # this exactly (see PersonaSpec.voters), so eligibility is structural — no
    # time window to reason about.
    eligibility_min_trips: int = 3
    overlap_tolerance_m: float = 50.0
    approve_prob_true_edge: float = 0.92
    approve_prob_spurious_edge: float = 0.15
    edge_min_votes: int = 3
    edge_approval_threshold: float = 0.6
    route_approval_threshold: float = 0.8


class FareModel(BaseModel):
    base_fare_bob: float = 2.40          # fare when no area applies
    misreport_prob: float = 0.05


class ScenarioConfig(BaseModel):
    name: str
    description: str = ""
    routes: list[RouteSpec] = Field(default_factory=list)
    seed: int = 42
    sim_days: int = 21
    vote_day: int = 21                   # day eligibility is evaluated on
    personas: list[PersonaSpec] = Field(default_factory=lambda: [PersonaSpec()])
    speed: SpeedModel = Field(default_factory=SpeedModel)
    noise: NoiseModel = Field(default_factory=NoiseModel)
    votes: VoteModel = Field(default_factory=VoteModel)
    fares: FareModel = Field(default_factory=FareModel)
    # Reconstruction overrides (passed through to routebuilder config).
    search_radius_m: int = 40
    min_match_quality: float = 0.6
    # GPS accuracy reported to Valhalla's HMM. None = derive the true
    # value from this scenario's noise config (per rider group, scaled
    # by its noise multiplier) — the simulator knows the real sigma.
    gps_accuracy_m: float | None = None
    # Straight-line weld: consensus gaps up to this many metres are
    # connected with a straight segment (one route) instead of
    # fragmenting. Larger gaps still fragment (or Valhalla-bridge).
    weld_gap_m: float = 30.0
    # Trace stitch: a wider gap is filled with the real road geometry of
    # a trace that drove through it (only when one exists). This merges
    # fragments wherever the traces are genuinely continuous.
    stitch_gap_m: float = 150.0
    # Bridge geometric gaps in the consensus via Valhalla routing.
    # Off by default: gaps stay visible as honest fragments instead of
    # inferred (dashed) segments nobody traversed.
    bridge_gaps: bool = False
    # Ramal discovery: a cluster fully contained in a longer sibling's
    # corridor is kept as its own ramal only if at least this share of its
    # traces consistently span it end-to-end. Higher = fewer phantom
    # variants from groups that ride a fixed sub-stretch (raise toward ~0.85
    # when several groups share one trunk). None = routebuilder default (0.6).
    terminus_consistency_min_share: float | None = None
    # Ramal discovery: minimum traces a connected component needs to stand as
    # its own ramal; smaller components are absorbed into the most-compatible
    # one. Raise this when several overlapping groups ride one trunk and you
    # want their fixed-window sub-stretches folded in rather than emitted as
    # separate ramales (e.g. ~ the size of one rider group). None = default (3).
    ramal_min_cluster_size: int | None = None
    # How ramales are discovered (blind mode): "components" (bottom-up: group
    # compatible traces, over-splits when partial groups share a trunk) or
    # "divergence" (top-down: one corridor, split only at evidenced junctions,
    # so fixed-window middle groups fold into the trunk). See RamalConfig.
    ramal_discovery: Literal["components", "divergence"] = "components"
    # Consensus algorithm: "support_graph" (routebuilder native) or
    # "edge_overlap" (legacy geodata edge-sequence assembly).
    strategy: Literal["support_graph", "edge_overlap"] = "support_graph"
    # Reconstruct each base route's traces separately (the simulation
    # knows which group rode which ramal). Off = one mixed
    # reconstruction, exercising ramal discovery instead.
    reconstruct_per_route: bool = True
    # The simulator knows each route's travel direction, so by default
    # reconstruction trusts it instead of re-inferring direction
    # geometrically (which mis-splits routes that double back). Turn on
    # to exercise routebuilder's direction inference.
    infer_direction: bool = False

    # Legacy field: single-route scenarios written before RouteSpec.
    route_geojson: str | None = None

    @model_validator(mode="after")
    def _normalize(self) -> ScenarioConfig:
        if not self.routes:
            if not self.route_geojson:
                raise ValueError("scenario needs at least one route in `routes`")
            self.routes = [RouteSpec(name="main", path=self.route_geojson, role="main")]
        self.route_geojson = None

        names = [r.name for r in self.routes]
        if len(set(names)) != len(names):
            raise ValueError(f"route names must be unique, got {names}")

        rideable = [r.name for r in self.routes if r.role != "detour"]
        if not rideable:
            raise ValueError("at least one route must be main or ramal")

        for route in self.routes:
            if route.role == "detour":
                if route.replaces is None:
                    route.replaces = rideable[0]
                elif route.replaces not in rideable:
                    raise ValueError(
                        f"detour {route.name!r} replaces unknown route {route.replaces!r}"
                    )

        for persona in self.personas:
            if persona.route is None:
                persona.route = rideable[0]
            elif persona.route not in rideable:
                raise ValueError(
                    f"group {persona.name!r} rides unknown route {persona.route!r}"
                )
        return self

    @classmethod
    def from_yaml(cls, path: str | Path) -> ScenarioConfig:
        data = yaml.safe_load(Path(path).read_text())
        return cls.model_validate(data)

    def to_yaml(self, path: str | Path) -> None:
        data = self.model_dump(mode="json", exclude_none=True)
        Path(path).write_text(yaml.safe_dump(data, sort_keys=False))

    def resolve_path(self, geojson_path: str, base: Path) -> Path:
        p = Path(geojson_path)
        return p if p.is_absolute() else (base / p)
