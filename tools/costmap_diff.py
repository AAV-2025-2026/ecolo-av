"""
Two costmaps against each other, cell by cell, where they overlap (no ROS).

sim_check.py --costmap own compares Nav2's local costmap with ours this way, while the
car stands still in front of an obstacle: the same scan, the same moment, two grids.

    compare(a, b) -> {'cells', 'same', 'lethal_a', 'lethal_b', 'lethal_both',
                      'mean_diff', 'max_diff'}

Each grid is a dict: origin_x, origin_y (m, the corner of cell 0), resolution (m),
width, height (cells), data (raw costs 0-255, row by row, x fastest), in one frame.
Unknown (255) cells are left out of the differences.
"""

LETHAL = 254
UNKNOWN = 255


def cell_of(grid, x, y):
    """Return the index of the cell holding (x, y), or None off the grid."""
    if x < grid['origin_x'] or y < grid['origin_y']:
        return None
    cx = int((x - grid['origin_x']) / grid['resolution'])
    cy = int((y - grid['origin_y']) / grid['resolution'])
    if cx >= grid['width'] or cy >= grid['height']:
        return None
    return cy * grid['width'] + cx


def compare(a, b):
    """Return how alike two grids are where both have a cell (a's cells, looked up in b)."""
    cells = same = lethal_a = lethal_b = lethal_both = 0
    diffs = []
    res = a['resolution']
    for cy in range(a['height']):
        y = a['origin_y'] + (cy + 0.5) * res
        for cx in range(a['width']):
            x = a['origin_x'] + (cx + 0.5) * res
            j = cell_of(b, x, y)
            if j is None:
                continue
            ca, cb = a['data'][cy * a['width'] + cx], b['data'][j]
            cells += 1
            same += ca == cb
            lethal_a += ca == LETHAL
            lethal_b += cb == LETHAL
            lethal_both += ca == LETHAL and cb == LETHAL
            if UNKNOWN not in (ca, cb):
                diffs.append(abs(int(ca) - int(cb)))
    return {'cells': cells, 'same': same, 'lethal_a': lethal_a, 'lethal_b': lethal_b,
            'lethal_both': lethal_both,
            'mean_diff': sum(diffs) / len(diffs) if diffs else 0.0,
            'max_diff': max(diffs) if diffs else 0}


def summary(result):
    """Return one line for a person: how many cells agree, and the lethal ones."""
    if not result['cells']:
        return 'the grids do not overlap'
    pct = 100.0 * result['same'] / result['cells']
    return (f"{pct:.1f} % of {result['cells']} cells the same, lethal {result['lethal_a']} "
            f"vs {result['lethal_b']} ({result['lethal_both']} in both), mean difference "
            f"{result['mean_diff']:.2f}, largest {result['max_diff']}")
