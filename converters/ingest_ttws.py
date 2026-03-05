"""
ingest_ttws.py — 从 ttws protobuf 编码解码谜题，转换为 UnifiedPuzzle

兼容 Python 3。修复了原始 loader.py 的 Py2 整除和 base64 问题。
"""
import sys
import os
import base64
from typing import List, Tuple, Optional

# 将 vendor_ttws 加入路径
_here = os.path.dirname(os.path.abspath(__file__))
_vendor = os.path.join(_here, "vendor_ttws")
if _vendor not in sys.path:
    sys.path.insert(0, _vendor)

import grid_pb2
from ttws_types import (
    Colour, CellType, NodeType, EdgeType, SymmetryType,
    Cell, Node, Edge, Square, Triangle, Star, Tetris, Hexagon,
)
from puzzle import Puzzle
from unified_puzzle import UnifiedPuzzle


# === Colour 到字符串名称的映射 ===
_COLOUR_TO_NAME = {
    Colour.BLACK: "black",
    Colour.WHITE: "white",
    Colour.CYAN: "cyan",
    Colour.MAGENTA: "magenta",
    Colour.YELLOW: "yellow",
    Colour.RED: "red",
    Colour.GREEN: "green",
    Colour.BLUE: "blue",
    Colour.ORANGE: "orange",
}


def _decode_protobuf(code: str) -> Puzzle:
    """将 protobuf base64 编码的谜题字符串解码为 Puzzle 对象（Python 3 兼容）。"""
    code = code.replace("\x00", "").strip().split("/")[-1]
    if code.endswith("_0"):
        code = code[:-2]
    code = code.replace("_", "/").replace("-", "+")

    storage = grid_pb2.Storage()
    storage.ParseFromString(base64.b64decode(code))

    storage_width = storage.width
    total_count = sum(e.count if e.count else 1 for e in storage.entity)

    width = storage_width // 2
    height = (total_count // storage_width) // 2

    # 对称性映射
    symmetry_map = {
        grid_pb2.UNKNOWN_SYMMETRY: SymmetryType.NONE,
        grid_pb2.NO_SYMMETRY: SymmetryType.NONE,
        grid_pb2.HORIZONTAL: SymmetryType.HORIZONTAL,
        grid_pb2.VERTICAL: SymmetryType.VERTICAL,
        grid_pb2.ROTATIONAL: SymmetryType.ROTATIONAL,
    }

    colour_map = {
        grid_pb2.BLACK: Colour.BLACK, grid_pb2.WHITE: Colour.WHITE,
        grid_pb2.CYAN: Colour.CYAN, grid_pb2.MAGENTA: Colour.MAGENTA,
        grid_pb2.YELLOW: Colour.YELLOW, grid_pb2.RED: Colour.RED,
        grid_pb2.GREEN: Colour.GREEN, grid_pb2.BLUE: Colour.BLUE,
        grid_pb2.ORANGE: Colour.ORANGE,
    }

    node_map = {
        grid_pb2.UNKNOWN_ENUM: NodeType.NONE, grid_pb2.NONE: NodeType.NONE,
        grid_pb2.START: NodeType.START, grid_pb2.END: NodeType.END,
        grid_pb2.HEXAGON: NodeType.HEXAGON,
    }

    edge_map = {
        grid_pb2.UNKNOWN_ENUM: EdgeType.NONE, grid_pb2.NONE: EdgeType.NONE,
        grid_pb2.DISJOINT: EdgeType.MISSING, grid_pb2.HEXAGON: EdgeType.HEXAGON,
    }

    cell_map = {
        grid_pb2.UNKNOWN_ENUM: CellType.NONE, grid_pb2.NONE: CellType.NONE,
        grid_pb2.TRIANGLE: CellType.TRIANGLE, grid_pb2.SQUARE: CellType.SQUARE,
        grid_pb2.STAR: CellType.STAR, grid_pb2.ERROR: CellType.Y,
        grid_pb2.TETRIS: CellType.TETRIS,
    }

    puzzle = Puzzle(width, height)
    puzzle.symmetry = symmetry_map.get(storage.symmetry, SymmetryType.NONE)

    current_entity = 0
    for entity in storage.entity:
        if entity.count:
            current_entity += entity.count
            continue

        entity_y = current_entity // storage_width
        entity_x = current_entity % storage_width
        y = entity_y // 2
        x = entity_x // 2

        if entity_y % 2 == 0:
            if entity_x % 2 == 0:
                # Node
                puzzle.nodes[y][x] = Node(type=node_map.get(entity.type, NodeType.NONE))
            else:
                # V-edge
                puzzle.v_edges[y][x] = Edge(type=edge_map.get(entity.type, EdgeType.NONE))
        else:
            if entity_x % 2 == 0:
                # H-edge
                puzzle.h_edges[y][x] = Edge(type=edge_map.get(entity.type, EdgeType.NONE))
            else:
                # Cell
                cell = Cell(type=cell_map.get(entity.type, CellType.NONE))
                if cell.is_triangle():
                    cell.triangle.number = entity.triangle_count
                elif cell.is_square():
                    cell.square.colour = colour_map.get(entity.color, Colour.WHITE)
                elif cell.is_star():
                    cell.star.colour = colour_map.get(entity.color, Colour.WHITE)
                elif cell.is_tetris():
                    shape = []
                    if entity.shape.width > 0:
                        index = 0
                        rows_count = len(entity.shape.grid) // entity.shape.width
                        for ty in range(rows_count):
                            for tx in range(entity.shape.width):
                                if entity.shape.grid[index]:
                                    shape.append((tx, ty))
                                index += 1
                    cell.tetris.shape = shape
                    if entity.shape.free:
                        cell.tetris.rotated = True
                    if entity.shape.negative:
                        cell.tetris.negative = True
                puzzle.cells[y][x] = cell

        current_entity += 1

    return puzzle


def _puzzle_to_unified(puzzle: Puzzle, source: str = "", index: int = 0) -> UnifiedPuzzle:
    """将 ttws Puzzle 对象转换为 UnifiedPuzzle。"""
    w, h = puzzle.width, puzzle.height

    # 对称性
    sym_map = {
        SymmetryType.NONE: None,
        SymmetryType.HORIZONTAL: "horizontal",
        SymmetryType.VERTICAL: "vertical",
        SymmetryType.ROTATIONAL: "rotational",
    }
    symmetry = sym_map.get(puzzle.symmetry)

    up = UnifiedPuzzle(
        cols=w, rows=h,
        symmetry=symmetry,
        source=source,
        source_index=index,
    )

    # 提取节点信息
    for y in range(h + 1):
        for x in range(w + 1):
            node = puzzle.nodes[y][x]
            if node.is_start():
                up.starts.append((x, y))
            if node.is_end():
                up.ends.append((x, y))
            if node.is_hexagon():
                up.hexagons.append((x, y))

    # 提取边信息
    for y in range(h + 1):
        for x in range(w):
            edge = puzzle.v_edges[y][x]
            if edge.is_hexagon():
                up.hex_edges.append((x, y, "v"))
            if edge.is_missing():
                up.missing_edges.append((x, y, "v"))

    for y in range(h):
        for x in range(w + 1):
            edge = puzzle.h_edges[y][x]
            if edge.is_hexagon():
                up.hex_edges.append((x, y, "h"))
            if edge.is_missing():
                up.missing_edges.append((x, y, "h"))

    # 提取单元格信息
    for y in range(h):
        for x in range(w):
            cell = puzzle.cells[y][x]
            if cell.is_square():
                color_name = _COLOUR_TO_NAME.get(cell.square.colour, "white")
                up.squares[(x, y)] = color_name
            elif cell.is_star():
                color_name = _COLOUR_TO_NAME.get(cell.star.colour, "white")
                up.stars[(x, y)] = color_name
            elif cell.is_triangle():
                up.triangles[(x, y)] = cell.triangle.number
            elif cell.is_tetris():
                up.tetris[(x, y)] = {
                    "shape": cell.tetris._shape if cell.tetris._shape else [(0, 0)],
                    "rotated": cell.tetris._rotated,
                    "negative": cell.tetris.negative,
                }
            elif cell.is_y():
                up.eliminations.append((x, y))

    return up


def ingest_file(filepath: str, source_label: str = "") -> List[UnifiedPuzzle]:
    """从谜题编码文件中读取所有谜题。"""
    with open(filepath) as f:
        codes = [line.strip() for line in f if line.strip()]

    puzzles = []
    errors = 0
    for i, code in enumerate(codes):
        try:
            puzzle = _decode_protobuf(code)
            up = _puzzle_to_unified(puzzle, source=source_label, index=i)
            puzzles.append(up)
        except Exception as e:
            errors += 1

    return puzzles


def ingest_all() -> List[UnifiedPuzzle]:
    """从 vendor_ttws/ 中读取所有谜题文件。"""
    vendor_dir = os.path.join(_here, "vendor_ttws")

    all_puzzles = []
    for filename, label in [("witness_puzzles", "witness"), ("windmill_puzzles", "windmill")]:
        filepath = os.path.join(vendor_dir, filename)
        if os.path.exists(filepath):
            puzzles = ingest_file(filepath, label)
            all_puzzles.extend(puzzles)

    return all_puzzles


if __name__ == "__main__":
    puzzles = ingest_all()
    print(f"Total decoded: {len(puzzles)}")

    from collections import Counter
    types = Counter(p.classify() for p in puzzles)
    print(f"\nType distribution:")
    for t, n in types.most_common():
        print(f"  {t}: {n}")

    features = Counter()
    for p in puzzles:
        for f in p.feature_set():
            features[f] += 1
    print(f"\nFeature counts:")
    for f, n in features.most_common():
        print(f"  {f}: {n}")
