"""Strategy registry for notebook-facing reconstruction."""

from .base import ReconstructionStrategy
from .dbscan_grid_search_preview import DBSCANGridSearchPreviewStrategy
from .dbscan_preview import DBSCANConsensusPreviewStrategy
from .edge_graph_consensus_preview import EdgeGraphConsensusPreviewStrategy
from .edge_sequence_overlap_assembly_preview import (
    EdgeSequenceOverlapAssemblyPreviewStrategy,
)
from .kde_preview import KDEDensityRidgePreviewStrategy
from .overlap_join_preview import OverlapJoinPreviewStrategy
from .route_file_preview import RouteFilePreviewStrategy
from .segment_vote_consensus_preview import SegmentVoteConsensusPreviewStrategy


def get_reconstruction_strategies() -> dict[str, ReconstructionStrategy]:
    """Return the available notebook-facing reconstruction strategies."""

    strategies = [
        RouteFilePreviewStrategy(),
        OverlapJoinPreviewStrategy(),
        DBSCANConsensusPreviewStrategy(),
        DBSCANGridSearchPreviewStrategy(),
        KDEDensityRidgePreviewStrategy(),
        EdgeGraphConsensusPreviewStrategy(),
        SegmentVoteConsensusPreviewStrategy(),
        EdgeSequenceOverlapAssemblyPreviewStrategy(),
    ]
    return {strategy.key: strategy for strategy in strategies}
