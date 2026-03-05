"""
tw06_tricount.py — TriCount: 三角形计数谜题

The Witness 三角形机制：格子中的三角形数 N 表示路径必须经过该格子恰好 N 条边。
训练 Agent 的边感知和精确路径规划能力。

Core Knowledge: Numbers + Geometry — 路径与格子边界的关系
ARC-AGI 启示: 计数约束
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
    COLOR_BLACK, TRI_COLOR,
)
from typing import List, Tuple, Set, Dict, Optional


class Tw06(ARCBaseGame):
    """TriCount — 三角形计数谜题

    规则：从起点画线到终点。含 N 个三角形的格子，
    路径必须经过该格子恰好 N 条边。
    """

    def __init__(self, seed: int = 0):
        self._seed = seed
        self._path: List[Tuple[int, int]] = []
        self._grid: Optional[WitnessGrid] = None
        self._start: Tuple[int, int] = (0, 0)
        self._end: Tuple[int, int] = (0, 0)
        self._triangles: Dict[Tuple[int, int], int] = {}  # cell -> count

        levels = self._create_levels()
        camera = Camera(background=GRID_BG, letter_box=COLOR_BLACK)
        super().__init__(
            game_id="tw06",
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
            levels_path = os.path.join(_code_dir, "levels", "tw06_levels.json")
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
                    "triangles": {
                        tuple(int(x) for x in k.split(",")): v
                        for k, v in cfg["triangles"].items()
                    },
                }
                level_configs.append(config)
        else:
            # 硬编码回退
            level_configs = [
                {
                    "cols": 3, "rows": 3,
                    "start": (0, 0), "end": (3, 3),
                    "triangles": {(1, 1): 2},
                },
                {
                    "cols": 3, "rows": 3,
                    "start": (0, 0), "end": (3, 3),
                    "triangles": {(0, 0): 1, (2, 2): 3},
                },
            ]

        levels = []
        for i, config in enumerate(level_configs):
            grid = WitnessGrid(config["cols"], config["rows"])
            frame = grid.render_grid()

            grid.draw_start(frame, config["start"])
            grid.draw_end(frame, config["end"])

            for cell, count in config["triangles"].items():
                grid.draw_triangle(frame, cell, count, TRI_COLOR)

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
                    "triangles": {f"{k[0]},{k[1]}": v for k, v in config["triangles"].items()},
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
        self._triangles = {}
        for k, v in data["triangles"].items():
            parts = k.split(",")
            self._triangles[(int(parts[0]), int(parts[1]))] = v
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

        # 三角形边计数检查
        path_edges = self._grid.path_to_edges(self._path)
        for cell, expected_count in self._triangles.items():
            actual = self._grid.cell_edge_count(cell, path_edges)
            if actual != expected_count:
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

        for cell, count in self._triangles.items():
            self._grid.draw_triangle(frame, cell, count, TRI_COLOR)

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
