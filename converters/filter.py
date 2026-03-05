"""
filter.py — 按游戏类型筛选和过滤谜题

筛选条件：
- tw01 PathDots: hex-only, max(cols,rows)<=7, 1 start, 1 end, 仅节点 hex（不含边 hex）
- tw02 ColorSplit: sq-only, max(cols,rows)<=7, 1 start, 1 end, <=3 colors
- tw04 SymDraw: symmetry puzzles, max(cols,rows)<=7, >=1 start, >=1 end
"""
from typing import List, Dict
from unified_puzzle import UnifiedPuzzle


def filter_tw01(puzzles: List[UnifiedPuzzle]) -> List[UnifiedPuzzle]:
    """筛选 tw01 PathDots 候选谜题。

    条件：
    - 仅有 node hexagons（节点必经点），不含边上的 hexagon
    - 无 squares, stars, triangles, tetris, eliminations, symmetry
    - max(cols, rows) <= 7
    - 恰好 1 个起点和至少 1 个终点
    - 至少有 1 个 hexagon
    """
    results = []
    for p in puzzles:
        # 基本特征检查：仅有 hex（和 missing edges）
        if p.squares or p.stars or p.triangles or p.tetris or p.eliminations or p.symmetry:
            continue
        if max(p.cols, p.rows) > 7:
            continue
        if len(p.starts) != 1 or len(p.ends) < 1:
            continue
        # 仅接受节点 hex，不接受边 hex（我们的游戏只支持节点 dots）
        if p.hex_edges:
            continue
        if not p.hexagons:
            continue
        # 允许 missing edges（映射为 breakpoints）
        results.append(p)
    return results


def filter_tw02(puzzles: List[UnifiedPuzzle]) -> List[UnifiedPuzzle]:
    """筛选 tw02 ColorSplit 候选谜题。

    条件：
    - 仅有 squares（彩色方块），无其他约束
    - max(cols, rows) <= 7
    - 恰好 1 个起点和至少 1 个终点
    - 使用 <= 3 种颜色
    - 至少有 2 个 squares
    """
    results = []
    for p in puzzles:
        if p.classify() != "tw02":
            continue
        if max(p.cols, p.rows) > 7:
            continue
        if len(p.starts) != 1 or len(p.ends) < 1:
            continue
        if p.unique_square_colors() > 3:
            continue
        if len(p.squares) < 2:
            continue
        if p.missing_edges:
            continue
        results.append(p)
    return results


def filter_tw04(puzzles: List[UnifiedPuzzle]) -> List[UnifiedPuzzle]:
    """筛选 tw04 SymDraw 候选谜题。

    条件：
    - 有 symmetry
    - max(cols, rows) <= 7
    - 有起点和终点
    - 可以有 hexagons（作为 dots）
    - 不含 squares, stars, triangles, tetris, eliminations（简化）
    """
    results = []
    for p in puzzles:
        if p.symmetry is None:
            continue
        if max(p.cols, p.rows) > 7:
            continue
        if len(p.starts) < 1 or len(p.ends) < 1:
            continue
        # 只接受 hex+sym 或纯 sym 的简单谜题
        if p.squares or p.stars or p.triangles or p.tetris or p.eliminations:
            continue
        results.append(p)
    return results


def filter_all(puzzles: List[UnifiedPuzzle]) -> Dict[str, List[UnifiedPuzzle]]:
    """对所有谜题进行分类筛选。"""
    return {
        "tw01": filter_tw01(puzzles),
        "tw02": filter_tw02(puzzles),
        "tw04": filter_tw04(puzzles),
    }


if __name__ == "__main__":
    from ingest_ttws import ingest_all

    puzzles = ingest_all()
    filtered = filter_all(puzzles)

    for game, ps in filtered.items():
        print(f"\n{game}: {len(ps)} candidates")
        from collections import Counter
        sizes = Counter((p.cols, p.rows) for p in ps)
        for (c, r), n in sorted(sizes.items()):
            print(f"  {c}x{r}: {n}")
