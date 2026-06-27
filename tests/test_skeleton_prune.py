"""Tests for skeleton spur pruning."""

from __future__ import annotations

import numpy as np
import pytest

from xiaozhi_drawing.skeleton_prune import prune_skeleton_spurs


def _t_shape_with_short_spur() -> np.ndarray:
    """Vertical bar with a 2-pixel horizontal spur on its left side."""
    skeleton = np.zeros((15, 15), dtype=np.uint8)
    skeleton[2:13, 7] = 255  # vertical bar
    skeleton[5, 6:4:-1] = 255  # spur: (5,6) and (5,5)
    return skeleton


class TestSkeletonPrune:
    def test_prune_removes_short_spur(self):
        skeleton = _t_shape_with_short_spur()
        pruned = prune_skeleton_spurs(skeleton, spur_length_threshold=5)
        assert pruned[5, 5] == 0
        assert pruned[5, 6] == 0
        # Main vertical bar remains.
        assert pruned[2:13, 7].sum() > 0

    def test_prune_preserves_long_branch(self):
        skeleton = np.zeros((10, 10), dtype=np.uint8)
        skeleton[3, 1:9] = 255  # long horizontal line
        pruned = prune_skeleton_spurs(skeleton, spur_length_threshold=5)
        assert pruned[3, 1:9].sum() > 0

    def test_prune_empty_safe(self):
        skeleton = np.zeros((8, 8), dtype=np.uint8)
        pruned = prune_skeleton_spurs(skeleton, spur_length_threshold=5)
        assert pruned.sum() == 0

    def test_prune_zero_threshold_skips(self):
        skeleton = _t_shape_with_short_spur()
        pruned = prune_skeleton_spurs(skeleton, spur_length_threshold=0)
        assert np.array_equal(pruned, skeleton)
