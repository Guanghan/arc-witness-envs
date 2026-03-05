"""
unified_puzzle.py — 统一谜题中间表示

从 ttws protobuf 数据转换为统一格式，再转换为游戏 level_config。
"""
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Set


@dataclass
class UnifiedPuzzle:
    """统一谜题表示，与具体数据源无关。"""
    # 网格尺寸（单元格数）
    cols: int
    rows: int

    # 起点和终点（节点坐标）
    starts: List[Tuple[int, int]] = field(default_factory=list)
    ends: List[Tuple[int, int]] = field(default_factory=list)

    # 约束类型
    hexagons: List[Tuple[int, int]] = field(default_factory=list)        # 节点必经点
    hex_edges: List[Tuple[int, int, str]] = field(default_factory=list)  # 边上必经点: (x, y, 'h'|'v')
    squares: Dict[Tuple[int, int], str] = field(default_factory=dict)    # 彩色方块 cell->(color_name)
    stars: Dict[Tuple[int, int], str] = field(default_factory=dict)      # 星星 cell->(color_name)
    triangles: Dict[Tuple[int, int], int] = field(default_factory=dict)  # 三角形 cell->(count)
    tetris: Dict[Tuple[int, int], dict] = field(default_factory=dict)    # 多联骨牌
    eliminations: List[Tuple[int, int]] = field(default_factory=list)    # 消除符号

    # 对称性
    symmetry: Optional[str] = None  # None, "horizontal", "vertical", "rotational"

    # 断开的边
    missing_edges: List[Tuple[int, int, str]] = field(default_factory=list)  # (x, y, 'h'|'v')

    # 元数据
    source: str = ""  # 来源标识
    source_index: int = 0  # 在源文件中的索引

    def classify(self) -> str:
        """分类谜题类型，返回最匹配的游戏标识。

        优先级：tw07 (elim+other) > tw08 (sq+star) > tw01 (hex) > tw02 (sq) >
                tw04 (sym) > tw05 (star) > tw06 (tri) > tw03 (tetris) > other
        """
        has_hex = bool(self.hexagons or self.hex_edges)
        has_sq = bool(self.squares)
        has_star = bool(self.stars)
        has_tri = bool(self.triangles)
        has_tetris = bool(self.tetris)
        has_elim = bool(self.eliminations)
        has_sym = self.symmetry is not None

        # tw07: 消除符号 + 至少一种其他约束
        if has_elim and (has_sq or has_star or has_tri):
            return "tw07"

        # tw08: 方块 + 星星组合（无其他约束）
        if has_sq and has_star and not has_hex and not has_tri and not has_tetris and not has_elim and not has_sym:
            return "tw08"

        # tw01: 仅有 hexagon 约束（节点必经点）
        if has_hex and not has_sq and not has_star and not has_tri and not has_tetris and not has_elim and not has_sym:
            return "tw01"

        # tw02: 仅有 square 约束（彩色方块分隔）
        if has_sq and not has_hex and not has_star and not has_tri and not has_tetris and not has_elim and not has_sym:
            return "tw02"

        # tw04: 对称性谜题
        if has_sym:
            return "tw04"

        # tw05: 仅有星星
        if has_star and not has_sq and not has_hex and not has_tri and not has_tetris and not has_elim:
            return "tw05"

        # tw06: 仅有三角形
        if has_tri and not has_sq and not has_hex and not has_star and not has_tetris and not has_elim:
            return "tw06"

        # tw03: 仅有多联骨牌
        if has_tetris and not has_sq and not has_hex and not has_star and not has_tri and not has_elim:
            return "tw03"

        return "other"

    def feature_set(self) -> Set[str]:
        """返回谜题包含的特征集合。"""
        features = set()
        if self.hexagons or self.hex_edges:
            features.add("hex")
        if self.squares:
            features.add("squares")
        if self.stars:
            features.add("stars")
        if self.triangles:
            features.add("triangles")
        if self.tetris:
            features.add("tetris")
        if self.eliminations:
            features.add("eliminations")
        if self.symmetry:
            features.add(f"sym_{self.symmetry}")
        if self.missing_edges:
            features.add("missing_edges")
        return features

    def unique_square_colors(self) -> int:
        """方块使用的颜色数量。"""
        return len(set(self.squares.values()))
