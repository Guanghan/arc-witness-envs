"""
tw10_colorfilter.py — ColorFilter: 颜色滤镜谜题

颜色滤镜改变方块的感知颜色，约束基于感知颜色而非真实颜色。
训练 Agent 的感知变换推理能力。

Core Knowledge: Perception + Transformation — 颜色空间变换
ARC-AGI 启示: 变换后应用规则

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
    START_COLOR, END_COLOR, ERROR_COLOR, SUCCESS_COLOR,
    COLOR_BLACK, SQUARE_A, SQUARE_B, SQUARE_C,
    COLOR_MAROON,
)
from typing import List, Tuple, Set, Dict, Optional

# 滤镜颜色：用于标记滤镜格子
FILTER_COLOR = COLOR_MAROON  # 栗色边框标记滤镜


class Tw10(ARCBaseGame):
    """ColorFilter — 颜色滤镜谜题

    规则：从起点画线到终点，路径将面板分区。
    同一区域方块必须"同色"（与 tw02 相同）。
    但：滤镜格子改变其中方块的感知颜色。
    """

    def __init__(self, seed: int = 0):
        self._seed = seed
        self._path: List[Tuple[int, int]] = []
        self._grid: Optional[WitnessGrid] = None
        self._start: Tuple[int, int] = (0, 0)
        self._end: Tuple[int, int] = (0, 0)
        self._squares: Dict[Tuple[int, int], int] = {}
        self._filters: Dict[Tuple[int, int], int] = {}  # cell -> new_color

        levels = self._create_levels()
        camera = Camera(background=GRID_BG, letter_box=COLOR_BLACK)
        super().__init__(
            game_id="tw10",
            levels=levels,
            camera=camera,
            win_score=min(len(levels), 254),
            available_actions=[1, 2, 3, 4, 5],
            seed=seed,
        )

    @staticmethod
    def _load_json_levels() -> Optional[list]:
        """Load levels from JSON file.

        Returns a list of dicts with keys 'config' and 'validated'.
        """
        try:
            import json
            levels_path = os.path.join(_code_dir, "levels", "tw10_levels.json")
            if os.path.exists(levels_path):
                with open(levels_path) as f:
                    data = json.load(f)
                return [{"config": entry["config"], "validated": entry.get("validated", True)} for entry in data["levels"]]
        except Exception:
            pass
        return None

    def _create_levels(self) -> List[Level]:
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
                    "squares": {
                        tuple(int(x) for x in k.split(",")): v
                        for k, v in cfg["squares"].items()
                    },
                    "filters": {
                        tuple(int(x) for x in k.split(",")): v
                        for k, v in cfg["filters"].items()
                    },
                    "validated": entry.get("validated", True),
                }
                level_configs.append(config)
        else:
            # 手工设计 5 个关卡
            level_configs = [
                # Level 1: 3×3, 一个滤镜将 A 变成 B
                {
                    "cols": 3, "rows": 3,
                    "start": (0, 0), "end": (3, 3),
                    "squares": {(0, 0): SQUARE_A, (2, 0): SQUARE_B, (0, 2): SQUARE_A},
                    "filters": {(0, 0): SQUARE_B},  # 将 (0,0) 的 A 变为 B
                },
                # Level 2: 3×3, 两个滤镜
                {
                    "cols": 3, "rows": 3,
                    "start": (0, 0), "end": (0, 3),
                    "squares": {(0, 1): SQUARE_A, (2, 1): SQUARE_B, (1, 0): SQUARE_B},
                    "filters": {(0, 1): SQUARE_B},  # A->B
                },
                # Level 3: 4×3, 颜色交换
                {
                    "cols": 4, "rows": 3,
                    "start": (0, 0), "end": (4, 3),
                    "squares": {(0, 0): SQUARE_A, (1, 0): SQUARE_B,
                                (2, 2): SQUARE_A, (3, 2): SQUARE_B},
                    "filters": {(1, 0): SQUARE_A},  # B->A
                },
                # Level 4: 4×4, 三色
                {
                    "cols": 4, "rows": 4,
                    "start": (0, 0), "end": (4, 4),
                    "squares": {(0, 0): SQUARE_A, (3, 0): SQUARE_B,
                                (1, 2): SQUARE_C, (2, 2): SQUARE_A},
                    "filters": {(2, 2): SQUARE_C},  # A->C
                },
                # Level 5: 4×4, 多滤镜
                {
                    "cols": 4, "rows": 4,
                    "start": (0, 0), "end": (4, 4),
                    "squares": {(0, 0): SQUARE_A, (3, 0): SQUARE_B,
                                (0, 3): SQUARE_B, (3, 3): SQUARE_A},
                    "filters": {(0, 0): SQUARE_B, (3, 3): SQUARE_B},
                },
            ]

        levels = []
        for i, config in enumerate(level_configs):
            grid = WitnessGrid(config["cols"], config["rows"])
            frame = grid.render_grid()

            grid.draw_start(frame, config["start"])
            grid.draw_end(frame, config["end"])

            for cell, color in config["squares"].items():
                grid.draw_cell_symbol(frame, cell, color)

            # 绘制滤镜标记（在有滤镜的格子边缘画栗色边框）
            for cell in config["filters"]:
                cx, cy = grid.cell_center_pixel(*cell)
                half = 3
                for dx in range(-half, half + 1):
                    for dy in [-half, half]:
                        px, py = cx + dx, cy + dy
                        if 0 <= px < 64 and 0 <= py < 64:
                            frame[py][px] = FILTER_COLOR
                for dy in range(-half, half + 1):
                    for dx in [-half, half]:
                        px, py = cx + dx, cy + dy
                        if 0 <= px < 64 and 0 <= py < 64:
                            frame[py][px] = FILTER_COLOR

            if not config.get("validated", True):
                grid.draw_unvalidated_indicator(frame)

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
                    "squares": {f"{k[0]},{k[1]}": v for k, v in config["squares"].items()},
                    "filters": {f"{k[0]},{k[1]}": v for k, v in config["filters"].items()},
                    "validated": config.get("validated", True),
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
        self._squares = {}
        for k, v in data["squares"].items():
            parts = k.split(",")
            self._squares[(int(parts[0]), int(parts[1]))] = v
        self._filters = {}
        for k, v in data["filters"].items():
            parts = k.split(",")
            self._filters[(int(parts[0]), int(parts[1]))] = v
        self._path = [self._start]

    def _perceived_color(self, cell: Tuple[int, int]) -> Optional[int]:
        """获取格子的感知颜色（应用滤镜后）。"""
        if cell not in self._squares:
            return None
        if cell in self._filters:
            return self._filters[cell]
        return self._squares[cell]

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
        if not (0 <= tc <= self._grid.cols and 0 <= tr <= self._grid.rows):
            return False
        fc, fr = from_node
        if abs(fc - tc) + abs(fr - tr) != 1:
            return False
        return True

    def _check_solution(self) -> None:
        if not self._grid:
            return

        if self._path[-1] != self._end:
            self._path = [self._start]
            self._update_display()
            return

        # 区域分割 + 感知颜色检查
        regions = self._grid.path_splits_regions(self._path)
        for region in regions:
            colors_in_region = set()
            for cell in region:
                pc = self._perceived_color(cell)
                if pc is not None:
                    colors_in_region.add(pc)
            if len(colors_in_region) > 1:
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

        for cell, color in self._squares.items():
            self._grid.draw_cell_symbol(frame, cell, color)

        for cell in self._filters:
            cx, cy = self._grid.cell_center_pixel(*cell)
            half = 3
            for dx in range(-half, half + 1):
                for dy in [-half, half]:
                    px, py = cx + dx, cy + dy
                    if 0 <= px < 64 and 0 <= py < 64:
                        frame[py][px] = FILTER_COLOR
            for dy in range(-half, half + 1):
                for dx in [-half, half]:
                    px, py = cx + dx, cy + dy
                    if 0 <= px < 64 and 0 <= py < 64:
                        frame[py][px] = FILTER_COLOR

        for i in range(len(self._path) - 1):
            self._grid.draw_path_segment(frame, self._path[i], self._path[i + 1], path_color)

        if self._path:
            self._grid.draw_dot(frame, self._path[-1], CURSOR_COLOR)

        # 未验证标记
        if not self.current_level._data.get("validated", True):
            self._grid.draw_unvalidated_indicator(frame)

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
