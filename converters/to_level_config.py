"""
to_level_config.py — 将 UnifiedPuzzle 转换为游戏 level_config 格式

坐标系说明：
- ttws/Windmill: nodes[y][x]，y 从上到下，x 从左到右
- 我们的游戏: node (col, row)，col=x, row=y，左上原点
- 两者一致，无需翻转

颜色映射：
- Witness 9 色 → 我们 3 色 palette (SQUARE_A/B/C)
"""
import sys
import os
from typing import List, Dict, Tuple, Optional

# 添加项目根目录到路径
_here = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_here)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from unified_puzzle import UnifiedPuzzle

# === 颜色映射 ===
# witness_grid.py 中的颜色常量
SQUARE_A = 6   # COLOR_MAGENTA
SQUARE_B = 10  # COLOR_LIGHT_BLUE
SQUARE_C = 12  # COLOR_ORANGE

# Witness 颜色名称 → 我们的颜色索引
# 使用稳定映射：按首次出现顺序分配 A/B/C
_GAME_COLORS = [SQUARE_A, SQUARE_B, SQUARE_C]


def _map_colors(color_dict: Dict[Tuple[int, int], str]) -> Dict[Tuple[int, int], int]:
    """将颜色名称映射为游戏颜色索引。"""
    # 收集所有出现的颜色，按首次出现顺序
    seen = []
    for cell in sorted(color_dict.keys()):
        c = color_dict[cell]
        if c not in seen:
            seen.append(c)

    if len(seen) > 3:
        return {}  # 超过 3 色，无法映射

    color_map = {c: _GAME_COLORS[i] for i, c in enumerate(seen)}
    return {cell: color_map[color] for cell, color in color_dict.items()}


def _pick_end(puzzle: UnifiedPuzzle) -> Tuple[int, int]:
    """选择距起点（组）最远的终点。多起点时用起点质心。"""
    starts = puzzle.starts
    cx = sum(s[0] for s in starts) / len(starts)
    cy = sum(s[1] for s in starts) / len(starts)
    return max(puzzle.ends, key=lambda e: abs(e[0] - cx) + abs(e[1] - cy))


def _start_fields(puzzle: UnifiedPuzzle) -> dict:
    """生成 start/starts 字段。单起点用 'start'，多起点用 'starts'。"""
    if len(puzzle.starts) == 1:
        return {"start": list(puzzle.starts[0])}
    return {"starts": [list(s) for s in puzzle.starts]}


def convert_tw01(puzzle: UnifiedPuzzle) -> Optional[dict]:
    """将 UnifiedPuzzle 转换为 tw01 PathDots level_config。"""
    if len(puzzle.starts) < 1 or not puzzle.ends:
        return None

    end = _pick_end(puzzle)

    config = {
        "cols": puzzle.cols,
        "rows": puzzle.rows,
        **_start_fields(puzzle),
        "end": list(end),
        "dots": [list(h) for h in puzzle.hexagons],
    }

    if puzzle.missing_edges:
        breakpoints = []
        for x, y, direction in puzzle.missing_edges:
            if direction == "v":
                n1 = (x, y)
                n2 = (x + 1, y)
            else:  # "h"
                n1 = (x, y)
                n2 = (x, y + 1)
            breakpoints.append([list(n1), list(n2)])
        config["breakpoints"] = breakpoints

    return config


def convert_tw02(puzzle: UnifiedPuzzle) -> Optional[dict]:
    """将 UnifiedPuzzle 转换为 tw02 ColorSplit level_config。"""
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
    }


def convert_tw03(puzzle: UnifiedPuzzle) -> Optional[dict]:
    """将 UnifiedPuzzle 转换为 tw03 ShapeFill level_config。

    格式: {cols, rows, start(s), end, tetris: {"c,r": {shape, rotated, negative}}}
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
    }


def convert_tw04(puzzle: UnifiedPuzzle) -> Optional[dict]:
    """将 UnifiedPuzzle 转换为 tw04 SymDraw level_config。"""
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

    # 配对起点
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

    # 配对终点
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

    # 确保 blue 在"左半/上半"
    if sym == "horizontal" and blue_start[0] > cols // 2:
        blue_start, yellow_start = yellow_start, blue_start
        blue_end, yellow_end = yellow_end, blue_end
    elif sym == "vertical" and blue_start[1] > rows // 2:
        blue_start, yellow_start = yellow_start, blue_start
        blue_end, yellow_end = yellow_end, blue_end

    # 分配 hexagons
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
    }


def convert_tw05(puzzle: UnifiedPuzzle) -> Optional[dict]:
    """将 UnifiedPuzzle 转换为 tw05 StarPair level_config。

    格式: {cols, rows, start(s), end, stars: {"c,r": color_index}}
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
    }


def convert_tw06(puzzle: UnifiedPuzzle) -> Optional[dict]:
    """将 UnifiedPuzzle 转换为 tw06 TriCount level_config。

    格式: {cols, rows, start(s), end, triangles: {"c,r": count}}
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
    }


def convert_tw07(puzzle: UnifiedPuzzle) -> Optional[dict]:
    """将 UnifiedPuzzle 转换为 tw07 EraserLogic level_config。

    格式: {cols, rows, start(s), end, erasers: [[c,r],...], + squares/stars/triangles}
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
    }

    # 添加方块约束
    if puzzle.squares:
        mapped = _map_colors(puzzle.squares)
        if mapped:
            config["squares"] = {f"{c},{r}": v for (c, r), v in mapped.items()}

    # 添加星星约束
    if puzzle.stars:
        mapped = _map_colors(puzzle.stars)
        if mapped:
            config["stars"] = {f"{c},{r}": v for (c, r), v in mapped.items()}

    # 添加三角形约束
    if puzzle.triangles:
        config["triangles"] = {f"{c},{r}": v for (c, r), v in puzzle.triangles.items()}

    return config


def convert_tw08(puzzle: UnifiedPuzzle) -> Optional[dict]:
    """将 UnifiedPuzzle 转换为 tw08 ComboBasic level_config。

    格式: {cols, rows, start(s), end, squares: {...}, stars: {...}}
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
    }


def convert_puzzle(puzzle: UnifiedPuzzle, game_type: str) -> Optional[dict]:
    """根据游戏类型转换谜题。"""
    converters = {
        "tw01": convert_tw01,
        "tw02": convert_tw02,
        "tw03": convert_tw03,
        "tw04": convert_tw04,
        "tw05": convert_tw05,
        "tw06": convert_tw06,
        "tw07": convert_tw07,
        "tw08": convert_tw08,
    }
    converter = converters.get(game_type)
    if not converter:
        return None
    return converter(puzzle)
