"""
tw09_cylinderwrap.py — CylinderWrap: Cylinder Wrap Puzzle

The panel wraps horizontally: the left edge connects to the right edge. Paths can cross from one side to the other.
Base constraints use dots (similar to tw01), progressively introducing wrap requirements.
Trains the agent's topological reasoning ability.

Core Knowledge: Topology — Non-planar space
ARC-AGI Insight: Boundary conditions and topological invariants

5 hand-designed levels (no TTWS data).
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
    START_COLOR, END_COLOR, DOT_COLOR, ERROR_COLOR, SUCCESS_COLOR,
    COLOR_BLACK, COLOR_PURPLE,
)
from typing import List, Tuple, Set, Optional


class Tw09(ARCBaseGame):
    """CylinderWrap — Cylinder Wrap Puzzle

    Rules: Draw a line from start to end; the path must pass through all marked dots.
    Special mechanic: The panel wraps horizontally; col=0 and col=cols are connected.
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
            win_score=min(len(levels), 254),
            available_actions=[1, 2, 3, 4, 5],
            seed=seed,
        )

    @staticmethod
    def _load_json_levels() -> Optional[list]:
        """Load levels from JSON. Returns list of dicts with 'config' and 'validated' keys."""
        try:
            import json
            levels_path = os.path.join(_code_dir, "levels", "tw09_levels.json")
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
                    "dots": [tuple(d) for d in cfg["dots"]],
                    "validated": entry.get("validated", True),
                }
                level_configs.append(config)
        else:
            # 5 hand-designed levels
            level_configs = [
                # Level 1: 3x3, start and end on opposite sides, wrap required
                {
                    "cols": 3, "rows": 3,
                    "start": (0, 0), "end": (0, 3),
                    "dots": [(3, 1)],  # must go right to col=3 then wrap back
                },
                # Level 2: 3x3, dot on opposite side
                {
                    "cols": 3, "rows": 3,
                    "start": (0, 0), "end": (3, 3),
                    "dots": [(3, 0), (0, 2)],  # wrap needed to reach dots efficiently
                },
                # Level 3: 4x3, multiple dots
                {
                    "cols": 4, "rows": 3,
                    "start": (0, 0), "end": (0, 3),
                    "dots": [(4, 1), (2, 2)],
                },
                # Level 4: 4x4, complex wrap path
                {
                    "cols": 4, "rows": 4,
                    "start": (0, 0), "end": (4, 4),
                    "dots": [(4, 0), (0, 2), (4, 3)],
                },
                # Level 5: 5x4, requires multiple wraps
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

            # Draw wrap indicators (mark left and right edges with purple)
            for row in range(config["rows"] + 1):
                # Left edge
                lx, ly = grid.node_to_pixel(0, row)
                if 0 <= lx - 1 < 64 and 0 <= ly < 64:
                    frame[ly][lx - 1] = COLOR_PURPLE
                # Right edge
                rx, ry = grid.node_to_pixel(config["cols"], row)
                if 0 <= rx + 1 < 64 and 0 <= ry < 64:
                    frame[ry][rx + 1] = COLOR_PURPLE

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
                    "dots": config["dots"],
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

            # Wrap logic: horizontal wrapping
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
        # Horizontal range is 0..cols (already handled after wrap), vertical range is normal
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

        # Wrap indicators
        for row in range(self._grid.rows + 1):
            lx, ly = self._grid.node_to_pixel(0, row)
            if 0 <= lx - 1 < 64 and 0 <= ly < 64:
                frame[ly][lx - 1] = COLOR_PURPLE
            rx, ry = self._grid.node_to_pixel(self._grid.cols, row)
            if 0 <= rx + 1 < 64 and 0 <= ry < 64:
                frame[ry][rx + 1] = COLOR_PURPLE

        for i in range(len(self._path) - 1):
            n1, n2 = self._path[i], self._path[i + 1]
            # For wrap edges (crossing left-right boundary), draw in two segments
            if abs(n1[0] - n2[0]) > 1:
                # Wrap edge: draw to edge on both sides
                pass  # Simplified: skip drawing wrap edge connections
            else:
                self._grid.draw_path_segment(frame, n1, n2, path_color)

        if self._path:
            self._grid.draw_dot(frame, self._path[-1], CURSOR_COLOR)

        # Redraw start so it always appears green above the cursor
        self._grid.draw_start(frame, self._start)

        # Unvalidated indicator
        if not self.current_level._data.get("validated", True):
            self._grid.draw_unvalidated_indicator(frame)

        # Update background sprite
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
