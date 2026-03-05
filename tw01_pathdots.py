"""
tw01_pathdots.py — PathDots: 六边形点（路径必经）谜题

The Witness 核心机制之一：在网格上画线，路径必须经过所有标记点。
这是最基础的约束类型，训练 Agent 的路径规划和空间推理能力。

Core Knowledge: Objectness — 路径上的必经节点
ARC-AGI 启示: "保留特定元素"规则

关卡设计（渐进式教学）:
  Level 1: 3×3网格，1个点在直线路径上（自然经过）
  Level 2: 3×3网格，1个点需要绕行
  Level 3: 4×4网格，2个点
  Level 4: 4×4网格，3个点（需要精确路径规划）
  Level 5: 5×5网格，4个点（假设打破：点在边上）
"""

import sys
import os
# 确保本目录在 sys.path 中（兼容 SDK exec() 和直接运行两种方式）
try:
    _code_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _code_dir = os.getcwd()
if _code_dir not in sys.path:
    sys.path.insert(0, _code_dir)

from arcengine import (
    ARCBaseGame, BlockingMode, Camera, GameAction,
    InteractionMode, Level, Sprite,
)
from witness_grid import (
    WitnessGrid, GRID_BG, PATH_COLOR, CURSOR_COLOR,
    START_COLOR, END_COLOR, DOT_COLOR, ERROR_COLOR, SUCCESS_COLOR,
    COLOR_BLACK,
)
from typing import List, Tuple, Set, Optional


class Tw01(ARCBaseGame):
    """PathDots — 路径必经点谜题

    规则：从起点画线到终点，路径必须经过所有标记的黄色点。
    """

    def __init__(self, seed: int = 0):
        self._seed = seed

        # 游戏状态 — 必须在 super().__init__() 之前初始化，
        # 因为 super().__init__() 会调用 on_set_level() 设置这些值
        self._path: List[Tuple[int, int]] = []
        self._grid: Optional[WitnessGrid] = None
        self._start: Tuple[int, int] = (0, 0)
        self._end: Tuple[int, int] = (0, 0)
        self._dots: List[Tuple[int, int]] = []
        self._breakpoints: Set[Tuple[Tuple[int, int], Tuple[int, int]]] = set()
        self._drawing = False

        levels = self._create_levels()
        camera = Camera(background=GRID_BG, letter_box=COLOR_BLACK)
        super().__init__(
            game_id="tw01",
            levels=levels,
            camera=camera,
            win_score=len(levels),
            available_actions=[1, 2, 3, 4, 5],  # 上下左右 + 确认
            seed=seed,
        )

    @staticmethod
    def _load_json_levels() -> Optional[list]:
        """尝试从 JSON 文件加载关卡。返回 [{"config": ..., "validated": bool}]。"""
        try:
            import json
            levels_path = os.path.join(_code_dir, "levels", "tw01_levels.json")
            if os.path.exists(levels_path):
                with open(levels_path) as f:
                    data = json.load(f)
                return [{"config": entry["config"],
                         "validated": entry.get("validated", True)}
                        for entry in data["levels"]]
        except Exception:
            pass
        return None

    def _create_levels(self) -> List[Level]:
        """创建所有关卡。优先从 JSON 加载，回退到硬编码。"""
        json_entries = self._load_json_levels()
        if json_entries:
            level_configs = []
            for entry in json_entries:
                cfg = entry["config"]
                config = {
                    "cols": cfg["cols"],
                    "rows": cfg["rows"],
                    "start": tuple(cfg["start"]),
                    "end": tuple(cfg["end"]),
                    "dots": [tuple(d) for d in cfg["dots"]],
                    "validated": entry.get("validated", True),
                }
                if "breakpoints" in cfg:
                    config["breakpoints"] = [
                        (tuple(bp[0]), tuple(bp[1])) for bp in cfg["breakpoints"]
                    ]
                level_configs.append(config)
        else:
            # 硬编码回退
            level_configs = [
                {
                    "cols": 3, "rows": 3,
                    "start": (0, 0), "end": (3, 0),
                    "dots": [(2, 0)],
                },
                {
                    "cols": 3, "rows": 3,
                    "start": (0, 0), "end": (3, 0),
                    "dots": [(1, 1)],
                },
                {
                    "cols": 4, "rows": 4,
                    "start": (0, 0), "end": (4, 4),
                    "dots": [(2, 0), (2, 4)],
                },
                {
                    "cols": 4, "rows": 4,
                    "start": (0, 0), "end": (4, 4),
                    "dots": [(0, 2), (4, 2), (2, 4)],
                },
                {
                    "cols": 5, "rows": 5,
                    "start": (0, 0), "end": (5, 5),
                    "dots": [(1, 0), (5, 1), (3, 5), (0, 3)],
                },
            ]

        levels = []
        for i, config in enumerate(level_configs):
            grid = WitnessGrid(config["cols"], config["rows"])
            frame = grid.render_grid()

            # 绘制起点和终点
            grid.draw_start(frame, config["start"])
            grid.draw_end(frame, config["end"])

            # 绘制必经点
            for dot in config["dots"]:
                grid.draw_dot(frame, dot, DOT_COLOR)

            # 未验证标记
            if not config.get("validated", True):
                grid.draw_unvalidated_indicator(frame)

            # 创建背景 sprite
            bg_sprite = Sprite(
                pixels=frame,
                name="grid_bg",
                x=0, y=0,
                layer=-10,
                blocking=BlockingMode.NOT_BLOCKED,
                interaction=InteractionMode.INTANGIBLE,
                tags=["sys_static"],
            )

            # 创建光标 sprite（在起点位置）
            sx, sy = grid.node_to_pixel(*config["start"])
            cursor_sprite = Sprite(
                pixels=[[CURSOR_COLOR]],
                name="cursor",
                x=sx, y=sy,
                layer=10,
                blocking=BlockingMode.NOT_BLOCKED,
                interaction=InteractionMode.TANGIBLE,
            )

            level_data = {
                "cols": config["cols"],
                "rows": config["rows"],
                "start": config["start"],
                "end": config["end"],
                "dots": config["dots"],
                "validated": config.get("validated", True),
            }
            if "breakpoints" in config:
                level_data["breakpoints"] = config["breakpoints"]

            level = Level(
                sprites=[bg_sprite, cursor_sprite],
                grid_size=(64, 64),
                data=level_data,
                name=f"Level {i + 1}",
            )
            levels.append(level)

        return levels

    def on_set_level(self, level: Level) -> None:
        """关卡切换时重置状态。"""
        data = level._data
        self._grid = WitnessGrid(data["cols"], data["rows"])
        self._start = tuple(data["start"])
        self._end = tuple(data["end"])
        self._dots = [tuple(d) for d in data["dots"]]
        self._breakpoints = set()
        for bp in data.get("breakpoints", []):
            n1, n2 = tuple(bp[0]), tuple(bp[1])
            self._breakpoints.add((min(n1, n2), max(n1, n2)))
        self._path = [self._start]
        self._drawing = True

    def _current_node(self) -> Tuple[int, int]:
        """当前路径末端节点。"""
        return self._path[-1] if self._path else self._start

    def _pixel_to_nearest_node(self, px: int, py: int) -> Optional[Tuple[int, int]]:
        """将像素坐标转换为最近的网格节点。"""
        if not self._grid:
            return None

        best_node = None
        best_dist = float('inf')

        for row in range(self._grid.rows + 1):
            for col in range(self._grid.cols + 1):
                nx, ny = self._grid.node_to_pixel(col, row)
                dist = abs(px - nx) + abs(py - ny)
                if dist < best_dist:
                    best_dist = dist
                    best_node = (col, row)

        return best_node

    def step(self) -> None:
        """核心游戏逻辑。"""
        if not self._grid or not self._drawing:
            self.complete_action()
            return

        action = self.action.id
        current = self._current_node()

        if action == GameAction.ACTION5:
            # 提交路径
            self._check_solution()
        elif action in (GameAction.ACTION1, GameAction.ACTION2,
                        GameAction.ACTION3, GameAction.ACTION4):
            # 方向移动
            dc, dr = 0, 0
            if action == GameAction.ACTION1:
                dr = -1  # 上
            elif action == GameAction.ACTION2:
                dr = 1   # 下
            elif action == GameAction.ACTION3:
                dc = -1  # 左
            elif action == GameAction.ACTION4:
                dc = 1   # 右

            target = (current[0] + dc, current[1] + dr)

            # 验证移动合法性
            if self._is_valid_move(current, target):
                # 如果回退到上一个节点
                if len(self._path) >= 2 and target == self._path[-2]:
                    self._path.pop()
                elif target not in self._path:
                    self._path.append(target)
                # else: target already in path (would create loop), ignore

                self._update_display()

        self.complete_action()

    def _is_valid_move(self, from_node: Tuple[int, int],
                       to_node: Tuple[int, int]) -> bool:
        """检查从一个节点移动到另一个节点是否合法。"""
        if not self._grid:
            return False

        fc, fr = from_node
        tc, tr = to_node

        # 检查目标在网格范围内
        if not (0 <= tc <= self._grid.cols and 0 <= tr <= self._grid.rows):
            return False

        # 必须是相邻节点（曼哈顿距离=1）
        if abs(fc - tc) + abs(fr - tr) != 1:
            return False

        # 检查断点
        edge = (min(from_node, to_node), max(from_node, to_node))
        if edge in self._breakpoints:
            return False

        return True

    def _check_solution(self) -> None:
        """检查当前路径是否满足所有约束。"""
        # 检查1: 路径必须到达终点
        if self._current_node() != self._end:
            self._show_error()
            return

        # 检查2: 路径必须经过所有必经点
        path_set = set(self._path)
        for dot in self._dots:
            if dot not in path_set:
                self._show_error()
                return

        # 全部通过！
        self._show_success()
        self.next_level()

    def _show_error(self) -> None:
        """显示错误反馈（短暂闪红）。"""
        # 重置路径
        self._path = [self._start]
        self._update_display()

    def _show_success(self) -> None:
        """显示成功反馈。"""
        # 路径变绿
        self._update_display(path_color=SUCCESS_COLOR)

    def _update_display(self, path_color: int = PATH_COLOR) -> None:
        """更新显示。"""
        if not self._grid:
            return

        data = self.current_level._data
        frame = self._grid.render_grid()

        # 绘制起点和终点
        self._grid.draw_start(frame, self._start)
        self._grid.draw_end(frame, self._end)

        # 绘制必经点
        for dot in self._dots:
            covered = dot in set(self._path)
            color = SUCCESS_COLOR if covered else DOT_COLOR
            self._grid.draw_dot(frame, dot, color)

        # 绘制路径
        for i in range(len(self._path) - 1):
            self._grid.draw_path_segment(frame, self._path[i], self._path[i + 1], path_color)

        # 绘制光标
        if self._path:
            cursor_node = self._path[-1]
            self._grid.draw_dot(frame, cursor_node, CURSOR_COLOR)

        # 未验证标记
        if not self.current_level._data.get("validated", True):
            self._grid.draw_unvalidated_indicator(frame)

        # 更新背景 sprite
        bg_sprites = self.current_level.get_sprites_by_name("grid_bg")
        if bg_sprites:
            self.current_level.remove_sprite(bg_sprites[0])

        new_bg = Sprite(
            pixels=frame,
            name="grid_bg",
            x=0, y=0,
            layer=-10,
            blocking=BlockingMode.NOT_BLOCKED,
            interaction=InteractionMode.INTANGIBLE,
            tags=["sys_static"],
        )
        self.current_level.add_sprite(new_bg)

        # 移动光标 sprite
        if self._path:
            cx, cy = self._grid.node_to_pixel(*self._path[-1])
            cursor_sprites = self.current_level.get_sprites_by_name("cursor")
            if cursor_sprites:
                cursor_sprites[0].set_position(cx, cy)
