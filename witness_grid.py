"""
witness_grid.py — The Witness 风格面板谜题的共享网格渲染工具

所有见证者启发的 ARC-AGI-3 游戏共享此工具类来渲染面板网格。

核心概念：
- 在 64×64 像素空间中渲染一个 N×M 的网格面板
- 网格由"节点"（线段交叉点）和"边"（连接节点的线段）组成
- 路径沿网格边行走
- 符号放置在单元格中心

颜色索引（16色调色板）：
  0=白色, 1=浅灰, 2=中灰, 3=深灰, 4=近黑, 5=黑色,
  6=品红, 7=浅品红, 8=红色, 9=蓝色, 10=浅蓝, 11=黄色,
  12=橙色, 13=栗色, 14=绿色, 15=紫色
"""

import numpy as np
from typing import List, Tuple, Optional, Set
from arcengine import Sprite


# === 颜色常量 ===
COLOR_WHITE = 0
COLOR_LIGHT_GRAY = 1
COLOR_GRAY = 2
COLOR_DARK_GRAY = 3
COLOR_NEAR_BLACK = 4
COLOR_BLACK = 5
COLOR_MAGENTA = 6
COLOR_LIGHT_MAGENTA = 7
COLOR_RED = 8
COLOR_BLUE = 9
COLOR_LIGHT_BLUE = 10
COLOR_YELLOW = 11
COLOR_ORANGE = 12
COLOR_MAROON = 13
COLOR_GREEN = 14
COLOR_PURPLE = 15

# === 语义颜色 ===
GRID_BG = COLOR_DARK_GRAY      # 网格背景（面板底色）
GRID_LINE = COLOR_NEAR_BLACK   # 网格线
PATH_COLOR = COLOR_BLUE        # 已画路径
CURSOR_COLOR = COLOR_YELLOW    # 光标/活跃位置
START_COLOR = COLOR_GREEN      # 起点
END_COLOR = COLOR_RED          # 终点
DOT_COLOR = COLOR_YELLOW       # 六边形点
ERROR_COLOR = COLOR_RED        # 错误反馈
SUCCESS_COLOR = COLOR_GREEN    # 正确反馈
CELL_BG = COLOR_WHITE          # 单元格背景
SQUARE_A = COLOR_MAGENTA       # 彩色方块A
SQUARE_B = COLOR_LIGHT_BLUE    # 彩色方块B
SQUARE_C = COLOR_ORANGE        # 彩色方块C
STAR_COLOR = COLOR_YELLOW      # 星星
POLY_COLOR = COLOR_PURPLE      # 多联骨牌
TRI_COLOR = COLOR_ORANGE       # 三角形
ERASER_COLOR = COLOR_WHITE     # 消除符号


class WitnessGrid:
    """The Witness 风格网格面板。

    网格坐标系：
    - 节点(node)坐标: (col, row)，范围 [0, cols] × [0, rows]
    - 边(edge): 两个相邻节点之间的连线
    - 单元格(cell)坐标: (col, row)，范围 [0, cols-1] × [0, rows-1]

    渲染到 64×64 像素空间：
    - 外边距: margin 像素
    - 节点: node_size × node_size 像素
    - 边: edge_length × line_width 像素
    - 单元格: cell_size × cell_size 像素
    """

    def __init__(self, cols: int, rows: int, margin: int = 4):
        """
        Args:
            cols: 网格列数（单元格数）
            rows: 网格行数（单元格数）
            margin: 外边距像素数
        """
        self.cols = cols
        self.rows = rows
        self.margin = margin

        # 计算像素尺寸
        # 可用空间 = 64 - 2*margin
        avail = 64 - 2 * margin
        # 使用较大维度计算 cell_size，确保两个方向都能放下
        self.node_size = 1
        self.line_width = 1
        max_dim = max(cols, rows)
        self.cell_size = (avail - (max_dim + 1) * self.node_size) // max_dim

        # 检查是否适合
        total_w = (cols + 1) * self.node_size + cols * self.cell_size
        total_h = (rows + 1) * self.node_size + rows * self.cell_size
        assert total_w <= avail, f"Grid too wide: {total_w} > {avail}"
        assert total_h <= avail, f"Grid too tall: {total_h} > {avail}"

        # 居中偏移
        self.offset_x = margin + (avail - total_w) // 2
        self.offset_y = margin + (avail - total_h) // 2

    def node_to_pixel(self, col: int, row: int) -> Tuple[int, int]:
        """将节点坐标转换为像素坐标（左上角）。"""
        px = self.offset_x + col * (self.node_size + self.cell_size)
        py = self.offset_y + row * (self.node_size + self.cell_size)
        return (px, py)

    def cell_center_pixel(self, col: int, row: int) -> Tuple[int, int]:
        """将单元格坐标转换为中心像素坐标。"""
        px = self.offset_x + col * (self.node_size + self.cell_size) + self.node_size + self.cell_size // 2
        py = self.offset_y + row * (self.node_size + self.cell_size) + self.node_size + self.cell_size // 2
        return (px, py)

    def render_grid(self) -> List[List[int]]:
        """渲染空网格为 64×64 像素数组。

        Returns:
            64×64 的 int 数组（颜色索引）
        """
        frame = [[GRID_BG] * 64 for _ in range(64)]

        # 绘制网格线（节点 + 连接）
        for row in range(self.rows + 1):
            for col in range(self.cols + 1):
                # 绘制节点
                nx, ny = self.node_to_pixel(col, row)
                if 0 <= nx < 64 and 0 <= ny < 64:
                    frame[ny][nx] = GRID_LINE

                # 绘制水平边（节点右侧）
                if col < self.cols:
                    for dx in range(1, self.cell_size + 1):
                        px = nx + dx
                        if 0 <= px < 64 and 0 <= ny < 64:
                            frame[ny][px] = GRID_LINE

                # 绘制垂直边（节点下方）
                if row < self.rows:
                    for dy in range(1, self.cell_size + 1):
                        py = ny + dy
                        if 0 <= nx < 64 and 0 <= py < 64:
                            frame[py][nx] = GRID_LINE

        # 填充单元格背景
        for row in range(self.rows):
            for col in range(self.cols):
                cx = self.offset_x + col * (self.node_size + self.cell_size) + self.node_size
                cy = self.offset_y + row * (self.node_size + self.cell_size) + self.node_size
                for dy in range(self.cell_size):
                    for dx in range(self.cell_size):
                        px, py = cx + dx, cy + dy
                        if 0 <= px < 64 and 0 <= py < 64:
                            frame[py][px] = CELL_BG

        return frame

    def render_to_sprite(self, extra_pixels: Optional[List[Tuple[int, int, int]]] = None) -> Sprite:
        """渲染网格为 Sprite 对象。

        Args:
            extra_pixels: 额外像素列表 [(x, y, color), ...]

        Returns:
            64×64 的 Sprite 对象
        """
        frame = self.render_grid()

        if extra_pixels:
            for x, y, color in extra_pixels:
                if 0 <= x < 64 and 0 <= y < 64:
                    frame[y][x] = color

        return Sprite(
            pixels=frame,
            name="grid_bg",
            x=0, y=0,
            layer=-10,
            tags=["sys_static"],
        )

    def draw_path_segment(self, frame: List[List[int]],
                          node1: Tuple[int, int], node2: Tuple[int, int],
                          color: int = PATH_COLOR):
        """在帧上绘制两个相邻节点之间的路径段。"""
        x1, y1 = self.node_to_pixel(*node1)
        x2, y2 = self.node_to_pixel(*node2)

        if x1 == x2:  # 垂直
            for y in range(min(y1, y2), max(y1, y2) + 1):
                if 0 <= x1 < 64 and 0 <= y < 64:
                    frame[y][x1] = color
        elif y1 == y2:  # 水平
            for x in range(min(x1, x2), max(x1, x2) + 1):
                if 0 <= x < 64 and 0 <= y1 < 64:
                    frame[y1][x] = color

    def draw_dot(self, frame: List[List[int]],
                 node: Tuple[int, int], color: int = DOT_COLOR):
        """在节点位置绘制一个点标记。"""
        nx, ny = self.node_to_pixel(*node)
        # 绘制3×3十字形（如果空间允许）
        for dx, dy in [(-1, 0), (0, -1), (0, 0), (1, 0), (0, 1)]:
            px, py = nx + dx, ny + dy
            if 0 <= px < 64 and 0 <= py < 64:
                frame[py][px] = color

    def draw_start(self, frame: List[List[int]], node: Tuple[int, int]):
        """绘制起点标记。"""
        self.draw_dot(frame, node, START_COLOR)

    def draw_end(self, frame: List[List[int]], node: Tuple[int, int]):
        """绘制终点标记。"""
        self.draw_dot(frame, node, END_COLOR)

    def draw_cell_symbol(self, frame: List[List[int]],
                         cell: Tuple[int, int], color: int,
                         size: int = 3):
        """在单元格中心绘制方块符号。"""
        cx, cy = self.cell_center_pixel(*cell)
        half = size // 2
        for dy in range(-half, half + 1):
            for dx in range(-half, half + 1):
                px, py = cx + dx, cy + dy
                if 0 <= px < 64 and 0 <= py < 64:
                    frame[py][px] = color

    def get_adjacent_nodes(self, node: Tuple[int, int]) -> List[Tuple[int, int]]:
        """获取节点的所有相邻节点。"""
        col, row = node
        neighbors = []
        for dc, dr in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nc, nr = col + dc, row + dr
            if 0 <= nc <= self.cols and 0 <= nr <= self.rows:
                neighbors.append((nc, nr))
        return neighbors

    def path_to_edges(self, path: List[Tuple[int, int]]) -> Set[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """将路径节点序列转换为边集合。"""
        edges = set()
        for i in range(len(path) - 1):
            a, b = path[i], path[i + 1]
            edges.add((min(a, b), max(a, b)))
        return edges

    def path_splits_regions(self, path: List[Tuple[int, int]]) -> List[Set[Tuple[int, int]]]:
        """根据路径将面板分割为区域。

        Returns:
            区域列表，每个区域是单元格坐标的集合
        """
        path_edges = self.path_to_edges(path)

        # 用 BFS 找连通区域
        visited = set()
        regions = []

        for row in range(self.rows):
            for col in range(self.cols):
                cell = (col, row)
                if cell in visited:
                    continue

                # BFS 从这个单元格开始
                region = set()
                queue = [cell]
                while queue:
                    c = queue.pop(0)
                    if c in visited:
                        continue
                    visited.add(c)
                    region.add(c)

                    cc, cr = c
                    # 检查四个方向的相邻单元格
                    for dc, dr, edge_n1, edge_n2 in [
                        (-1, 0, (cc, cr), (cc, cr + 1)),    # 左
                        (1, 0, (cc + 1, cr), (cc + 1, cr + 1)),  # 右
                        (0, -1, (cc, cr), (cc + 1, cr)),    # 上
                        (0, 1, (cc, cr + 1), (cc + 1, cr + 1)),  # 下
                    ]:
                        nc, nr = cc + dc, cr + dr
                        if 0 <= nc < self.cols and 0 <= nr < self.rows:
                            edge = (min(edge_n1, edge_n2), max(edge_n1, edge_n2))
                            if edge not in path_edges and (nc, nr) not in visited:
                                queue.append((nc, nr))

                regions.append(region)

        return regions

    def draw_star(self, frame: List[List[int]],
                  cell: Tuple[int, int], color: int = STAR_COLOR):
        """在单元格中心绘制星星符号（菱形）。与方块区分。"""
        cx, cy = self.cell_center_pixel(*cell)
        # Diamond shape
        for dx, dy in [(-2, 0), (-1, -1), (-1, 0), (-1, 1),
                       (0, -2), (0, -1), (0, 0), (0, 1), (0, 2),
                       (1, -1), (1, 0), (1, 1), (2, 0)]:
            px, py = cx + dx, cy + dy
            if 0 <= px < 64 and 0 <= py < 64:
                frame[py][px] = color

    def draw_triangle(self, frame: List[List[int]],
                      cell: Tuple[int, int], count: int,
                      color: int = TRI_COLOR):
        """在单元格中绘制 1-3 个小三角形标记。"""
        cx, cy = self.cell_center_pixel(*cell)
        offsets = [0] if count == 1 else [-2, 2] if count == 2 else [-3, 0, 3]
        for ox in offsets[:count]:
            px_base = cx + ox
            # Small upward triangle: 3 pixels
            for dy, dx in [(-1, 0), (0, -1), (0, 0), (0, 1)]:
                ppx, ppy = px_base + dx, cy + dy
                if 0 <= ppx < 64 and 0 <= ppy < 64:
                    frame[ppy][ppx] = color

    def draw_polyomino(self, frame: List[List[int]],
                       cell: Tuple[int, int], shape: list,
                       color: int = POLY_COLOR):
        """在单元格中绘制多联骨牌形状预览。"""
        cx, cy = self.cell_center_pixel(*cell)
        for sx, sy in shape:
            for dx in range(2):
                for dy in range(2):
                    px = cx - 2 + sx * 2 + dx
                    py = cy - 2 + sy * 2 + dy
                    if 0 <= px < 64 and 0 <= py < 64:
                        frame[py][px] = color

    def draw_eraser(self, frame: List[List[int]],
                    cell: Tuple[int, int], color: int = ERASER_COLOR):
        """在单元格中心绘制消除符号（Y形）。"""
        cx, cy = self.cell_center_pixel(*cell)
        # Y shape: stem + two branches
        for dx, dy in [(0, 0), (0, 1), (0, 2), (-1, -1), (1, -1), (-2, -2), (2, -2)]:
            px, py = cx + dx, cy + dy
            if 0 <= px < 64 and 0 <= py < 64:
                frame[py][px] = color

    def cell_edge_count(self, cell: Tuple[int, int],
                        path_edges: Set[Tuple[Tuple[int, int], Tuple[int, int]]]) -> int:
        """计算单元格边界被路径经过的边数。"""
        col, row = cell
        edges = [
            ((col, row), (col + 1, row)),       # 上
            ((col, row + 1), (col + 1, row + 1)),  # 下
            ((col, row), (col, row + 1)),         # 左
            ((col + 1, row), (col + 1, row + 1)),  # 右
        ]
        count = 0
        for e in edges:
            normalized = (min(e[0], e[1]), max(e[0], e[1]))
            if normalized in path_edges:
                count += 1
        return count
