"""
tw03_shapefill.py — ShapeFill: 多联骨牌铺满谜题

The Witness 多联骨牌机制：画线将面板分区后，每区域的多联骨牌必须精确铺满。
训练 Agent 的空间推理和精确覆盖能力。

Core Knowledge: Objectness + Geometry — 形状匹配与放置
ARC-AGI 启示: 拼图/铺砖操作
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
    COLOR_BLACK, POLY_COLOR,
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


class Tw03(ARCBaseGame):
    """ShapeFill — 多联骨牌铺满谜题

    规则：从起点画线到终点，路径将面板分区。
    每个区域的多联骨牌必须精确铺满（无空隙无重叠）。
    """

    def __init__(self, seed: int = 0):
        self._seed = seed
        self._path: List[Tuple[int, int]] = []
        self._grid: Optional[WitnessGrid] = None
        self._start: Tuple[int, int] = (0, 0)
        self._end: Tuple[int, int] = (0, 0)
        self._tetris: Dict[Tuple[int, int], dict] = {}

        levels = self._create_levels()
        camera = Camera(background=GRID_BG, letter_box=COLOR_BLACK)
        super().__init__(
            game_id="tw03",
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
            levels_path = os.path.join(_code_dir, "levels", "tw03_levels.json")
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
                tetris = {}
                for k, v in cfg["tetris"].items():
                    parts = k.split(",")
                    cell = (int(parts[0]), int(parts[1]))
                    tetris[cell] = {
                        "shape": [tuple(s) for s in v["shape"]],
                        "rotated": v.get("rotated", False),
                        "negative": v.get("negative", False),
                    }
                config = {
                    "cols": cfg["cols"],
                    "rows": cfg["rows"],
                    "start": tuple(cfg["start"]),
                    "end": tuple(cfg["end"]),
                    "tetris": tetris,
                }
                level_configs.append(config)
        else:
            # 硬编码回退：简单 2×2 方块
            level_configs = [
                {
                    "cols": 3, "rows": 3,
                    "start": (0, 0), "end": (3, 3),
                    "tetris": {
                        (0, 0): {"shape": [(0, 0), (1, 0), (0, 1), (1, 1)], "rotated": False, "negative": False},
                        (2, 0): {"shape": [(0, 0), (0, 1)], "rotated": False, "negative": False},
                    },
                },
            ]

        levels = []
        for i, config in enumerate(level_configs):
            grid = WitnessGrid(config["cols"], config["rows"])
            frame = grid.render_grid()

            grid.draw_start(frame, config["start"])
            grid.draw_end(frame, config["end"])

            for cell, t in config["tetris"].items():
                grid.draw_polyomino(frame, cell, t["shape"], POLY_COLOR)

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

            # Serialize tetris for level data
            tetris_data = {}
            for cell, t in config["tetris"].items():
                tetris_data[f"{cell[0]},{cell[1]}"] = {
                    "shape": [list(s) for s in t["shape"]],
                    "rotated": t["rotated"],
                    "negative": t["negative"],
                }

            level = Level(
                sprites=[bg_sprite, cursor_sprite],
                grid_size=(64, 64),
                data={
                    "cols": config["cols"],
                    "rows": config["rows"],
                    "start": config["start"],
                    "end": config["end"],
                    "tetris": tetris_data,
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
        self._tetris = {}
        for k, v in data["tetris"].items():
            parts = k.split(",")
            cell = (int(parts[0]), int(parts[1]))
            self._tetris[cell] = {
                "shape": [tuple(s) for s in v["shape"]],
                "rotated": v.get("rotated", False),
                "negative": v.get("negative", False),
            }
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

        # 区域铺砖检查
        regions = self._grid.path_splits_regions(self._path)
        for region in regions:
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

            if not shapes_in_region:
                continue

            expected_area = total_positive_area - total_negative_area
            if expected_area != len(region):
                self._path = [self._start]
                self._update_display()
                return

            positive_shapes = [s for s in shapes_in_region if not s["negative"]]
            if not _exact_cover(positive_shapes, set(region), set(), 0):
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

        for cell, t in self._tetris.items():
            self._grid.draw_polyomino(frame, cell, t["shape"], POLY_COLOR)

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
