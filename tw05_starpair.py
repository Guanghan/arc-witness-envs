"""
tw05_starpair.py — StarPair: 星星配对谜题

The Witness 星星机制：画线将面板分区，每个区域内每种颜色恰好有 2 个星星。
训练 Agent 的配对推理和区域规划能力。

Core Knowledge: Objectness + Counting — 按颜色配对
ARC-AGI 启示: "每组恰好 N 个"规则
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
)
from typing import List, Tuple, Set, Dict, Optional


class Tw05(ARCBaseGame):
    """StarPair — 星星配对谜题

    规则：从起点画线到终点，路径将面板分区。
    每个区域内每种颜色的星星恰好 2 个。
    """

    def __init__(self, seed: int = 0):
        self._seed = seed
        self._path: List[Tuple[int, int]] = []
        self._grid: Optional[WitnessGrid] = None
        self._start: Tuple[int, int] = (0, 0)
        self._end: Tuple[int, int] = (0, 0)
        self._stars: Dict[Tuple[int, int], int] = {}  # cell -> color

        levels = self._create_levels()
        camera = Camera(background=GRID_BG, letter_box=COLOR_BLACK)
        super().__init__(
            game_id="tw05",
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
            levels_path = os.path.join(_code_dir, "levels", "tw05_levels.json")
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
                    "stars": {
                        tuple(int(x) for x in k.split(",")): v
                        for k, v in cfg["stars"].items()
                    },
                }
                level_configs.append(config)
        else:
            # 硬编码回退：2 个基础关卡
            level_configs = [
                {
                    "cols": 3, "rows": 3,
                    "start": (0, 0), "end": (3, 3),
                    "stars": {(0, 0): SQUARE_A, (1, 0): SQUARE_A,
                              (2, 1): SQUARE_B, (2, 2): SQUARE_B},
                },
                {
                    "cols": 4, "rows": 4,
                    "start": (0, 0), "end": (4, 4),
                    "stars": {(0, 0): SQUARE_A, (1, 2): SQUARE_A,
                              (2, 1): SQUARE_B, (3, 3): SQUARE_B},
                },
            ]

        levels = []
        for i, config in enumerate(level_configs):
            grid = WitnessGrid(config["cols"], config["rows"])
            frame = grid.render_grid()

            grid.draw_start(frame, config["start"])
            grid.draw_end(frame, config["end"])

            for cell, color in config["stars"].items():
                grid.draw_star(frame, cell, color)

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
                    "stars": {f"{k[0]},{k[1]}": v for k, v in config["stars"].items()},
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
        self._stars = {}
        for k, v in data["stars"].items():
            parts = k.split(",")
            self._stars[(int(parts[0]), int(parts[1]))] = v
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

        # 区域星星配对检查
        regions = self._grid.path_splits_regions(self._path)
        for region in regions:
            color_counts: Dict[int, int] = {}
            for cell in region:
                if cell in self._stars:
                    c = self._stars[cell]
                    color_counts[c] = color_counts.get(c, 0) + 1
            for color, count in color_counts.items():
                if count != 2:
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

        for cell, color in self._stars.items():
            self._grid.draw_star(frame, cell, color)

        for i in range(len(self._path) - 1):
            self._grid.draw_path_segment(frame, self._path[i], self._path[i + 1], path_color)

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
