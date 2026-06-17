"""Tunable parameters for the reconstruction engine.

Defaults are tuned for the realistic regime in this project: 3–6
traces per line, recorded on phones riding trufis/micros in
Cochabamba's dense street grid.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CleaningConfig:
    costing: str = "bus"
    # 40m (down from geodata's 60m default): a smaller radius reduces
    # snapping onto parallel streets, one of the failure modes of the
    # previous reconstruction. Validated against seed routes in the
    # evaluation harness.
    search_radius_m: int = 40
    # Tell the HMM the truth about receiver noise: this is its emission
    # sigma, so overstating it makes wrong-street snaps look plausible.
    # ~10m fits typical phone recordings; simlab overrides it with the
    # accuracy derived from each scenario's configured noise.
    gps_accuracy_m: int = 10
    # Penalize turning between candidate edges so the matcher stops
    # taking brief cross-street excursions at intersections.
    turn_penalty_factor: int = 300
    min_match_quality: float = 0.6
    min_edges: int = 5
    # Edge shapes from trace_attributes can briefly detour onto a cross
    # street at an intersection (a Valhalla routing artifact) even though
    # the matched GPS points stay on the corridor — the "spike" the
    # matched-edge layer shows at corners. A shape vertex farther than
    # this from the clean matched-point band is such a detour and is
    # dropped from the edge geometry before it ever enters the support
    # graph. 0 disables. The matched points hug the road within ~10-15m;
    # a corner detour is 50m+.
    max_edge_detour_m: float = 30.0
    # Valhalla sometimes returns a sparse 2-point edge shape that cuts a
    # corner the bus actually rounds. When this edge's own matched GPS
    # points bow more than this off the sparse shape line, rebuild the
    # edge geometry from those (denser, road-following) points instead.
    # Below it the shape already tracks the road, so it is kept (cleaner
    # than GPS snaps). 0 disables.
    edge_corner_dev_m: float = 15.0


@dataclass
class DirectionConfig:
    # Pairs sharing fewer common edges than this (in either
    # orientation) are treated as unrelated rather than evidence of
    # same/opposite direction.
    min_common_edges: int = 5
    # ... and the overlap must also be a meaningful fraction of the
    # shorter trace. Opposite runs of an avenue often share a handful
    # of same-orientation connector edges (Valhalla models many
    # avenues as paired one-way edge chains); an absolute threshold
    # alone would misread those as same-direction evidence.
    min_overlap_fraction: float = 0.3


@dataclass
class RamalConfig:
    # How ramales are discovered from a set of traces:
    #  - "components": bottom-up — group traces into connected components of a
    #    pairwise corridor-compatibility relation, then split each once at a
    #    divergence. Over-splits when several partial groups share one trunk
    #    (each fixed-window group can island into its own ramal).
    #  - "divergence": top-down — treat all the traces as one corridor and split
    #    *only* at evidenced junctions (recursively). Trunk/middle traces stay
    #    shared, so groups that ride a fixed sub-stretch fold into the trunk
    #    instead of spawning phantom ramales. Best when variants share a trunk.
    discovery: str = "components"
    # Max divergence splits along one branch chain (recursion depth) in
    # "divergence" mode. "components" mode always splits once.
    max_divergence_depth: int = 6
    # Corridor gate: a trace point within this distance of another
    # trace's polyline counts as overlapping it.
    distance_threshold_m: float = 200.0
    min_cluster_size: int = 3
    # With very few traces a 3-trace minimum can wipe out everything;
    # below this total we lower the minimum to 2 and, if clustering
    # still yields nothing, treat all traces as a single ramal.
    small_regime_max_traces: int = 6
    resample_interval_m: float = 25.0
    # Two traces are compatible (same ramal) when they overlap by at
    # least this much and no bounded excursion (leave-and-rejoin
    # stretch) inside the overlap exceeds the excursion cap. Partial
    # traces with disjoint windows are "no information", not "far".
    min_overlap_m: float = 300.0
    max_branch_excursion_m: float = 250.0

    # --- emitted-ramal validation -------------------------------------
    # A standalone ramal shorter than this is noise, not a variant.
    min_ramal_length_m: float = 600.0
    min_ramal_traces: int = 2
    # Fragments of an already-kept ramal (same label family, split by
    # an unbridged gap) are honest partial evidence, not ramal
    # candidates: they only need to clear this debris floor.
    min_fragment_length_m: float = 300.0
    # A ramal fully contained in a longer sibling's corridor (e.g. the
    # A→B variant of an A→C line) is only believable when its traces
    # consistently span it: at least this share must start near one
    # endpoint and end near the other (within the tolerance). Scattered
    # extents mean partial riding around a popular stop, not a ramal.
    terminus_tolerance_m: float = 150.0
    terminus_consistency_min_share: float = 0.6


@dataclass
class ConsensusConfig:
    # An edge survives pruning if it appears in >= min_support_abs
    # traces OR its localized support fraction >= support_frac_min.
    min_support_abs: int = 2
    support_frac_min: float = 0.5
    # Radius around an edge midpoint within which a trace counts as
    # "covering" that part of the route (denominator of localized
    # support — handles partial traces fairly).
    coverage_radius_m: float = 100.0
    # Endpoint candidates must have at least this localized support.
    endpoint_support_frac_min: float = 0.5
    # Arcs that move backwards along the medoid ordering by more than
    # this are forbidden in path search (breaks noise cycles while
    # allowing real switchbacks).
    backtrack_tolerance_m: float = 150.0
    # Consecutive edge geometries farther apart than this need repair.
    connect_tolerance_m: float = 15.0
    # Straight-line weld: gaps up to here are connected with a straight
    # segment (kept as one route) instead of fragmenting — the
    # widest-path occasionally skips a short connector edge even though
    # the traces are continuous, and on urban roads a straight weld of
    # a few tens of metres tracks the road well. Beyond this, the route
    # bridges (if enabled) or fragments. Must be >= connect_tolerance_m.
    max_weld_gap_m: float = 30.0
    # Trace-based stitch: a wider gap is filled with the actual road
    # geometry of a supporting trace that drove straight through it
    # (real evidence, follows the road, no corner-cutting). Only used
    # when such a trace exists; otherwise the straight weld / fragment
    # rules apply. This is the right fix for "the traces are clearly
    # continuous but the consensus path skipped a connector".
    max_stitch_gap_m: float = 150.0
    # A trace-backed stitch follows a real GPS trace through the gap, so
    # it can safely span much more than the straight-weld limit — as long
    # as a supporting trace actually drove the whole way (gap ≤ this AND a
    # trace passes within tol of both ends spanning them). A genuine
    # coverage hole that no trace crosses still fragments. This is what
    # rejoins a route split into separate clusters by partial coverage.
    max_trace_bridge_gap_m: float = 700.0
    # Cross-trace bridge: when NO single trace densely spans a gap but the
    # union of traces covers the corridor, rebuild it from the median of
    # all traces' points (partial trips, or a stretch each trace matched
    # gappily). A bin needs at least cross_bridge_min_traces agreeing
    # points (within cross_bridge_corridor_m of the backbone) — that
    # cross-trace agreement is itself the noise filter: a corridor is
    # where many traces coincide, a spike is one trace no one else shares.
    cross_bridge_corridor_m: float = 35.0
    cross_bridge_min_traces: int = 3
    # Straight bridge: when a gap is an unambiguous straight shot — the
    # two fragments point at each other (no turn) and the supporting
    # traces hug the straight line (no block detour bulging off it) —
    # connect it with a clean straight line, even though map-matching
    # snap-spikes corrupted the trace geometry right at the junction.
    # A turn or a go-around-the-block detour fails one of these checks
    # and is left fragmented.
    straight_bridge_max_turn_deg: float = 20.0
    straight_bridge_max_trace_dev_m: float = 40.0
    # Merging two fragments end-to-end is only a continuation when the
    # route keeps heading the same way through the join. Beyond this turn
    # the join is a doubling-back (e.g. two ramal variants that merely
    # share a terminus), so it is left unmerged. A normal street corner
    # (~90deg) stays under this; a U-turn (~180deg) does not.
    max_merge_turn_deg: float = 110.0
    # De-drift: the traces are ground truth, so a consensus stretch that
    # strays farther than this from every trace (a wrong dogleg onto a
    # cross street from a snap-spike) is replaced with the band's own
    # path. 0 disables. On-band points stay within ~15-20m of traces;
    # a real drift is much farther.
    max_offband_m: float = 35.0
    # Gaps larger than this are never bridged with routed geometry —
    # the route is split into fragments with a diagnostic instead.
    max_bridge_gap_m: float = 300.0
    # Competing-branch (divergence) detection: both branches need at
    # least this many supporting traces to split into separate ramales.
    divergence_min_traces: int = 2
    # ... and the two candidate variants must actually separate by
    # more than this anywhere. Parallel carriageways of one avenue
    # (~15-40m apart) produce competing branches with disjoint trace
    # sets but are the same route, not two ramales.
    divergence_min_separation_m: float = 100.0


@dataclass
class ReconstructionConfig:
    cleaning: CleaningConfig = field(default_factory=CleaningConfig)
    direction: DirectionConfig = field(default_factory=DirectionConfig)
    ramales: RamalConfig = field(default_factory=RamalConfig)
    consensus: ConsensusConfig = field(default_factory=ConsensusConfig)
