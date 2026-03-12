"""
to_level_config.py — Convert UnifiedPuzzle to game level_config format

Coordinate system notes:
- ttws/Windmill: nodes[y][x], y top-to-bottom, x left-to-right
- Our game: node (col, row), col=x, row=y, origin at top-left
- Both are consistent, no flipping needed

Color mapping:
- Witness 9 colors -> our 3-color palette (SQUARE_A/B/C)
"""
import sys
import os
from typing import List, Dict, Tuple, Optional

# Add project root to path
_here = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_here)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from unified_puzzle import UnifiedPuzzle

# === Color mapping ===
# Color constants from witness_grid.py
SQUARE_A = 6   # COLOR_MAGENTA
SQUARE_B = 10  # COLOR_LIGHT_BLUE
SQUARE_C = 12  # COLOR_ORANGE

# Witness color names -> our color indices
# Stable mapping: assign A/B/C by order of first appearance
_GAME_COLORS = [SQUARE_A, SQUARE_B, SQUARE_C]


def _map_colors(color_dict: Dict[Tuple[int, int], str]) -> Dict[Tuple[int, int], int]:
    """Map color names to game color indices."""
    # Collect all colors in order of first appearance
    seen = []
    for cell in sorted(color_dict.keys()):
        c = color_dict[cell]
        if c not in seen:
            seen.append(c)

    if len(seen) > 3:
        return {}  # More than 3 colors, cannot map

    color_map = {c: _GAME_COLORS[i] for i, c in enumerate(seen)}
    return {cell: color_map[color] for cell, color in color_dict.items()}


def _pick_end(puzzle: UnifiedPuzzle) -> Tuple[int, int]:
    """Pick the endpoint farthest from the start(s). Uses centroid for multiple starts."""
    starts = puzzle.starts
    cx = sum(s[0] for s in starts) / len(starts)
    cy = sum(s[1] for s in starts) / len(starts)
    return max(puzzle.ends, key=lambda e: abs(e[0] - cx) + abs(e[1] - cy))


def _start_fields(puzzle: UnifiedPuzzle) -> dict:
    """Generate start/starts fields. Use 'start' for single, 'starts' for multiple."""
    if len(puzzle.starts) == 1:
        return {"start": list(puzzle.starts[0])}
    return {"starts": [list(s) for s in puzzle.starts]}


def _breakpoint_fields(puzzle: UnifiedPuzzle) -> dict:
    """Generate breakpoints field. Returns empty dict if no missing_edges."""
    if not puzzle.missing_edges:
        return {}
    breakpoints = []
    for x, y, direction in puzzle.missing_edges:
        if direction == "v":
            n1 = (x, y)
            n2 = (x + 1, y)
        else:  # "h"
            n1 = (x, y)
            n2 = (x, y + 1)
        breakpoints.append([list(n1), list(n2)])
    return {"breakpoints": breakpoints}


def convert_tw01(puzzle: UnifiedPuzzle) -> Optional[dict]:
    """Convert UnifiedPuzzle to tw01 PathDots level_config."""
    if len(puzzle.starts) < 1 or not puzzle.ends:
        return None

    end = _pick_end(puzzle)

    return {
        "cols": puzzle.cols,
        "rows": puzzle.rows,
        **_start_fields(puzzle),
        "end": list(end),
        "dots": [list(h) for h in puzzle.hexagons],
        **_breakpoint_fields(puzzle),
    }


def convert_tw02(puzzle: UnifiedPuzzle) -> Optional[dict]:
    """Convert UnifiedPuzzle to tw02 ColorSplit level_config."""
    if len(puzzle.starts) < 1 or not puzzle.ends:
        return None

    end = _pick_end(puzzle)

    mapped_colors = _map_colors(puzzle.squares)
    if not mapped_colors:
        return None

    return {
        "cols": puzzle.cols,
        "rows": puzzle.rows,
        **_start_fields(puzzle),
        "end": list(end),
        "squares": {f"{c},{r}": v for (c, r), v in mapped_colors.items()},
        **_breakpoint_fields(puzzle),
    }


def convert_tw03(puzzle: UnifiedPuzzle) -> Optional[dict]:
    """Convert UnifiedPuzzle to tw03 ShapeFill level_config.

    Format: {cols, rows, start(s), end, tetris: {"c,r": {shape, rotated, negative}}}
    """
    if len(puzzle.starts) < 1 or not puzzle.ends:
        return None

    end = _pick_end(puzzle)

    tetris = {}
    for (c, r), t in puzzle.tetris.items():
        tetris[f"{c},{r}"] = {
            "shape": t["shape"],
            "rotated": t.get("rotated", False),
            "negative": t.get("negative", False),
        }

    return {
        "cols": puzzle.cols,
        "rows": puzzle.rows,
        **_start_fields(puzzle),
        "end": list(end),
        "tetris": tetris,
        **_breakpoint_fields(puzzle),
    }


def convert_tw04(puzzle: UnifiedPuzzle) -> Optional[dict]:
    """Convert UnifiedPuzzle to tw04 SymDraw level_config."""
    if not puzzle.symmetry:
        return None
    if len(puzzle.starts) < 1 or len(puzzle.ends) < 1:
        return None

    cols, rows = puzzle.cols, puzzle.rows
    sym = puzzle.symmetry

    def mirror(node):
        x, y = node
        if sym == "horizontal":
            return (cols - x, y)
        elif sym == "vertical":
            return (x, rows - y)
        elif sym == "rotational":
            return (cols - x, rows - y)
        return node

    # Pair start points
    blue_start = yellow_start = None
    starts = list(puzzle.starts)
    if len(starts) == 2:
        s0, s1 = starts
        if mirror(s0) == s1:
            blue_start, yellow_start = s0, s1
        elif mirror(s1) == s0:
            blue_start, yellow_start = s1, s0
    elif len(starts) == 1:
        blue_start = starts[0]
        yellow_start = mirror(blue_start)
        if blue_start == yellow_start:
            return None

    if blue_start is None:
        for s in starts:
            m = mirror(s)
            if m in starts and m != s:
                blue_start, yellow_start = s, m
                break

    if blue_start is None:
        return None

    # Pair end points
    blue_end = yellow_end = None
    ends = list(puzzle.ends)
    if len(ends) == 2:
        e0, e1 = ends
        if mirror(e0) == e1:
            blue_end, yellow_end = e0, e1
        elif mirror(e1) == e0:
            blue_end, yellow_end = e1, e0
    elif len(ends) == 1:
        blue_end = ends[0]
        yellow_end = mirror(blue_end)
        if blue_end == yellow_end:
            return None

    if blue_end is None:
        for e in ends:
            m = mirror(e)
            if m in ends and m != e:
                blue_end, yellow_end = e, m
                break

    if blue_end is None:
        return None

    # Ensure blue is on the left/top half
    if sym == "horizontal" and blue_start[0] > cols // 2:
        blue_start, yellow_start = yellow_start, blue_start
        blue_end, yellow_end = yellow_end, blue_end
    elif sym == "vertical" and blue_start[1] > rows // 2:
        blue_start, yellow_start = yellow_start, blue_start
        blue_end, yellow_end = yellow_end, blue_end

    # Assign hexagons
    blue_dots, yellow_dots = [], []
    for h in puzzle.hexagons:
        m = mirror(h)
        if h != m:
            d_blue = abs(h[0] - blue_start[0]) + abs(h[1] - blue_start[1])
            d_yellow = abs(h[0] - yellow_start[0]) + abs(h[1] - yellow_start[1])
            if d_blue <= d_yellow:
                if h not in blue_dots:
                    blue_dots.append(h)
                if m not in yellow_dots:
                    yellow_dots.append(m)
            else:
                if h not in yellow_dots:
                    yellow_dots.append(h)
                if m not in blue_dots:
                    blue_dots.append(m)

    return {
        "cols": cols,
        "rows": rows,
        "symmetry": sym,
        "blue_start": list(blue_start),
        "blue_end": list(blue_end),
        "yellow_start": list(yellow_start),
        "yellow_end": list(yellow_end),
        "blue_dots": [list(d) for d in blue_dots],
        "yellow_dots": [list(d) for d in yellow_dots],
        **_breakpoint_fields(puzzle),
    }


def convert_tw05(puzzle: UnifiedPuzzle) -> Optional[dict]:
    """Convert UnifiedPuzzle to tw05 StarPair level_config.

    Format: {cols, rows, start(s), end, stars: {"c,r": color_index}}
    """
    if len(puzzle.starts) < 1 or not puzzle.ends:
        return None

    end = _pick_end(puzzle)

    mapped_colors = _map_colors(puzzle.stars)
    if not mapped_colors:
        return None

    return {
        "cols": puzzle.cols,
        "rows": puzzle.rows,
        **_start_fields(puzzle),
        "end": list(end),
        "stars": {f"{c},{r}": v for (c, r), v in mapped_colors.items()},
        **_breakpoint_fields(puzzle),
    }


def convert_tw06(puzzle: UnifiedPuzzle) -> Optional[dict]:
    """Convert UnifiedPuzzle to tw06 TriCount level_config.

    Format: {cols, rows, start(s), end, triangles: {"c,r": count}}
    """
    if len(puzzle.starts) < 1 or not puzzle.ends:
        return None

    end = _pick_end(puzzle)

    return {
        "cols": puzzle.cols,
        "rows": puzzle.rows,
        **_start_fields(puzzle),
        "end": list(end),
        "triangles": {f"{c},{r}": v for (c, r), v in puzzle.triangles.items()},
        **_breakpoint_fields(puzzle),
    }


def convert_tw07(puzzle: UnifiedPuzzle) -> Optional[dict]:
    """Convert UnifiedPuzzle to tw07 EraserLogic level_config.

    Format: {cols, rows, start(s), end, erasers: [[c,r],...], + squares/stars/triangles}
    """
    if len(puzzle.starts) < 1 or not puzzle.ends:
        return None

    end = _pick_end(puzzle)

    config = {
        "cols": puzzle.cols,
        "rows": puzzle.rows,
        **_start_fields(puzzle),
        "end": list(end),
        "erasers": [list(e) for e in puzzle.eliminations],
        **_breakpoint_fields(puzzle),
    }

    # Add square constraints
    if puzzle.squares:
        mapped = _map_colors(puzzle.squares)
        if mapped:
            config["squares"] = {f"{c},{r}": v for (c, r), v in mapped.items()}

    # Add star constraints
    if puzzle.stars:
        mapped = _map_colors(puzzle.stars)
        if mapped:
            config["stars"] = {f"{c},{r}": v for (c, r), v in mapped.items()}

    # Add triangle constraints
    if puzzle.triangles:
        config["triangles"] = {f"{c},{r}": v for (c, r), v in puzzle.triangles.items()}

    return config


def convert_tw08(puzzle: UnifiedPuzzle) -> Optional[dict]:
    """Convert UnifiedPuzzle to tw08 ComboBasic level_config.

    Format: {cols, rows, start(s), end, squares: {...}, stars: {...}}
    """
    if len(puzzle.starts) < 1 or not puzzle.ends:
        return None

    end = _pick_end(puzzle)

    mapped_sq = _map_colors(puzzle.squares)
    if not mapped_sq:
        return None

    mapped_st = _map_colors(puzzle.stars)
    if not mapped_st:
        return None

    return {
        "cols": puzzle.cols,
        "rows": puzzle.rows,
        **_start_fields(puzzle),
        "end": list(end),
        "squares": {f"{c},{r}": v for (c, r), v in mapped_sq.items()},
        "stars": {f"{c},{r}": v for (c, r), v in mapped_st.items()},
        **_breakpoint_fields(puzzle),
    }


def convert_tw11(puzzle: UnifiedPuzzle) -> Optional[dict]:
    """Convert UnifiedPuzzle to tw11 MultiRegion level_config.

    Format: {cols, rows, start(s), end, + squares/stars/triangles/tetris (at least 2 types)}
    """
    if len(puzzle.starts) < 1 or not puzzle.ends:
        return None

    end = _pick_end(puzzle)

    # Need at least 2 types of region constraints
    constraint_count = sum([
        bool(puzzle.squares), bool(puzzle.stars),
        bool(puzzle.triangles), bool(puzzle.tetris),
    ])
    if constraint_count < 2:
        return None

    config = {
        "cols": puzzle.cols,
        "rows": puzzle.rows,
        **_start_fields(puzzle),
        "end": list(end),
        **_breakpoint_fields(puzzle),
    }

    if puzzle.squares:
        mapped = _map_colors(puzzle.squares)
        if not mapped:
            return None
        config["squares"] = {f"{c},{r}": v for (c, r), v in mapped.items()}

    if puzzle.stars:
        mapped = _map_colors(puzzle.stars)
        if not mapped:
            return None
        config["stars"] = {f"{c},{r}": v for (c, r), v in mapped.items()}

    if puzzle.triangles:
        config["triangles"] = {f"{c},{r}": v for (c, r), v in puzzle.triangles.items()}

    if puzzle.tetris:
        tetris = {}
        for (c, r), t in puzzle.tetris.items():
            tetris[f"{c},{r}"] = {
                "shape": t["shape"],
                "rotated": t.get("rotated", False),
                "negative": t.get("negative", False),
            }
        config["tetris"] = tetris

    return config


def convert_tw12(puzzle: UnifiedPuzzle) -> Optional[dict]:
    """Convert UnifiedPuzzle to tw12 HexCombo level_config.

    Format: {cols, rows, start(s), end, dots: [...], + squares/stars/triangles/tetris}
    Requires: hex + >=1 region constraint
    """
    if len(puzzle.starts) < 1 or not puzzle.ends:
        return None

    if not puzzle.hexagons:
        return None

    has_region = bool(puzzle.squares or puzzle.stars or puzzle.triangles or puzzle.tetris)
    if not has_region:
        return None

    end = _pick_end(puzzle)

    config = {
        "cols": puzzle.cols,
        "rows": puzzle.rows,
        **_start_fields(puzzle),
        "end": list(end),
        "dots": [list(h) for h in puzzle.hexagons],
        **_breakpoint_fields(puzzle),
    }

    if puzzle.squares:
        mapped = _map_colors(puzzle.squares)
        if not mapped:
            return None
        config["squares"] = {f"{c},{r}": v for (c, r), v in mapped.items()}

    if puzzle.stars:
        mapped = _map_colors(puzzle.stars)
        if not mapped:
            return None
        config["stars"] = {f"{c},{r}": v for (c, r), v in mapped.items()}

    if puzzle.triangles:
        config["triangles"] = {f"{c},{r}": v for (c, r), v in puzzle.triangles.items()}

    if puzzle.tetris:
        tetris = {}
        for (c, r), t in puzzle.tetris.items():
            tetris[f"{c},{r}"] = {
                "shape": t["shape"],
                "rotated": t.get("rotated", False),
                "negative": t.get("negative", False),
            }
        config["tetris"] = tetris

    return config


def convert_tw13(puzzle: UnifiedPuzzle) -> Optional[dict]:
    """Convert UnifiedPuzzle to tw13 EraserAll level_config.

    Format: {cols, rows, start(s), end, erasers: [...], + all present constraints + optional dots}
    Extends tw07, covering elim + tetris, elim + hex, and other combinations
    """
    if len(puzzle.starts) < 1 or not puzzle.ends:
        return None

    end = _pick_end(puzzle)

    config = {
        "cols": puzzle.cols,
        "rows": puzzle.rows,
        **_start_fields(puzzle),
        "end": list(end),
        "erasers": [list(e) for e in puzzle.eliminations],
        **_breakpoint_fields(puzzle),
    }

    if puzzle.squares:
        mapped = _map_colors(puzzle.squares)
        if mapped:
            config["squares"] = {f"{c},{r}": v for (c, r), v in mapped.items()}

    if puzzle.stars:
        mapped = _map_colors(puzzle.stars)
        if mapped:
            config["stars"] = {f"{c},{r}": v for (c, r), v in mapped.items()}

    if puzzle.triangles:
        config["triangles"] = {f"{c},{r}": v for (c, r), v in puzzle.triangles.items()}

    if puzzle.tetris:
        tetris = {}
        for (c, r), t in puzzle.tetris.items():
            tetris[f"{c},{r}"] = {
                "shape": t["shape"],
                "rotated": t.get("rotated", False),
                "negative": t.get("negative", False),
            }
        config["tetris"] = tetris

    if puzzle.hexagons:
        config["dots"] = [list(h) for h in puzzle.hexagons]

    return config


def convert_puzzle(puzzle: UnifiedPuzzle, game_type: str) -> Optional[dict]:
    """Convert puzzle based on game type."""
    converters = {
        "tw01": convert_tw01,
        "tw02": convert_tw02,
        "tw03": convert_tw03,
        "tw04": convert_tw04,
        "tw05": convert_tw05,
        "tw06": convert_tw06,
        "tw07": convert_tw07,
        "tw08": convert_tw08,
        "tw11": convert_tw11,
        "tw12": convert_tw12,
        "tw13": convert_tw13,
    }
    converter = converters.get(game_type)
    if not converter:
        return None
    return converter(puzzle)
