"""tools/costmap_diff.py: two costmaps compared where they overlap."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import costmap_diff  # noqa: E402


def grid(ox, oy, w, h, data, res=1.0):
    return {'origin_x': ox, 'origin_y': oy, 'resolution': res, 'width': w, 'height': h,
            'data': data}


def test_identical_grids_agree_everywhere():
    g = grid(0.0, 0.0, 3, 2, [0, 254, 10, 0, 0, 253])
    r = costmap_diff.compare(g, g)
    assert r == {'cells': 6, 'same': 6, 'lethal_a': 1, 'lethal_b': 1, 'lethal_both': 1,
                 'mean_diff': 0.0, 'max_diff': 0}
    assert '100.0 %' in costmap_diff.summary(r)


def test_shifted_windows_compare_only_the_overlap_on_the_same_ground():
    a = grid(0.0, 0.0, 3, 1, [0, 254, 0])
    # b starts one cell east: its cell 0 is a's cell 1.
    b = grid(1.0, 0.0, 3, 1, [254, 50, 7])
    r = costmap_diff.compare(a, b)
    assert r['cells'] == 2 and r['lethal_both'] == 1
    assert r['max_diff'] == 50


def test_unknown_cells_are_left_out_of_the_differences():
    a = grid(0.0, 0.0, 2, 1, [255, 0])
    b = grid(0.0, 0.0, 2, 1, [0, 0])
    r = costmap_diff.compare(a, b)
    assert r['same'] == 1 and r['max_diff'] == 0
    assert costmap_diff.summary(costmap_diff.compare(a, grid(9.0, 9.0, 1, 1, [0]))) == (
        'the grids do not overlap')
