"""
validate.py — IDDFS solver + baseline calibration

Solves shortest paths for all tw game level_configs,
computes baseline_actions = ceil(shortest_moves * 1.2) + 1 (+1 for CONFIRM).
"""
import math
import time
from typing import List, Tuple, Set, Dict, Optional, FrozenSet
from collections import deque


# ====================================================================
# Shared utilities
# ====================================================================

def _path_to_edges(path):
    """Convert path node sequence to edge set."""
    edges = set()
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        edges.add((min(a, b), max(a, b)))
    return edges


def _path_splits_regions(path, cols, rows):
    """Split the panel into regions based on the path."""
    path_edges = _path_to_edges(path)

    visited = set()
    regions = []

    for row in range(rows):
        for col in range(cols):
            cell = (col, row)
            if cell in visited:
                continue

            region = set()
            queue = [cell]
            while queue:
                c = queue.pop(0)
                if c in visited:
                    continue
                visited.add(c)
                region.add(c)

                cc, cr = c
                for dc, dr, edge_n1, edge_n2 in [
                    (-1, 0, (cc, cr), (cc, cr + 1)),
                    (1, 0, (cc + 1, cr), (cc + 1, cr + 1)),
                    (0, -1, (cc, cr), (cc + 1, cr)),
                    (0, 1, (cc, cr + 1), (cc + 1, cr + 1)),
                ]:
                    nc, nr = cc + dc, cr + dr
                    if 0 <= nc < cols and 0 <= nr < rows:
                        edge = (min(edge_n1, edge_n2), max(edge_n1, edge_n2))
                        if edge not in path_edges and (nc, nr) not in visited:
                            queue.append((nc, nr))

            regions.append(region)

    return regions


def _cell_edge_count(cell, path_edges):
    """Count the number of cell boundary edges traversed by the path."""
    col, row = cell
    edges = [
        ((col, row), (col + 1, row)),
        ((col, row + 1), (col + 1, row + 1)),
        ((col, row), (col, row + 1)),
        ((col + 1, row), (col + 1, row + 1)),
    ]
    count = 0
    for e in edges:
        normalized = (min(e[0], e[1]), max(e[0], e[1]))
        if normalized in path_edges:
            count += 1
    return count


def _parse_cell_dict(d):
    """Parse "c,r" -> value dict into (c,r) -> value."""
    result = {}
    for k, v in d.items():
        parts = k.split(",")
        result[(int(parts[0]), int(parts[1]))] = v
    return result


def _parse_breakpoints(config: dict) -> Set[Tuple[Tuple[int, int], Tuple[int, int]]]:
    """Parse config["breakpoints"] into a normalized edge set."""
    breakpoints: Set[Tuple[Tuple[int, int], Tuple[int, int]]] = set()
    for bp in config.get("breakpoints", []):
        n1, n2 = tuple(bp[0]), tuple(bp[1])
        breakpoints.add((min(n1, n2), max(n1, n2)))
    return breakpoints


# ====================================================================
# tw01 PathDots Solver — BFS for shortest path
# ====================================================================

def solve_tw01(config: dict, timeout: float = 10.0) -> Optional[List[Tuple[int, int]]]:
    """BFS solve tw01 PathDots puzzle, return shortest path (node sequence)."""
    t0 = time.time()

    cols = config["cols"]
    rows = config["rows"]
    start = tuple(config["start"])
    end = tuple(config["end"])
    dots = set(tuple(d) for d in config["dots"])

    breakpoints = _parse_breakpoints(config)

    initial_visited_dots = frozenset({start} & dots)
    initial_state = (start, initial_visited_dots)

    queue = deque()
    queue.append((initial_state, [start]))
    seen = {initial_state}

    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    while queue:
        if time.time() - t0 > timeout:
            return None

        (node, visited_dots), path = queue.popleft()

        for dc, dr in directions:
            nc, nr = node[0] + dc, node[1] + dr
            next_node = (nc, nr)

            if not (0 <= nc <= cols and 0 <= nr <= rows):
                continue
            if next_node in set(path):
                continue

            edge = (min(node, next_node), max(node, next_node))
            if edge in breakpoints:
                continue

            new_visited = visited_dots | ({next_node} & dots)
            new_path = path + [next_node]

            if next_node == end and new_visited == dots:
                return new_path

            new_state = (next_node, new_visited)
            if new_state not in seen:
                seen.add(new_state)
                queue.append((new_state, new_path))

    return None


# ====================================================================
# tw02 ColorSplit Solver — DFS + region validation
# ====================================================================

def _check_colorsplit(path, squares, cols, rows):
    """Check whether the path satisfies ColorSplit constraints."""
    regions = _path_splits_regions(path, cols, rows)
    for region in regions:
        colors_in_region = set()
        for cell in region:
            if cell in squares:
                colors_in_region.add(squares[cell])
        if len(colors_in_region) > 1:
            return False
    return True


def solve_tw02(config: dict, timeout: float = 5.0) -> Optional[List[Tuple[int, int]]]:
    """DFS solve tw02 ColorSplit puzzle."""
    cols = config["cols"]
    rows = config["rows"]
    start = tuple(config["start"])
    end = tuple(config["end"])

    squares = _parse_cell_dict(config["squares"])
    breakpoints = _parse_breakpoints(config)

    t0 = time.time()
    best_solution = [None]
    best_len = [(cols + 1) * (rows + 1) + 1]

    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    def dfs(path, path_set):
        if time.time() - t0 > timeout:
            return
        if len(path) >= best_len[0]:
            return

        node = path[-1]

        for dc, dr in directions:
            nc, nr = node[0] + dc, node[1] + dr
            next_node = (nc, nr)

            if not (0 <= nc <= cols and 0 <= nr <= rows):
                continue
            if next_node in path_set:
                continue

            edge = (min(node, next_node), max(node, next_node))
            if edge in breakpoints:
                continue

            path.append(next_node)
            path_set.add(next_node)

            if next_node == end:
                if _check_colorsplit(path, squares, cols, rows):
                    if len(path) < best_len[0]:
                        best_len[0] = len(path)
                        best_solution[0] = list(path)
            else:
                if len(path) < best_len[0] - 1:
                    dfs(path, path_set)

            path.pop()
            path_set.remove(next_node)

    dfs([start], {start})
    return best_solution[0]


# ====================================================================
# tw03 ShapeFill Solver — DFS + backtracking tiling
# ====================================================================

def _rotations(shape):
    """Generate all rotations of a shape (0/90/180/270)."""
    shapes = [shape]
    current = shape
    for _ in range(3):
        current = [(y, -x) for x, y in current]
        # Normalize to positive coordinates
        min_x = min(x for x, y in current)
        min_y = min(y for x, y in current)
        current = [(x - min_x, y - min_y) for x, y in current]
        current.sort()
        if current not in shapes:
            shapes.append(current)
    return shapes


def _can_place(shape_cells, region_cells, placed):
    """Check whether a shape can be placed in the region."""
    for cell in shape_cells:
        if cell not in region_cells or cell in placed:
            return False
    return True


def _exact_cover(shapes, region_cells, placed, idx):
    """Backtrack to check if shapes can exactly cover the remaining region."""
    remaining = region_cells - placed
    if not remaining:
        return idx >= len(shapes)
    if idx >= len(shapes):
        return len(remaining) == 0

    shape_info = shapes[idx]
    cells = shape_info["cells"]
    is_rotated = shape_info["rotated"]
    is_negative = shape_info["negative"]

    if is_negative:
        # Negative shape: skip placement (area subtraction handled in pre-check)
        return _exact_cover(shapes, region_cells, placed, idx + 1)

    # Get all possible rotations
    variants = _rotations(cells) if is_rotated else [cells]

    # Try placing at each position in the region
    anchor = min(remaining)  # First uncovered cell
    for variant in variants:
        # Align variant's first cell with anchor
        for ref in variant:
            offset_x = anchor[0] - ref[0]
            offset_y = anchor[1] - ref[1]
            placed_cells = [(x + offset_x, y + offset_y) for x, y in variant]
            placed_set = set(placed_cells)

            if _can_place(placed_cells, region_cells, placed):
                new_placed = placed | placed_set
                if _exact_cover(shapes, region_cells, new_placed, idx + 1):
                    return True

    return False


def _check_shapefill(path, tetris, cols, rows):
    """Check whether the path satisfies ShapeFill constraints."""
    regions = _path_splits_regions(path, cols, rows)
    tetris_parsed = {}
    for k, v in tetris.items():
        parts = k.split(",")
        tetris_parsed[(int(parts[0]), int(parts[1]))] = v

    for region in regions:
        shapes_in_region = []
        total_positive_area = 0
        total_negative_area = 0

        for cell in region:
            if cell in tetris_parsed:
                t = tetris_parsed[cell]
                shape_cells = [tuple(s) for s in t["shape"]]
                is_negative = t.get("negative", False)
                shapes_in_region.append({
                    "cells": sorted(shape_cells),
                    "rotated": t.get("rotated", False),
                    "negative": is_negative,
                })
                if is_negative:
                    total_negative_area += len(shape_cells)
                else:
                    total_positive_area += len(shape_cells)

        if not shapes_in_region:
            continue

        # Area pre-check
        expected_area = total_positive_area - total_negative_area
        if expected_area != len(region):
            return False

        # Use only positive shapes for exact cover
        positive_shapes = [s for s in shapes_in_region if not s["negative"]]
        if not _exact_cover(positive_shapes, set(region), set(), 0):
            return False

    return True


def solve_tw03(config: dict, timeout: float = 10.0) -> Optional[List[Tuple[int, int]]]:
    """DFS solve tw03 ShapeFill puzzle."""
    cols = config["cols"]
    rows = config["rows"]
    start = tuple(config["start"])
    end = tuple(config["end"])
    tetris = config["tetris"]
    breakpoints = _parse_breakpoints(config)

    t0 = time.time()
    best_solution = [None]
    best_len = [(cols + 1) * (rows + 1) + 1]

    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    def dfs(path, path_set):
        if time.time() - t0 > timeout:
            return
        if len(path) >= best_len[0]:
            return

        node = path[-1]
        for dc, dr in directions:
            nc, nr = node[0] + dc, node[1] + dr
            next_node = (nc, nr)
            if not (0 <= nc <= cols and 0 <= nr <= rows):
                continue
            if next_node in path_set:
                continue

            edge = (min(node, next_node), max(node, next_node))
            if edge in breakpoints:
                continue

            path.append(next_node)
            path_set.add(next_node)

            if next_node == end:
                if _check_shapefill(path, tetris, cols, rows):
                    if len(path) < best_len[0]:
                        best_len[0] = len(path)
                        best_solution[0] = list(path)
            else:
                if len(path) < best_len[0] - 1:
                    dfs(path, path_set)

            path.pop()
            path_set.remove(next_node)

    dfs([start], {start})
    return best_solution[0]


# ====================================================================
# tw04 SymDraw Solver — BFS with mirrored moves
# ====================================================================

def solve_tw04(config: dict, timeout: float = 10.0) -> Optional[List[Tuple[int, int]]]:
    """BFS solve tw04 SymDraw puzzle, return the blue path."""
    t0 = time.time()

    cols = config["cols"]
    rows = config["rows"]
    sym = config["symmetry"]

    blue_start = tuple(config["blue_start"])
    blue_end = tuple(config["blue_end"])
    yellow_start = tuple(config["yellow_start"])
    yellow_end = tuple(config["yellow_end"])
    blue_dots = set(tuple(d) for d in config["blue_dots"])
    yellow_dots = set(tuple(d) for d in config["yellow_dots"])
    breakpoints = _parse_breakpoints(config)

    def mirror_delta(dc, dr):
        if sym == "horizontal":
            return (-dc, dr)
        elif sym == "vertical":
            return (dc, -dr)
        elif sym == "rotational":
            return (-dc, -dr)
        return (dc, dr)

    def valid_node(n):
        return 0 <= n[0] <= cols and 0 <= n[1] <= rows

    b_init_dots = frozenset({blue_start} & blue_dots)
    y_init_dots = frozenset({yellow_start} & yellow_dots)

    initial = (blue_start, yellow_start, b_init_dots, y_init_dots)
    queue = deque()
    queue.append((initial, [blue_start]))
    seen = {(blue_start, yellow_start, b_init_dots, y_init_dots)}

    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    while queue:
        if time.time() - t0 > timeout:
            return None

        (b_node, y_node, b_visited, y_visited), b_path = queue.popleft()

        for dc, dr in directions:
            b_next = (b_node[0] + dc, b_node[1] + dr)
            ydc, ydr = mirror_delta(dc, dr)
            y_next = (y_node[0] + ydc, y_node[1] + ydr)

            if not valid_node(b_next) or not valid_node(y_next):
                continue

            # breakpoint check for both paths
            b_edge = (min(b_node, b_next), max(b_node, b_next))
            y_edge = (min(y_node, y_next), max(y_node, y_next))
            if b_edge in breakpoints or y_edge in breakpoints:
                continue

            if b_next in set(b_path):
                continue
            y_path = _compute_yellow_path(b_path + [b_next], yellow_start, sym, cols, rows)
            if y_next in set(y_path[:-1]):
                continue
            if b_next == y_next:
                continue

            new_b_visited = b_visited | ({b_next} & blue_dots)
            new_y_visited = y_visited | ({y_next} & yellow_dots)
            new_b_path = b_path + [b_next]

            if (b_next == blue_end and y_next == yellow_end and
                    new_b_visited == blue_dots and new_y_visited == yellow_dots):
                return new_b_path

            state = (b_next, y_next, new_b_visited, new_y_visited)
            if state not in seen:
                seen.add(state)
                queue.append(((b_next, y_next, new_b_visited, new_y_visited), new_b_path))

    return None


def _compute_yellow_path(blue_path, yellow_start, sym, cols, rows):
    """Compute yellow path from blue path."""
    y_path = [yellow_start]
    for i in range(1, len(blue_path)):
        bc, br = blue_path[i]
        pc, pr = blue_path[i - 1]
        dc, dr = bc - pc, br - pr
        if sym == "horizontal":
            ydc, ydr = -dc, dr
        elif sym == "vertical":
            ydc, ydr = dc, -dr
        elif sym == "rotational":
            ydc, ydr = -dc, -dr
        else:
            ydc, ydr = dc, dr
        last = y_path[-1]
        y_path.append((last[0] + ydc, last[1] + ydr))
    return y_path


# ====================================================================
# tw05 StarPair Solver — DFS + region star pairing validation
# ====================================================================

def _check_starpair(path, stars, cols, rows):
    """Check whether the path satisfies StarPair constraints. Exactly 2 stars per color per region."""
    regions = _path_splits_regions(path, cols, rows)
    for region in regions:
        color_counts = {}
        for cell in region:
            if cell in stars:
                c = stars[cell]
                color_counts[c] = color_counts.get(c, 0) + 1
        for color, count in color_counts.items():
            if count != 2:
                return False
    return True


def solve_tw05(config: dict, timeout: float = 5.0) -> Optional[List[Tuple[int, int]]]:
    """DFS solve tw05 StarPair puzzle."""
    cols = config["cols"]
    rows = config["rows"]
    start = tuple(config["start"])
    end = tuple(config["end"])

    stars = _parse_cell_dict(config["stars"])
    breakpoints = _parse_breakpoints(config)

    t0 = time.time()
    best_solution = [None]
    best_len = [(cols + 1) * (rows + 1) + 1]
    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    def dfs(path, path_set):
        if time.time() - t0 > timeout:
            return
        if len(path) >= best_len[0]:
            return
        node = path[-1]
        for dc, dr in directions:
            nc, nr = node[0] + dc, node[1] + dr
            next_node = (nc, nr)
            if not (0 <= nc <= cols and 0 <= nr <= rows):
                continue
            if next_node in path_set:
                continue

            edge = (min(node, next_node), max(node, next_node))
            if edge in breakpoints:
                continue
            path.append(next_node)
            path_set.add(next_node)
            if next_node == end:
                if _check_starpair(path, stars, cols, rows):
                    if len(path) < best_len[0]:
                        best_len[0] = len(path)
                        best_solution[0] = list(path)
            else:
                if len(path) < best_len[0] - 1:
                    dfs(path, path_set)
            path.pop()
            path_set.remove(next_node)

    dfs([start], {start})
    return best_solution[0]


# ====================================================================
# tw06 TriCount Solver — DFS + edge count validation
# ====================================================================

def _check_tricount(path, triangles, cols, rows):
    """Check whether the path satisfies TriCount constraints. Path edge count = triangle count for each triangle cell."""
    path_edges = _path_to_edges(path)
    for cell, expected_count in triangles.items():
        actual = _cell_edge_count(cell, path_edges)
        if actual != expected_count:
            return False
    return True


def solve_tw06(config: dict, timeout: float = 5.0) -> Optional[List[Tuple[int, int]]]:
    """DFS solve tw06 TriCount puzzle."""
    cols = config["cols"]
    rows = config["rows"]
    start = tuple(config["start"])
    end = tuple(config["end"])

    triangles = _parse_cell_dict(config["triangles"])
    breakpoints = _parse_breakpoints(config)

    t0 = time.time()
    best_solution = [None]
    best_len = [(cols + 1) * (rows + 1) + 1]
    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    def dfs(path, path_set):
        if time.time() - t0 > timeout:
            return
        if len(path) >= best_len[0]:
            return
        node = path[-1]
        for dc, dr in directions:
            nc, nr = node[0] + dc, node[1] + dr
            next_node = (nc, nr)
            if not (0 <= nc <= cols and 0 <= nr <= rows):
                continue
            if next_node in path_set:
                continue

            edge = (min(node, next_node), max(node, next_node))
            if edge in breakpoints:
                continue
            path.append(next_node)
            path_set.add(next_node)
            if next_node == end:
                if _check_tricount(path, triangles, cols, rows):
                    if len(path) < best_len[0]:
                        best_len[0] = len(path)
                        best_solution[0] = list(path)
            else:
                if len(path) < best_len[0] - 1:
                    dfs(path, path_set)
            path.pop()
            path_set.remove(next_node)

    dfs([start], {start})
    return best_solution[0]


# ====================================================================
# tw07 EraserLogic Solver — DFS + elimination meta-reasoning
# ====================================================================

def _count_violations(region, squares, stars, triangles, path_edges):
    """Count constraint violations within a region."""
    violations = 0

    # Square constraint violation: multiple colors in region
    if squares:
        colors = set()
        for cell in region:
            if cell in squares:
                colors.add(squares[cell])
        if len(colors) > 1:
            violations += len(colors) - 1

    # Star constraint violation: not exactly 2 per color
    if stars:
        color_counts = {}
        for cell in region:
            if cell in stars:
                c = stars[cell]
                color_counts[c] = color_counts.get(c, 0) + 1
        for color, count in color_counts.items():
            if count != 2:
                violations += abs(count - 2)

    # Triangle constraint violation: edge count mismatch
    if triangles:
        for cell in region:
            if cell in triangles:
                actual = _cell_edge_count(cell, path_edges)
                if actual != triangles[cell]:
                    violations += 1

    return violations


def _check_eraser(path, erasers, squares, stars, triangles, cols, rows):
    """Check whether the path satisfies EraserLogic constraints."""
    regions = _path_splits_regions(path, cols, rows)
    path_edges = _path_to_edges(path)
    eraser_set = set(tuple(e) for e in erasers)

    for region in regions:
        eraser_count = sum(1 for cell in region if cell in eraser_set)
        violations = _count_violations(region, squares, stars, triangles, path_edges)
        if violations != eraser_count:
            return False
    return True


def solve_tw07(config: dict, timeout: float = 10.0) -> Optional[List[Tuple[int, int]]]:
    """DFS solve tw07 EraserLogic puzzle."""
    cols = config["cols"]
    rows = config["rows"]
    start = tuple(config["start"])
    end = tuple(config["end"])
    erasers = [tuple(e) for e in config["erasers"]]

    squares = _parse_cell_dict(config.get("squares", {}))
    stars = _parse_cell_dict(config.get("stars", {}))
    triangles = _parse_cell_dict(config.get("triangles", {}))
    breakpoints = _parse_breakpoints(config)

    t0 = time.time()
    best_solution = [None]
    best_len = [(cols + 1) * (rows + 1) + 1]
    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    def dfs(path, path_set):
        if time.time() - t0 > timeout:
            return
        if len(path) >= best_len[0]:
            return
        node = path[-1]
        for dc, dr in directions:
            nc, nr = node[0] + dc, node[1] + dr
            next_node = (nc, nr)
            if not (0 <= nc <= cols and 0 <= nr <= rows):
                continue
            if next_node in path_set:
                continue

            edge = (min(node, next_node), max(node, next_node))
            if edge in breakpoints:
                continue
            path.append(next_node)
            path_set.add(next_node)
            if next_node == end:
                if _check_eraser(path, erasers, squares, stars, triangles, cols, rows):
                    if len(path) < best_len[0]:
                        best_len[0] = len(path)
                        best_solution[0] = list(path)
            else:
                if len(path) < best_len[0] - 1:
                    dfs(path, path_set)
            path.pop()
            path_set.remove(next_node)

    dfs([start], {start})
    return best_solution[0]


# ====================================================================
# tw07 helpers for tetris violation counting (reused by tw13)
# ====================================================================

def _count_tetris_violations(region, tetris, path_edges, cols, rows):
    """Count tetris violations within a region.

    If positive shapes in the region cannot exactly cover the region, return violation count.
    Violation count = 1 (simplified: tiling failure counts as 1 violation).
    """
    tetris_parsed = {}
    for k, v in tetris.items():
        if isinstance(k, str):
            parts = k.split(",")
            tetris_parsed[(int(parts[0]), int(parts[1]))] = v
        else:
            tetris_parsed[k] = v

    shapes_in_region = []
    total_positive_area = 0
    total_negative_area = 0

    for cell in region:
        if cell in tetris_parsed:
            t = tetris_parsed[cell]
            shape_cells = [tuple(s) if isinstance(s, (list, tuple)) else s for s in t["shape"]]
            is_negative = t.get("negative", False)
            shapes_in_region.append({
                "cells": sorted(shape_cells),
                "rotated": t.get("rotated", False),
                "negative": is_negative,
            })
            if is_negative:
                total_negative_area += len(shape_cells)
            else:
                total_positive_area += len(shape_cells)

    if not shapes_in_region:
        return 0

    expected_area = total_positive_area - total_negative_area
    if expected_area != len(region):
        return 1

    positive_shapes = [s for s in shapes_in_region if not s["negative"]]
    if not _exact_cover(positive_shapes, set(region), set(), 0):
        return 1

    return 0


# ====================================================================
# tw08 ComboBasic Solver — DFS + dual constraints
# ====================================================================

def _check_combo(path, squares, stars, cols, rows):
    """Check whether the path satisfies both ColorSplit + StarPair."""
    return (_check_colorsplit(path, squares, cols, rows) and
            _check_starpair(path, stars, cols, rows))


def solve_tw08(config: dict, timeout: float = 10.0) -> Optional[List[Tuple[int, int]]]:
    """DFS solve tw08 ComboBasic puzzle."""
    cols = config["cols"]
    rows = config["rows"]
    start = tuple(config["start"])
    end = tuple(config["end"])

    squares = _parse_cell_dict(config["squares"])
    stars = _parse_cell_dict(config["stars"])
    breakpoints = _parse_breakpoints(config)

    t0 = time.time()
    best_solution = [None]
    best_len = [(cols + 1) * (rows + 1) + 1]
    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    def dfs(path, path_set):
        if time.time() - t0 > timeout:
            return
        if len(path) >= best_len[0]:
            return
        node = path[-1]
        for dc, dr in directions:
            nc, nr = node[0] + dc, node[1] + dr
            next_node = (nc, nr)
            if not (0 <= nc <= cols and 0 <= nr <= rows):
                continue
            if next_node in path_set:
                continue

            edge = (min(node, next_node), max(node, next_node))
            if edge in breakpoints:
                continue
            path.append(next_node)
            path_set.add(next_node)
            if next_node == end:
                if _check_combo(path, squares, stars, cols, rows):
                    if len(path) < best_len[0]:
                        best_len[0] = len(path)
                        best_solution[0] = list(path)
            else:
                if len(path) < best_len[0] - 1:
                    dfs(path, path_set)
            path.pop()
            path_set.remove(next_node)

    dfs([start], {start})
    return best_solution[0]


# ====================================================================
# tw11 MultiRegion Solver — DFS + multi-constraint validation
# ====================================================================

def _check_multiregion(path, config, cols, rows):
    """Check whether the path satisfies all present region constraints (AND logic)."""
    squares = _parse_cell_dict(config.get("squares", {}))
    stars = _parse_cell_dict(config.get("stars", {}))
    triangles = _parse_cell_dict(config.get("triangles", {}))
    tetris = config.get("tetris", {})

    if squares:
        if not _check_colorsplit(path, squares, cols, rows):
            return False
    if stars:
        if not _check_starpair(path, stars, cols, rows):
            return False
    if triangles:
        if not _check_tricount(path, triangles, cols, rows):
            return False
    if tetris:
        if not _check_shapefill(path, tetris, cols, rows):
            return False

    return True


def solve_tw11(config: dict, timeout: float = 10.0) -> Optional[List[Tuple[int, int]]]:
    """DFS solve tw11 MultiRegion puzzle."""
    cols = config["cols"]
    rows = config["rows"]
    start = tuple(config["start"])
    end = tuple(config["end"])
    breakpoints = _parse_breakpoints(config)

    t0 = time.time()
    best_solution = [None]
    best_len = [(cols + 1) * (rows + 1) + 1]
    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    def dfs(path, path_set):
        if time.time() - t0 > timeout:
            return
        if len(path) >= best_len[0]:
            return
        node = path[-1]
        for dc, dr in directions:
            nc, nr = node[0] + dc, node[1] + dr
            next_node = (nc, nr)
            if not (0 <= nc <= cols and 0 <= nr <= rows):
                continue
            if next_node in path_set:
                continue
            edge = (min(node, next_node), max(node, next_node))
            if edge in breakpoints:
                continue
            path.append(next_node)
            path_set.add(next_node)
            if next_node == end:
                if _check_multiregion(path, config, cols, rows):
                    if len(path) < best_len[0]:
                        best_len[0] = len(path)
                        best_solution[0] = list(path)
            else:
                if len(path) < best_len[0] - 1:
                    dfs(path, path_set)
            path.pop()
            path_set.remove(next_node)

    dfs([start], {start})
    return best_solution[0]


# ====================================================================
# tw12 HexCombo Solver — BFS + dots + region validation
# ====================================================================

def solve_tw12(config: dict, timeout: float = 10.0) -> Optional[List[Tuple[int, int]]]:
    """BFS solve tw12 HexCombo puzzle. Path must visit all dots and satisfy region constraints."""
    t0 = time.time()

    cols = config["cols"]
    rows = config["rows"]
    start = tuple(config["start"])
    end = tuple(config["end"])
    dots = set(tuple(d) for d in config["dots"])
    breakpoints = _parse_breakpoints(config)

    initial_visited_dots = frozenset({start} & dots)
    initial_state = (start, initial_visited_dots)

    queue = deque()
    queue.append((initial_state, [start]))
    seen = {initial_state}

    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    while queue:
        if time.time() - t0 > timeout:
            return None

        (node, visited_dots), path = queue.popleft()

        for dc, dr in directions:
            nc, nr = node[0] + dc, node[1] + dr
            next_node = (nc, nr)

            if not (0 <= nc <= cols and 0 <= nr <= rows):
                continue
            if next_node in set(path):
                continue

            edge = (min(node, next_node), max(node, next_node))
            if edge in breakpoints:
                continue

            new_visited = visited_dots | ({next_node} & dots)
            new_path = path + [next_node]

            if next_node == end and new_visited == dots:
                # All dots visited, now check region constraints
                if _check_multiregion(new_path, config, cols, rows):
                    return new_path

            new_state = (next_node, new_visited)
            if new_state not in seen:
                seen.add(new_state)
                queue.append((new_state, new_path))

    return None


# ====================================================================
# tw13 EraserAll Solver — DFS/BFS + extended elimination logic
# ====================================================================

def _count_violations_extended(region, squares, stars, triangles, tetris, path_edges, cols, rows):
    """Extended violation count, with tetris violation support."""
    violations = 0

    # Square constraint violation
    if squares:
        colors = set()
        for cell in region:
            if cell in squares:
                colors.add(squares[cell])
        if len(colors) > 1:
            violations += len(colors) - 1

    # Star constraint violation
    if stars:
        color_counts = {}
        for cell in region:
            if cell in stars:
                c = stars[cell]
                color_counts[c] = color_counts.get(c, 0) + 1
        for color, count in color_counts.items():
            if count != 2:
                violations += abs(count - 2)

    # Triangle constraint violation
    if triangles:
        for cell in region:
            if cell in triangles:
                actual = _cell_edge_count(cell, path_edges)
                if actual != triangles[cell]:
                    violations += 1

    # Tetris constraint violation
    if tetris:
        violations += _count_tetris_violations(region, tetris, path_edges, cols, rows)

    return violations


def _check_eraser_all(path, erasers, config, cols, rows):
    """Check whether the path satisfies EraserAll constraints (extended, supports tetris + hex dots)."""
    # If dots exist, first check whether all are visited
    if "dots" in config:
        dots = set(tuple(d) for d in config["dots"])
        path_set = set(path)
        for dot in dots:
            if dot not in path_set:
                return False

    regions = _path_splits_regions(path, cols, rows)
    path_edges = _path_to_edges(path)
    eraser_set = set(tuple(e) for e in erasers)

    squares = _parse_cell_dict(config.get("squares", {}))
    stars = _parse_cell_dict(config.get("stars", {}))
    triangles = _parse_cell_dict(config.get("triangles", {}))
    tetris = config.get("tetris", {})

    for region in regions:
        eraser_count = sum(1 for cell in region if cell in eraser_set)
        violations = _count_violations_extended(
            region, squares, stars, triangles, tetris, path_edges, cols, rows
        )
        if violations != eraser_count:
            return False
    return True


def solve_tw13(config: dict, timeout: float = 10.0) -> Optional[List[Tuple[int, int]]]:
    """Solve tw13 EraserAll puzzle. Uses BFS when hex dots are present, otherwise DFS."""
    cols = config["cols"]
    rows = config["rows"]
    start = tuple(config["start"])
    end = tuple(config["end"])
    erasers = [tuple(e) for e in config["erasers"]]
    breakpoints = _parse_breakpoints(config)
    has_dots = "dots" in config and config["dots"]

    t0 = time.time()

    if has_dots:
        # BFS with dot tracking
        dots = set(tuple(d) for d in config["dots"])
        initial_visited_dots = frozenset({start} & dots)
        initial_state = (start, initial_visited_dots)

        queue = deque()
        queue.append((initial_state, [start]))
        seen = {initial_state}

        directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

        while queue:
            if time.time() - t0 > timeout:
                return None

            (node, visited_dots), path = queue.popleft()

            for dc, dr in directions:
                nc, nr = node[0] + dc, node[1] + dr
                next_node = (nc, nr)

                if not (0 <= nc <= cols and 0 <= nr <= rows):
                    continue
                if next_node in set(path):
                    continue

                edge_key = (min(node, next_node), max(node, next_node))
                if edge_key in breakpoints:
                    continue

                new_visited = visited_dots | ({next_node} & dots)
                new_path = path + [next_node]

                if next_node == end and new_visited == dots:
                    if _check_eraser_all(new_path, erasers, config, cols, rows):
                        return new_path

                new_state = (next_node, new_visited)
                if new_state not in seen:
                    seen.add(new_state)
                    queue.append((new_state, new_path))

        return None
    else:
        # DFS (like tw07)
        best_solution = [None]
        best_len = [(cols + 1) * (rows + 1) + 1]
        directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

        def dfs(path, path_set):
            if time.time() - t0 > timeout:
                return
            if len(path) >= best_len[0]:
                return
            node = path[-1]
            for dc, dr in directions:
                nc, nr = node[0] + dc, node[1] + dr
                next_node = (nc, nr)
                if not (0 <= nc <= cols and 0 <= nr <= rows):
                    continue
                if next_node in path_set:
                    continue
                edge_key = (min(node, next_node), max(node, next_node))
                if edge_key in breakpoints:
                    continue
                path.append(next_node)
                path_set.add(next_node)
                if next_node == end:
                    if _check_eraser_all(path, erasers, config, cols, rows):
                        if len(path) < best_len[0]:
                            best_len[0] = len(path)
                            best_solution[0] = list(path)
                else:
                    if len(path) < best_len[0] - 1:
                        dfs(path, path_set)
                path.pop()
                path_set.remove(next_node)

        dfs([start], {start})
        return best_solution[0]


# ====================================================================
# Baseline calibration
# ====================================================================

def calibrate_baseline(solution_path: List[Tuple[int, int]]) -> int:
    """Compute baseline_actions.

    baseline = ceil((moves + 1) * 1.2)
    where moves = len(path) - 1 (path steps), +1 for CONFIRM
    """
    moves = len(solution_path) - 1
    total_actions = moves + 1  # +1 for CONFIRM
    baseline = math.ceil(total_actions * 1.2)
    return baseline


def _get_starts(config: dict) -> list:
    """Extract start point list from config. Supports 'starts' (multiple) and 'start' (single)."""
    if "starts" in config:
        return [tuple(s) for s in config["starts"]]
    if "start" in config:
        return [tuple(config["start"])]
    return []


def validate_config(config: dict, game_type: str, timeout: float = 5.0) -> dict:
    """Validate a level_config, return validation result.

    Multi-start puzzles: try each start point in turn, return shortest solution.
    """
    solvers = {
        "tw01": solve_tw01,
        "tw02": solve_tw02,
        "tw03": solve_tw03,
        "tw04": solve_tw04,
        "tw05": solve_tw05,
        "tw06": solve_tw06,
        "tw07": solve_tw07,
        "tw08": solve_tw08,
        "tw11": solve_tw11,
        "tw12": solve_tw12,
        "tw13": solve_tw13,
    }

    solver = solvers.get(game_type)
    if not solver:
        return {"valid": False, "solution": None, "moves": 0, "baseline": 0,
                "error": f"Unknown game type: {game_type}"}

    # tw04 has its own start handling logic (blue_start/yellow_start), call directly
    if game_type == "tw04":
        try:
            solution = solver(config, timeout=timeout)
        except Exception as e:
            return {"valid": False, "solution": None, "moves": 0, "baseline": 0,
                    "error": str(e)}
        if solution is None:
            return {"valid": False, "solution": None, "moves": 0, "baseline": 0,
                    "error": "No solution found"}
        moves = len(solution) - 1
        return {"valid": True, "solution": solution, "moves": moves,
                "baseline": calibrate_baseline(solution), "error": None}

    # Non-tw04 games: check start points
    starts = _get_starts(config)
    if not starts:
        return {"valid": False, "solution": None, "moves": 0, "baseline": 0,
                "error": "No start point in config"}

    # Try solving independently for each start point
    best_solution = None
    last_error = "No solution found"
    per_start_timeout = timeout / len(starts) if len(starts) > 1 else timeout

    for start in starts:
        single_config = {**config, "start": list(start)}
        single_config.pop("starts", None)
        try:
            solution = solver(single_config, timeout=per_start_timeout)
        except Exception as e:
            last_error = str(e)
            continue
        if solution is not None:
            if best_solution is None or len(solution) < len(best_solution):
                best_solution = solution

    if best_solution is None:
        return {"valid": False, "solution": None, "moves": 0, "baseline": 0,
                "error": last_error}

    moves = len(best_solution) - 1
    return {
        "valid": True,
        "solution": best_solution,
        "moves": moves,
        "baseline": calibrate_baseline(best_solution),
        "error": None,
    }


def solution_to_actions(solution: List[Tuple[int, int]]) -> List[int]:
    """Convert path node sequence to action ID sequence.

    ACTION1=UP(dr=-1), ACTION2=DOWN(dr=+1), ACTION3=LEFT(dc=-1), ACTION4=RIGHT(dc=+1), ACTION5=CONFIRM
    """
    actions = []
    for i in range(1, len(solution)):
        pc, pr = solution[i - 1]
        nc, nr = solution[i]
        dc, dr = nc - pc, nr - pr
        if dr == -1:
            actions.append(1)  # UP
        elif dr == 1:
            actions.append(2)  # DOWN
        elif dc == -1:
            actions.append(3)  # LEFT
        elif dc == 1:
            actions.append(4)  # RIGHT
    actions.append(5)  # CONFIRM
    return actions
