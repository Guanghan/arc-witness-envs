"""
tw11_multiregion.py — MultiRegion: 多约束区域组合谜题

同时满足 2+ 种区域约束（squares/stars/triangles/tetris 的任意组合）。
训练 Agent 同时推理多种约束的能力。

Core Knowledge: Multi-constraint reasoning
ARC-AGI 启示: 同时满足多条规则
"""

import sys
import os
try:
    _code_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
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
    COLOR_BLACK, SQUARE_A, SQUARE_B, SQUARE_C, POLY_COLOR, TRI_COLOR,
)
from typing import List, Tuple, Set, Dict, Optional


def _rotations(shape):
    """生成形状的所有旋转。"""
    shapes = [shape]
    current = shape
    for _ in range(3):
        current = [(y, -x) for x, y in current]
        min_x = min(x for x, y in current)
        min_y = min(y for x, y in current)
        current = [(x - min_x, y - min_y) for x, y in current]
        current.sort()
        if current not in shapes:
            shapes.append(current)
    return shapes


def _exact_cover(shapes, region_cells, placed, idx):
    """回溯检查形状能否精确覆盖区域。"""
    remaining = region_cells - placed
    if not remaining:
        return idx >= len(shapes)
    if idx >= len(shapes):
        return len(remaining) == 0

    shape_info = shapes[idx]
    cells = shape_info["cells"]
    is_rotated = shape_info["rotated"]
    is_negative = shape_info["negative"]

    if is_negative:
        return _exact_cover(shapes, region_cells, placed, idx + 1)

    variants = _rotations(cells) if is_rotated else [cells]
    anchor = min(remaining)

    for variant in variants:
        for ref in variant:
            offset_x = anchor[0] - ref[0]
            offset_y = anchor[1] - ref[1]
            placed_cells = [(x + offset_x, y + offset_y) for x, y in variant]
            placed_set = set(placed_cells)

            if all(c in region_cells and c not in placed for c in placed_cells):
                new_placed = placed | placed_set
                if _exact_cover(shapes, region_cells, new_placed, idx + 1):
                    return True

    return False


class Tw11(ARCBaseGame):
    """MultiRegion — 多约束区域组合谜题

    规则：从起点画线到终点，路径将面板分区。
    同时满足所有存在的区域约束（squares/stars/triangles/tetris 任意组合，至少 2 种）。
    """

    def __init__(self, seed: int = 0):
        self._seed = seed
        self._path: List[Tuple[int, int]] = []
        self._grid: Optional[WitnessGrid] = None
        self._starts: List[Tuple[int, int]] = [(0, 0)]
        self._start: Tuple[int, int] = (0, 0)
        self._end: Tuple[int, int] = (0, 0)
        self._squares: Dict[Tuple[int, int], int] = {}
        self._stars: Dict[Tuple[int, int], int] = {}
        self._triangles: Dict[Tuple[int, int], int] = {}
        self._tetris: Dict[Tuple[int, int], dict] = {}
        self._breakpoints: Set[Tuple[Tuple[int, int], Tuple[int, int]]] = set()

        levels = self._create_levels()
        camera = Camera(background=GRID_BG, letter_box=COLOR_BLACK)
        super().__init__(
            game_id="tw11",
            levels=levels,
            camera=camera,
            win_score=min(len(levels), 254),
            available_actions=[1, 2, 3, 4, 5],
            seed=seed,
        )

    @staticmethod
    def _load_json_levels() -> Optional[list]:
        try:
            import json
            levels_path = os.path.join(_code_dir, "levels", "tw11_levels.json")
            if os.path.exists(levels_path):
                with open(levels_path) as f:
                    data = json.load(f)
                return [{"config": entry["config"], "validated": entry.get("validated", True)} for entry in data["levels"]]
        except Exception:
            pass
        return None

    @staticmethod
    def _parse_starts(cfg: dict) -> List[Tuple[int, int]]:
        if "starts" in cfg:
            return [tuple(s) for s in cfg["starts"]]
        return [tuple(cfg["start"])]

    def _create_levels(self) -> List[Level]:
        json_entries = self._load_json_levels()
        if json_entries:
            level_configs = []
            for entry in json_entries:
                cfg = entry["config"]
                config = {
                    "cols": cfg["cols"],
                    "rows": cfg["rows"],
                    "starts": self._parse_starts(cfg),
                    "end": tuple(cfg["end"]),
                    "squares": {
                        tuple(int(x) for x in k.split(",")): v
                        for k, v in cfg.get("squares", {}).items()
                    },
                    "stars": {
                        tuple(int(x) for x in k.split(",")): v
                        for k, v in cfg.get("stars", {}).items()
                    },
                    "triangles": {
                        tuple(int(x) for x in k.split(",")): v
                        for k, v in cfg.get("triangles", {}).items()
                    },
                    "validated": entry.get("validated", True),
                }
                # Parse tetris
                if "tetris" in cfg:
                    tetris = {}
                    for k, v in cfg["tetris"].items():
                        parts = k.split(",")
                        cell = (int(parts[0]), int(parts[1]))
                        tetris[cell] = {
                            "shape": [tuple(s) for s in v["shape"]],
                            "rotated": v.get("rotated", False),
                            "negative": v.get("negative", False),
                        }
                    config["tetris"] = tetris
                if "breakpoints" in cfg:
                    config["breakpoints"] = [
                        (tuple(bp[0]), tuple(bp[1])) for bp in cfg["breakpoints"]
                    ]
                level_configs.append(config)
        else:
            # 硬编码回退
            level_configs = [
                {
                    "cols": 4, "rows": 4,
                    "starts": [(0, 0)], "end": (4, 4),
                    "squares": {(0, 0): SQUARE_A, (3, 0): SQUARE_B},
                    "stars": {(1, 2): SQUARE_A, (2, 2): SQUARE_A,
                              (1, 3): SQUARE_B, (2, 3): SQUARE_B},
                    "triangles": {},
                },
            ]

        levels = []
        for i, config in enumerate(level_configs):
            grid = WitnessGrid(config["cols"], config["rows"])
            frame = grid.render_grid()

            for s in config["starts"]:
                grid.draw_start(frame, s)
            grid.draw_end(frame, config["end"])

            for cell, color in config.get("squares", {}).items():
                grid.draw_cell_symbol(frame, cell, color)
            for cell, color in config.get("stars", {}).items():
                grid.draw_star(frame, cell, color)
            for cell, count in config.get("triangles", {}).items():
                grid.draw_triangle(frame, cell, count, TRI_COLOR)
            for cell, t in config.get("tetris", {}).items():
                grid.draw_polyomino(frame, cell, t["shape"], POLY_COLOR)

            for bp in config.get("breakpoints", []):
                grid.draw_breakpoint(frame, bp[0], bp[1])

            if not config.get("validated", True):
                grid.draw_unvalidated_indicator(frame)

            bg_sprite = Sprite(
                pixels=frame, name="grid_bg",
                x=0, y=0, layer=-10,
                blocking=BlockingMode.NOT_BLOCKED,
                interaction=InteractionMode.INTANGIBLE,
                tags=["sys_static"],
            )

            sx, sy = grid.node_to_pixel(*config["starts"][0])
            cursor_sprite = Sprite(
                pixels=[[CURSOR_COLOR]], name="cursor",
                x=sx, y=sy, layer=10,
                blocking=BlockingMode.NOT_BLOCKED,
                interaction=InteractionMode.TANGIBLE,
            )

            level_data = {
                "cols": config["cols"],
                "rows": config["rows"],
                "starts": config["starts"],
                "end": config["end"],
                "squares": {f"{k[0]},{k[1]}": v for k, v in config.get("squares", {}).items()},
                "stars": {f"{k[0]},{k[1]}": v for k, v in config.get("stars", {}).items()},
                "triangles": {f"{k[0]},{k[1]}": v for k, v in config.get("triangles", {}).items()},
                "validated": config.get("validated", True),
            }
            if "tetris" in config:
                level_data["tetris"] = {
                    f"{cell[0]},{cell[1]}": {
                        "shape": [list(s) for s in t["shape"]],
                        "rotated": t["rotated"],
                        "negative": t["negative"],
                    }
                    for cell, t in config["tetris"].items()
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
        data = level._data
        self._grid = WitnessGrid(data["cols"], data["rows"])
        if "starts" in data:
            self._starts = [tuple(s) for s in data["starts"]]
        else:
            self._starts = [tuple(data["start"])]
        self._start = self._starts[0]
        self._end = tuple(data["end"])
        self._squares = {}
        for k, v in data.get("squares", {}).items():
            parts = k.split(",")
            self._squares[(int(parts[0]), int(parts[1]))] = v
        self._stars = {}
        for k, v in data.get("stars", {}).items():
            parts = k.split(",")
            self._stars[(int(parts[0]), int(parts[1]))] = v
        self._triangles = {}
        for k, v in data.get("triangles", {}).items():
            parts = k.split(",")
            self._triangles[(int(parts[0]), int(parts[1]))] = v
        self._tetris = {}
        for k, v in data.get("tetris", {}).items():
            parts = k.split(",")
            cell = (int(parts[0]), int(parts[1]))
            self._tetris[cell] = {
                "shape": [tuple(s) for s in v["shape"]],
                "rotated": v.get("rotated", False),
                "negative": v.get("negative", False),
            }
        self._breakpoints = set()
        for bp in data.get("breakpoints", []):
            n1, n2 = tuple(bp[0]), tuple(bp[1])
            self._breakpoints.add((min(n1, n2), max(n1, n2)))
        self._path = [self._start]

    def _try_auto_select_start(self, dc: int, dr: int) -> bool:
        if len(self._path) != 1 or len(self._starts) <= 1:
            return False
        for alt in self._starts:
            alt_target = (alt[0] + dc, alt[1] + dr)
            if self._is_valid_move(alt, alt_target):
                self._start = alt
                self._path = [alt]
                return True
        return False

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

            if not self._is_valid_move(current, target):
                if self._try_auto_select_start(dc, dr):
                    current = self._path[-1]
                    target = (current[0] + dc, current[1] + dr)
                else:
                    self.complete_action()
                    return

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
        edge = (min(from_node, to_node), max(from_node, to_node))
        if edge in self._breakpoints:
            return False
        return True

    def _check_solution(self) -> None:
        if not self._grid:
            return

        if self._path[-1] != self._end:
            self._start = self._starts[0]
            self._path = [self._start]
            self._update_display()
            return

        regions = self._grid.path_splits_regions(self._path)
        path_edges = self._grid.path_to_edges(self._path)

        for region in regions:
            # 方块同色检查
            if self._squares:
                sq_colors = set()
                for cell in region:
                    if cell in self._squares:
                        sq_colors.add(self._squares[cell])
                if len(sq_colors) > 1:
                    self._start = self._starts[0]
                    self._path = [self._start]
                    self._update_display()
                    return

            # 星星配对检查
            if self._stars:
                star_counts: Dict[int, int] = {}
                for cell in region:
                    if cell in self._stars:
                        c = self._stars[cell]
                        star_counts[c] = star_counts.get(c, 0) + 1
                for color, count in star_counts.items():
                    if count != 2:
                        self._start = self._starts[0]
                        self._path = [self._start]
                        self._update_display()
                        return

            # 三角形计数检查
            if self._triangles:
                for cell in region:
                    if cell in self._triangles:
                        actual = self._grid.cell_edge_count(cell, path_edges)
                        if actual != self._triangles[cell]:
                            self._start = self._starts[0]
                            self._path = [self._start]
                            self._update_display()
                            return

            # tetris 铺砖检查
            if self._tetris:
                shapes_in_region = []
                total_positive_area = 0
                total_negative_area = 0

                for cell in region:
                    if cell in self._tetris:
                        t = self._tetris[cell]
                        is_negative = t.get("negative", False)
                        shapes_in_region.append({
                            "cells": sorted(t["shape"]),
                            "rotated": t.get("rotated", False),
                            "negative": is_negative,
                        })
                        if is_negative:
                            total_negative_area += len(t["shape"])
                        else:
                            total_positive_area += len(t["shape"])

                if shapes_in_region:
                    expected_area = total_positive_area - total_negative_area
                    if expected_area != len(region):
                        self._start = self._starts[0]
                        self._path = [self._start]
                        self._update_display()
                        return

                    positive_shapes = [s for s in shapes_in_region if not s["negative"]]
                    if not _exact_cover(positive_shapes, set(region), set(), 0):
                        self._start = self._starts[0]
                        self._path = [self._start]
                        self._update_display()
                        return

        self._update_display(path_color=SUCCESS_COLOR)
        self.next_level()

    def _update_display(self, path_color: int = PATH_COLOR) -> None:
        if not self._grid:
            return

        frame = self._grid.render_grid()
        for s in self._starts:
            self._grid.draw_start(frame, s)
        self._grid.draw_end(frame, self._end)

        for cell, color in self._squares.items():
            self._grid.draw_cell_symbol(frame, cell, color)
        for cell, color in self._stars.items():
            self._grid.draw_star(frame, cell, color)
        for cell, count in self._triangles.items():
            self._grid.draw_triangle(frame, cell, count, TRI_COLOR)
        for cell, t in self._tetris.items():
            self._grid.draw_polyomino(frame, cell, t["shape"], POLY_COLOR)

        for bp in self._breakpoints:
            self._grid.draw_breakpoint(frame, bp[0], bp[1])

        for i in range(len(self._path) - 1):
            self._grid.draw_path_segment(frame, self._path[i], self._path[i + 1], path_color)

        if self._path:
            self._grid.draw_dot(frame, self._path[-1], CURSOR_COLOR)

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
