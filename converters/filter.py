"""
filter.py — 按游戏类型筛选和过滤谜题

筛选条件：
- tw01 PathDots: hex-only, max(cols,rows)<=7, >=1 start, >=1 end, 仅节点 hex
- tw02 ColorSplit: sq-only, max(cols,rows)<=7, >=1 start, >=1 end, <=3 colors
- tw03 ShapeFill: tetris-only, max(cols,rows)<=6, >=1 start, >=1 end
- tw04 SymDraw: symmetry puzzles, max(cols,rows)<=7, >=1 start, >=1 end
- tw05 StarPair: stars-only, max(cols,rows)<=7, >=1 start, >=1 end, >=2 stars
- tw06 TriCount: triangles-only, max(cols,rows)<=7, >=1 start, >=1 end
- tw07 EraserLogic: eliminations + other constraint, max(cols,rows)<=6
- tw08 ComboBasic: squares + stars, max(cols,rows)<=7, <=3 colors
"""
from typing import List, Dict
from unified_puzzle import UnifiedPuzzle


def filter_tw01(puzzles: List[UnifiedPuzzle]) -> List[UnifiedPuzzle]:
    """筛选 tw01 PathDots 候选谜题。"""
    results = []
    for p in puzzles:
        if p.squares or p.stars or p.triangles or p.tetris or p.eliminations or p.symmetry:
            continue
        if max(p.cols, p.rows) > 7:
            continue
        if len(p.starts) < 1 or len(p.ends) < 1:
            continue
        if p.hex_edges:
            continue
        if not p.hexagons:
            continue
        results.append(p)
    return results


def filter_tw02(puzzles: List[UnifiedPuzzle]) -> List[UnifiedPuzzle]:
    """筛选 tw02 ColorSplit 候选谜题。"""
    results = []
    for p in puzzles:
        if p.classify() != "tw02":
            continue
        if max(p.cols, p.rows) > 7:
            continue
        if len(p.starts) < 1 or len(p.ends) < 1:
            continue
        if p.unique_square_colors() > 3:
            continue
        if len(p.squares) < 2:
            continue
        results.append(p)
    return results


def filter_tw03(puzzles: List[UnifiedPuzzle]) -> List[UnifiedPuzzle]:
    """筛选 tw03 ShapeFill 候选谜题。

    条件：仅有 tetris，max(cols,rows)<=6，1 start, >=1 end
    """
    results = []
    for p in puzzles:
        if p.classify() != "tw03":
            continue
        if max(p.cols, p.rows) > 6:
            continue
        if len(p.starts) < 1 or len(p.ends) < 1:
            continue
        results.append(p)
    return results


def filter_tw04(puzzles: List[UnifiedPuzzle]) -> List[UnifiedPuzzle]:
    """筛选 tw04 SymDraw 候选谜题。"""
    results = []
    for p in puzzles:
        if p.symmetry is None:
            continue
        if max(p.cols, p.rows) > 7:
            continue
        if len(p.starts) < 1 or len(p.ends) < 1:
            continue
        if p.squares or p.stars or p.triangles or p.tetris or p.eliminations:
            continue
        results.append(p)
    return results


def filter_tw05(puzzles: List[UnifiedPuzzle]) -> List[UnifiedPuzzle]:
    """筛选 tw05 StarPair 候选谜题。

    条件：仅有 stars，max(cols,rows)<=7，1 start, >=1 end, >=2 stars, no missing_edges
    """
    results = []
    for p in puzzles:
        if p.classify() != "tw05":
            continue
        if max(p.cols, p.rows) > 7:
            continue
        if len(p.starts) < 1 or len(p.ends) < 1:
            continue
        if len(p.stars) < 2:
            continue
        results.append(p)
    return results


def filter_tw06(puzzles: List[UnifiedPuzzle]) -> List[UnifiedPuzzle]:
    """筛选 tw06 TriCount 候选谜题。

    条件：仅有 triangles，max(cols,rows)<=7，1 start, >=1 end
    """
    results = []
    for p in puzzles:
        if p.classify() != "tw06":
            continue
        if max(p.cols, p.rows) > 7:
            continue
        if len(p.starts) < 1 or len(p.ends) < 1:
            continue
        results.append(p)
    return results


def filter_tw07(puzzles: List[UnifiedPuzzle]) -> List[UnifiedPuzzle]:
    """筛选 tw07 EraserLogic 候选谜题。

    条件：有 eliminations 且有至少一种其他约束，max(cols,rows)<=6
    """
    results = []
    for p in puzzles:
        if p.classify() != "tw07":
            continue
        if max(p.cols, p.rows) > 6:
            continue
        if len(p.starts) < 1 or len(p.ends) < 1:
            continue
        results.append(p)
    return results


def filter_tw08(puzzles: List[UnifiedPuzzle]) -> List[UnifiedPuzzle]:
    """筛选 tw08 ComboBasic 候选谜题。

    条件：同时有 squares AND stars，无其他约束，max(cols,rows)<=7, <=3 colors
    """
    results = []
    for p in puzzles:
        if p.classify() != "tw08":
            continue
        if max(p.cols, p.rows) > 7:
            continue
        if len(p.starts) < 1 or len(p.ends) < 1:
            continue
        if p.unique_square_colors() > 3:
            continue
        results.append(p)
    return results


def filter_tw11(puzzles: List[UnifiedPuzzle]) -> List[UnifiedPuzzle]:
    """筛选 tw11 MultiRegion 候选谜题。

    条件：2+ 区域约束同时满足，max(cols,rows)<=7（有 tetris 时<=6），
    >=1 start, >=1 end, <=3 色
    """
    results = []
    for p in puzzles:
        if p.classify() != "tw11":
            continue
        has_tetris = bool(p.tetris)
        max_dim = 6 if has_tetris else 7
        if max(p.cols, p.rows) > max_dim:
            continue
        if len(p.starts) < 1 or len(p.ends) < 1:
            continue
        if p.squares and p.unique_square_colors() > 3:
            continue
        results.append(p)
    return results


def filter_tw12(puzzles: List[UnifiedPuzzle]) -> List[UnifiedPuzzle]:
    """筛选 tw12 HexCombo 候选谜题。

    条件：hex + 至少一种区域约束，max(cols,rows)<=7（有 tetris 时<=6），
    无 hex_edges，有 hexagons，>=1 start, >=1 end, <=3 色
    """
    results = []
    for p in puzzles:
        if p.classify() != "tw12":
            continue
        has_tetris = bool(p.tetris)
        max_dim = 6 if has_tetris else 7
        if max(p.cols, p.rows) > max_dim:
            continue
        if len(p.starts) < 1 or len(p.ends) < 1:
            continue
        if p.hex_edges:
            continue
        if not p.hexagons:
            continue
        if p.squares and p.unique_square_colors() > 3:
            continue
        results.append(p)
    return results


def filter_tw13(puzzles: List[UnifiedPuzzle]) -> List[UnifiedPuzzle]:
    """筛选 tw13 EraserAll 候选谜题。

    条件：有 eliminations（tw07 未覆盖的组合），max(cols,rows)<=6，
    >=1 start, >=1 end, <=3 色
    """
    results = []
    for p in puzzles:
        if p.classify() != "tw13":
            continue
        if max(p.cols, p.rows) > 6:
            continue
        if len(p.starts) < 1 or len(p.ends) < 1:
            continue
        if p.squares and p.unique_square_colors() > 3:
            continue
        results.append(p)
    return results


def filter_all(puzzles: List[UnifiedPuzzle]) -> Dict[str, List[UnifiedPuzzle]]:
    """对所有谜题进行分类筛选。"""
    return {
        "tw01": filter_tw01(puzzles),
        "tw02": filter_tw02(puzzles),
        "tw03": filter_tw03(puzzles),
        "tw04": filter_tw04(puzzles),
        "tw05": filter_tw05(puzzles),
        "tw06": filter_tw06(puzzles),
        "tw07": filter_tw07(puzzles),
        "tw08": filter_tw08(puzzles),
        "tw11": filter_tw11(puzzles),
        "tw12": filter_tw12(puzzles),
        "tw13": filter_tw13(puzzles),
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
