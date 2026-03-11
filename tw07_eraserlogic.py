"""
tw07_eraserlogic.py — EraserLogic: 消除逻辑谜题

The Witness 消除符号(Y)机制：消除符号吸收约束违反。
每个区域：消除符号数 = 约束违反数。
训练 Agent 的元推理能力——推理约规则的例外。

Core Knowledge: Meta-reasoning — 规则的例外
ARC-AGI 启示: 错误修正模式
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
    COLOR_BLACK, SQUARE_A, SQUARE_B, SQUARE_C, ERASER_COLOR, TRI_COLOR,
)
from typing import List, Tuple, Set, Dict, Optional


class Tw07(ARCBaseGame):
    """EraserLogic — 消除逻辑谜题

    规则：从起点画线到终点，路径将面板分区。
    消除符号吸收约束违反：每个区域的消除符号数 = 违反数。
    """

    def __init__(self, seed: int = 0):
        self._seed = seed
        self._path: List[Tuple[int, int]] = []
        self._grid: Optional[WitnessGrid] = None
        self._starts: List[Tuple[int, int]] = [(0, 0)]
        self._start: Tuple[int, int] = (0, 0)
        self._end: Tuple[int, int] = (0, 0)
        self._erasers: Set[Tuple[int, int]] = set()
        self._squares: Dict[Tuple[int, int], int] = {}
        self._stars: Dict[Tuple[int, int], int] = {}
        self._triangles: Dict[Tuple[int, int], int] = {}
        self._breakpoints: Set[Tuple[Tuple[int, int], Tuple[int, int]]] = set()

        levels = self._create_levels()
        camera = Camera(background=GRID_BG, letter_box=COLOR_BLACK)
        super().__init__(
            game_id="tw07",
            levels=levels,
            camera=camera,
            win_score=min(len(levels), 254),
            available_actions=[1, 2, 3, 4, 5],
            seed=seed,
        )

    @staticmethod
    def _parse_starts(cfg: dict) -> List[Tuple[int, int]]:
        """从 config 解析起点列表。支持 'starts' (多起点) 和 'start' (单起点)。"""
        if "starts" in cfg:
            return [tuple(s) for s in cfg["starts"]]
        return [tuple(cfg["start"])]

    @staticmethod
    def _load_json_levels() -> Optional[list]:
        """Load levels from JSON file.

        Returns a list of dicts with keys 'config' and 'validated'.
        """
        try:
            import json
            levels_path = os.path.join(_code_dir, "levels", "tw07_levels.json")
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
                starts = self._parse_starts(cfg)
                config = {
                    "cols": cfg["cols"],
                    "rows": cfg["rows"],
                    "starts": starts,
                    "end": tuple(cfg["end"]),
                    "erasers": set(tuple(e) for e in cfg["erasers"]),
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
                if "breakpoints" in cfg:
                    config["breakpoints"] = [
                        (tuple(bp[0]), tuple(bp[1])) for bp in cfg["breakpoints"]
                    ]
                level_configs.append(config)
        else:
            # 硬编码回退：方块 + 消除
            level_configs = [
                {
                    "cols": 3, "rows": 3,
                    "starts": [(0, 0)], "end": (3, 3),
                    "erasers": {(1, 1)},
                    "squares": {(0, 0): SQUARE_A, (2, 0): SQUARE_B, (0, 2): SQUARE_A},
                    "stars": {},
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

            for cell, color in config["squares"].items():
                grid.draw_cell_symbol(frame, cell, color)
            for cell, color in config["stars"].items():
                grid.draw_star(frame, cell, color)
            for cell, count in config["triangles"].items():
                grid.draw_triangle(frame, cell, count, TRI_COLOR)
            for cell in config["erasers"]:
                grid.draw_eraser(frame, cell, ERASER_COLOR)

            # 绘制断边
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
                    "erasers": [list(e) for e in config["erasers"]],
                    "squares": {f"{k[0]},{k[1]}": v for k, v in config["squares"].items()},
                    "stars": {f"{k[0]},{k[1]}": v for k, v in config["stars"].items()},
                    "triangles": {f"{k[0]},{k[1]}": v for k, v in config["triangles"].items()},
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
        data = level._data
        self._grid = WitnessGrid(data["cols"], data["rows"])
        if "starts" in data:
            self._starts = [tuple(s) for s in data["starts"]]
        else:
            self._starts = [tuple(data["start"])]
        self._start = self._starts[0]
        self._end = tuple(data["end"])
        self._erasers = set(tuple(e) for e in data["erasers"])
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
        self._breakpoints = set()
        for bp in data.get("breakpoints", []):
            n1, n2 = tuple(bp[0]), tuple(bp[1])
            self._breakpoints.add((min(n1, n2), max(n1, n2)))
        self._path = [self._start]

    def _try_auto_select_start(self, dc: int, dr: int) -> bool:
        """多起点时，尝试根据第一步方向自动选择起点。"""
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

            # 多起点：尝试自动切换起点
            if not self._is_valid_move(current, target):
                if self._try_auto_select_start(dc, dr):
                    current = self._path[-1]
                    target = (current[0] + dc, current[1] + dr)
                else:
                    self.complete_action()
                    return

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

    def _count_violations(self, region):
        """计算区域内的约束违反数。"""
        violations = 0
        path_edges = self._grid.path_to_edges(self._path) if self._grid else set()

        # 方块多色违反
        if self._squares:
            colors = set()
            for cell in region:
                if cell in self._squares:
                    colors.add(self._squares[cell])
            if len(colors) > 1:
                violations += len(colors) - 1

        # 星星配对违反
        if self._stars:
            color_counts: Dict[int, int] = {}
            for cell in region:
                if cell in self._stars:
                    c = self._stars[cell]
                    color_counts[c] = color_counts.get(c, 0) + 1
            for count in color_counts.values():
                if count != 2:
                    violations += abs(count - 2)

        # 三角形计数违反
        if self._triangles:
            for cell in region:
                if cell in self._triangles:
                    actual = self._grid.cell_edge_count(cell, path_edges) if self._grid else 0
                    if actual != self._triangles[cell]:
                        violations += 1

        return violations

    def _check_solution(self) -> None:
        if not self._grid:
            return

        if self._path[-1] != self._end:
            self._start = self._starts[0]
            self._path = [self._start]
            self._update_display()
            return

        regions = self._grid.path_splits_regions(self._path)

        for region in regions:
            eraser_count = sum(1 for cell in region if cell in self._erasers)
            violations = self._count_violations(region)
            if violations != eraser_count:
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
        for cell in self._erasers:
            self._grid.draw_eraser(frame, cell, ERASER_COLOR)

        # 绘制断边
        for bp in self._breakpoints:
            self._grid.draw_breakpoint(frame, bp[0], bp[1])

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
