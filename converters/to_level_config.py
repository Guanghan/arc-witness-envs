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


def _map_colors(squares: Dict[Tuple[int, int], str]) -> Dict[Tuple[int, int], int]:
    """将颜色名称映射为游戏颜色索引。"""
    # 收集所有出现的颜色，按首次出现顺序
    seen = []
    for cell in sorted(squares.keys()):
        c = squares[cell]
        if c not in seen:
            seen.append(c)

    if len(seen) > 3:
        return {}  # 超过 3 色，无法映射

    color_map = {c: _GAME_COLORS[i] for i, c in enumerate(seen)}
    return {cell: color_map[color] for cell, color in squares.items()}


def convert_tw01(puzzle: UnifiedPuzzle) -> Optional[dict]:
    """将 UnifiedPuzzle 转换为 tw01 PathDots level_config。

    格式: {cols, rows, start, end, dots, breakpoints?}
    """
    if len(puzzle.starts) != 1:
        return None
    if not puzzle.ends:
        return None

    start = puzzle.starts[0]
    # 如果多个终点，选择离起点最远的
    end = max(puzzle.ends, key=lambda e: abs(e[0] - start[0]) + abs(e[1] - start[1]))

    config = {
        "cols": puzzle.cols,
        "rows": puzzle.rows,
        "start": list(start),
        "end": list(end),
        "dots": [list(h) for h in puzzle.hexagons],
    }

    # 添加 breakpoints（missing edges → 不可通过的边）
    if puzzle.missing_edges:
        breakpoints = []
        for x, y, direction in puzzle.missing_edges:
            if direction == "v":
                # v_edges[y][x] 连接 node(x,y) 和 node(x+1,y)
                # 实际上 v_edge 是垂直方向的边，连接 node(x,y) 和 node(x,y+1)
                # 但在 ttws 中 v_edges[y][x] 是 row y, col x 的垂直边
                # 对应我们的边 (x,y)-(x+1,y)? 不对
                # ttws puzzle.py: v_edges 3 x 3 - w x h+1
                # 这意味着 v_edges[y][x] 连接 node(x,y) 和 node(x+1,y)
                # Wait, from puzzle.py diagram:
                # V Edges: +-V-+-V-+-V-+
                # v_edges: w x (h+1) -- w cols, h+1 rows
                # v_edge at [y][x] is horizontal position x, at row y
                # It connects node(x,y) to node(x+1,y)? No...
                # Looking at the diagram more carefully:
                # +---+---+---+    n-v-n-v-n-v-n
                # v_edges are between nodes horizontally
                # Actually v_edges seem to be the horizontal connections between nodes
                # Wait, the name is confusing. Let me re-read:
                # Storage layout: n-v-n-v-n-v-n
                #                 h c h c h c h
                # v = v-edge (connecting two nodes on the same row)
                # h = h-edge (connecting two nodes in the same column)
                # So v_edges[y][x] connects node(x,y) and node(x+1,y) - HORIZONTAL edge
                # And h_edges[y][x] connects node(x,y) and node(x,y+1) - VERTICAL edge
                # This is counterintuitive naming!
                n1 = (x, y)
                n2 = (x + 1, y)
            else:  # "h"
                n1 = (x, y)
                n2 = (x, y + 1)
            breakpoints.append([list(n1), list(n2)])
        config["breakpoints"] = breakpoints

    return config


def convert_tw02(puzzle: UnifiedPuzzle) -> Optional[dict]:
    """将 UnifiedPuzzle 转换为 tw02 ColorSplit level_config。

    格式: {cols, rows, start, end, squares}
    """
    if len(puzzle.starts) != 1:
        return None
    if not puzzle.ends:
        return None

    start = puzzle.starts[0]
    end = max(puzzle.ends, key=lambda e: abs(e[0] - start[0]) + abs(e[1] - start[1]))

    mapped_colors = _map_colors(puzzle.squares)
    if not mapped_colors:
        return None

    config = {
        "cols": puzzle.cols,
        "rows": puzzle.rows,
        "start": list(start),
        "end": list(end),
        "squares": {f"{c},{r}": v for (c, r), v in mapped_colors.items()},
    }
    return config


def convert_tw04(puzzle: UnifiedPuzzle) -> Optional[dict]:
    """将 UnifiedPuzzle 转换为 tw04 SymDraw level_config。

    需要确定 blue/yellow 的 start/end 对。
    对称性决定了如何配对起点和终点。
    """
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

    # 配对起点：选择一个起点作为 blue_start，其镜像为 yellow_start
    blue_start = None
    yellow_start = None

    starts = list(puzzle.starts)
    if len(starts) == 2:
        # 检查两个起点是否互为镜像
        s0, s1 = starts
        if mirror(s0) == s1:
            blue_start, yellow_start = s0, s1
        elif mirror(s1) == s0:
            blue_start, yellow_start = s1, s0
    elif len(starts) == 1:
        # 单起点 — 另一个是其镜像
        blue_start = starts[0]
        yellow_start = mirror(blue_start)
        if blue_start == yellow_start:
            return None  # 自对称起点，不适合双线

    if blue_start is None:
        # 尝试从多个起点中找配对
        for s in starts:
            m = mirror(s)
            if m in starts and m != s:
                blue_start = s
                yellow_start = m
                break

    if blue_start is None:
        return None

    # 配对终点
    blue_end = None
    yellow_end = None

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
                blue_end = e
                yellow_end = m
                break

    if blue_end is None:
        return None

    # 确保 blue 在"左半/上半"（约定）
    if sym == "horizontal" and blue_start[0] > cols // 2:
        blue_start, yellow_start = yellow_start, blue_start
        blue_end, yellow_end = yellow_end, blue_end
    elif sym == "vertical" and blue_start[1] > rows // 2:
        blue_start, yellow_start = yellow_start, blue_start
        blue_end, yellow_end = yellow_end, blue_end

    # 分配 hexagons 到 blue/yellow dots
    blue_dots = []
    yellow_dots = []
    for h in puzzle.hexagons:
        m = mirror(h)
        if h != m:
            # 把靠近 blue_start 的分给 blue
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
        # Skip self-symmetric hexagons (both paths must cross, complex)

    config = {
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
    return config


def convert_puzzle(puzzle: UnifiedPuzzle, game_type: str) -> Optional[dict]:
    """根据游戏类型转换谜题。"""
    converters = {
        "tw01": convert_tw01,
        "tw02": convert_tw02,
        "tw04": convert_tw04,
    }
    converter = converters.get(game_type)
    if not converter:
        return None
    return converter(puzzle)
