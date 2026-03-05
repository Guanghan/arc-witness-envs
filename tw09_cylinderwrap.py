"""
tw09_cylinderwrap.py — CylinderWrap: 圆柱环绕谜题

面板水平环绕：左边缘连接右边缘。路径可以从一侧走到另一侧。
基础约束使用 dots（类似 tw01），渐进引入 wrap 需求。
训练 Agent 的拓扑推理能力。

Core Knowledge: Topology — 非平面空间
ARC-AGI 启示: 边界条件和拓扑不变量

手工设计 5 个关卡（无 TTWS 数据）。
"""

import sys
import os
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
    COLOR_BLACK, COLOR_PURPLE,
)
from typing import List, Tuple, Set, Optional


class Tw09(ARCBaseGame):
    """CylinderWrap — 圆柱环绕谜题

    规则：从起点画线到终点，路径必须经过所有标记点。
    特殊机制：面板水平环绕，col=0 和 col=cols 相连。
    """

    def __init__(self, seed: int = 0):
        self._seed = seed
        self._path: List[Tuple[int, int]] = []
        self._grid: Optional[WitnessGrid] = None
        self._start: Tuple[int, int] = (0, 0)
        self._end: Tuple[int, int] = (0, 0)
        self._dots: List[Tuple[int, int]] = []

        levels = self._create_levels()
        camera = Camera(background=GRID_BG, letter_box=COLOR_BLACK)
        super().__init__(
            game_id="tw09",
            levels=levels,
            camera=camera,
            win_score=len(levels),
            available_actions=[1, 2, 3, 4, 5],
            seed=seed,
        )

    @staticmethod
    def _load_json_levels() -> Optional[list]:
        try:
            import json
            levels_path = os.path.join(_code_dir, "levels", "tw09_levels.json")
            if os.path.exists(levels_path):
                with open(levels_path) as f:
                    data = json.load(f)
                return [entry["config"] for entry in data["levels"]]
        except Exception:
            pass
        return None

    def _create_levels(self) -> List[Level]:
        json_configs = self._load_json_levels()
        if json_configs:
            level_configs = []
            for cfg in json_configs:
                config = {
                    "cols": cfg["cols"],
                    "rows": cfg["rows"],
                    "start": tuple(cfg["start"]),
                    "end": tuple(cfg["end"]),
                    "dots": [tuple(d) for d in cfg["dots"]],
                }
                level_configs.append(config)
        else:
            # 手工设计 5 个关卡
            level_configs = [
                # Level 1: 3×3, 起终点在两侧，需要 wrap
                {
                    "cols": 3, "rows": 3,
                    "start": (0, 0), "end": (0, 3),
                    "dots": [(3, 1)],  # 需要向右走到 col=3 然后 wrap 回来
                },
                # Level 2: 3×3, dot 在对面
                {
                    "cols": 3, "rows": 3,
                    "start": (0, 0), "end": (3, 3),
                    "dots": [(3, 0), (0, 2)],  # wrap needed to reach dots efficiently
                },
                # Level 3: 4×3, 多个 dots
                {
                    "cols": 4, "rows": 3,
                    "start": (0, 0), "end": (0, 3),
                    "dots": [(4, 1), (2, 2)],
                },
                # Level 4: 4×4, 复杂 wrap 路径
                {
                    "cols": 4, "rows": 4,
                    "start": (0, 0), "end": (4, 4),
                    "dots": [(4, 0), (0, 2), (4, 3)],
                },
                # Level 5: 5×4, 需要多次 wrap
                {
                    "cols": 5, "rows": 4,
                    "start": (0, 0), "end": (5, 4),
                    "dots": [(5, 1), (0, 3), (3, 2)],
                },
            ]

        levels = []
        for i, config in enumerate(level_configs):
            grid = WitnessGrid(config["cols"], config["rows"])
            frame = grid.render_grid()

            grid.draw_start(frame, config["start"])
            grid.draw_end(frame, config["end"])

            for dot in config["dots"]:
                grid.draw_dot(frame, dot, DOT_COLOR)

            # 绘制 wrap 指示器（左右边缘用紫色标记）
            for row in range(config["rows"] + 1):
                # 左边缘
                lx, ly = grid.node_to_pixel(0, row)
                if 0 <= lx - 1 < 64 and 0 <= ly < 64:
                    frame[ly][lx - 1] = COLOR_PURPLE
                # 右边缘
                rx, ry = grid.node_to_pixel(config["cols"], row)
                if 0 <= rx + 1 < 64 and 0 <= ry < 64:
                    frame[ry][rx + 1] = COLOR_PURPLE

            bg_sprite = Sprite(
                pixels=frame, name="grid_bg",
                x=0, y=0, layer=-10,
                blocking=BlockingMode.NOT_BLOCKED,
                interaction=InteractionMode.INTANGIBLE,
                tags=["sys_static"],
            )

            sx, sy = grid.node_to_pixel(*config["start"])
            cursor_sprite = Sprite(
                pixels=[[CURSOR_COLOR]], name="cursor",
                x=sx, y=sy, layer=10,
                blocking=BlockingMode.NOT_BLOCKED,
                interaction=InteractionMode.TANGIBLE,
            )

            level = Level(
                sprites=[bg_sprite, cursor_sprite],
                grid_size=(64, 64),
                data={
                    "cols": config["cols"],
                    "rows": config["rows"],
                    "start": config["start"],
                    "end": config["end"],
                    "dots": config["dots"],
                },
                name=f"Level {i + 1}",
            )
            levels.append(level)

        return levels

    def on_set_level(self, level: Level) -> None:
        data = level._data
        self._grid = WitnessGrid(data["cols"], data["rows"])
        self._start = tuple(data["start"])
        self._end = tuple(data["end"])
        self._dots = [tuple(d) for d in data["dots"]]
        self._path = [self._start]

    def step(self) -> None:
        if not self._grid:
            self.complete_action()
            return

        action = self.action.id
        current = self._path[-1] if self._path else self._start

        if action == GameAction.ACTION5:
            self._check_solution()
        elif action in (GameAction.ACTION1, GameAction.ACTION2,
                        GameAction.ACTION3, GameAction.ACTION4):
            dc, dr = 0, 0
            if action == GameAction.ACTION1: dr = -1
            elif action == GameAction.ACTION2: dr = 1
            elif action == GameAction.ACTION3: dc = -1
            elif action == GameAction.ACTION4: dc = 1

            target = (current[0] + dc, current[1] + dr)

            # Wrap 逻辑：水平环绕
            cols = self._grid.cols
            tc, tr = target
            if tc < 0:
                target = (cols, tr)  # wrap left -> right
            elif tc > cols:
                target = (0, tr)    # wrap right -> left

            if self._is_valid_move(current, target):
                if len(self._path) >= 2 and target == self._path[-2]:
                    self._path.pop()
                elif target not in self._path:
                    self._path.append(target)
                self._update_display()

        self.complete_action()

    def _is_valid_move(self, from_node, to_node):
        if not self._grid:
            return False
        tc, tr = to_node
        # 水平方向允许 0..cols（wrap 后已处理），垂直方向正常
        if not (0 <= tc <= self._grid.cols and 0 <= tr <= self._grid.rows):
            return False
        return True

    def _check_solution(self) -> None:
        if self._path[-1] != self._end:
            self._path = [self._start]
            self._update_display()
            return

        path_set = set(self._path)
        for dot in self._dots:
            if dot not in path_set:
                self._path = [self._start]
                self._update_display()
                return

        self._update_display(path_color=SUCCESS_COLOR)
        self.next_level()

    def _update_display(self, path_color: int = PATH_COLOR) -> None:
        if not self._grid:
            return

        frame = self._grid.render_grid()
        self._grid.draw_start(frame, self._start)
        self._grid.draw_end(frame, self._end)

        for dot in self._dots:
            covered = dot in set(self._path)
            color = SUCCESS_COLOR if covered else DOT_COLOR
            self._grid.draw_dot(frame, dot, color)

        # Wrap 指示器
        for row in range(self._grid.rows + 1):
            lx, ly = self._grid.node_to_pixel(0, row)
            if 0 <= lx - 1 < 64 and 0 <= ly < 64:
                frame[ly][lx - 1] = COLOR_PURPLE
            rx, ry = self._grid.node_to_pixel(self._grid.cols, row)
            if 0 <= rx + 1 < 64 and 0 <= ry < 64:
                frame[ry][rx + 1] = COLOR_PURPLE

        for i in range(len(self._path) - 1):
            n1, n2 = self._path[i], self._path[i + 1]
            # 对于 wrap 边（跨越左右），分两段绘制
            if abs(n1[0] - n2[0]) > 1:
                # Wrap edge: draw to edge on both sides
                pass  # 简化处理：不绘制 wrap 边的连线
            else:
                self._grid.draw_path_segment(frame, n1, n2, path_color)

        if self._path:
            self._grid.draw_dot(frame, self._path[-1], CURSOR_COLOR)

        bg_sprites = self.current_level.get_sprites_by_name("grid_bg")
        if bg_sprites:
            self.current_level.remove_sprite(bg_sprites[0])

        new_bg = Sprite(
            pixels=frame, name="grid_bg",
            x=0, y=0, layer=-10,
            blocking=BlockingMode.NOT_BLOCKED,
            interaction=InteractionMode.INTANGIBLE,
            tags=["sys_static"],
        )
        self.current_level.add_sprite(new_bg)
