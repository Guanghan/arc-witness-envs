"""
validate.py — IDDFS 求解器 + baseline 校准

为 tw01/tw02/tw04 的 level_config 求解最短路径，
计算 baseline_actions = ceil(shortest_moves * 1.2) + 1（+1 for CONFIRM）。
"""
import math
from typing import List, Tuple, Set, Dict, Optional, FrozenSet
from collections import deque


# ====================================================================
# tw01 PathDots Solver — BFS 求最短路径
# ====================================================================

def solve_tw01(config: dict, timeout: float = 10.0) -> Optional[List[Tuple[int, int]]]:
    """BFS 求解 tw01 PathDots 谜题，返回最短路径（节点序列）。"""
    import time
    t0 = time.time()

    cols = config["cols"]
    rows = config["rows"]
    start = tuple(config["start"])
    end = tuple(config["end"])
    dots = set(tuple(d) for d in config["dots"])

    # 解析 breakpoints
    breakpoints: Set[Tuple[Tuple[int, int], Tuple[int, int]]] = set()
    for bp in config.get("breakpoints", []):
        n1, n2 = tuple(bp[0]), tuple(bp[1])
        breakpoints.add((min(n1, n2), max(n1, n2)))

    # State: (current_node, visited_dots_frozenset)
    # BFS for shortest path
    initial_visited_dots = frozenset({start} & dots)
    initial_state = (start, initial_visited_dots)

    queue = deque()
    queue.append((initial_state, [start]))
    seen = {initial_state}

    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    while queue:
        if time.time() - t0 > timeout:
            return None

        (node, visited_dots), path = queue.popleft()

        for dc, dr in directions:
            nc, nr = node[0] + dc, node[1] + dr
            next_node = (nc, nr)

            if not (0 <= nc <= cols and 0 <= nr <= rows):
                continue
            if next_node in set(path):
                continue

            edge = (min(node, next_node), max(node, next_node))
            if edge in breakpoints:
                continue

            new_visited = visited_dots | ({next_node} & dots)
            new_path = path + [next_node]

            if next_node == end and new_visited == dots:
                return new_path

            new_state = (next_node, new_visited)
            if new_state not in seen:
                seen.add(new_state)
                queue.append((new_state, new_path))

    return None


# ====================================================================
# tw02 ColorSplit Solver — BFS + 区域验证
# ====================================================================

def _path_splits_regions(path: List[Tuple[int, int]], cols: int, rows: int) -> List[Set[Tuple[int, int]]]:
    """根据路径将面板分割为区域（与 witness_grid.py 一致）。"""
    path_edges = set()
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        path_edges.add((min(a, b), max(a, b)))

    visited = set()
    regions = []

    for row in range(rows):
        for col in range(cols):
            cell = (col, row)
            if cell in visited:
                continue

            region = set()
            queue = [cell]
            while queue:
                c = queue.pop(0)
                if c in visited:
                    continue
                visited.add(c)
                region.add(c)

                cc, cr = c
                for dc, dr, edge_n1, edge_n2 in [
                    (-1, 0, (cc, cr), (cc, cr + 1)),
                    (1, 0, (cc + 1, cr), (cc + 1, cr + 1)),
                    (0, -1, (cc, cr), (cc + 1, cr)),
                    (0, 1, (cc, cr + 1), (cc + 1, cr + 1)),
                ]:
                    nc, nr = cc + dc, cr + dr
                    if 0 <= nc < cols and 0 <= nr < rows:
                        edge = (min(edge_n1, edge_n2), max(edge_n1, edge_n2))
                        if edge not in path_edges and (nc, nr) not in visited:
                            queue.append((nc, nr))

            regions.append(region)

    return regions


def _check_colorsplit(path: List[Tuple[int, int]], squares: Dict[Tuple[int, int], int],
                      cols: int, rows: int) -> bool:
    """检查路径是否满足 ColorSplit 约束。"""
    regions = _path_splits_regions(path, cols, rows)
    for region in regions:
        colors_in_region = set()
        for cell in region:
            if cell in squares:
                colors_in_region.add(squares[cell])
        if len(colors_in_region) > 1:
            return False
    return True


def solve_tw02(config: dict, timeout: float = 5.0) -> Optional[List[Tuple[int, int]]]:
    """DFS 求解 tw02 ColorSplit 谜题，带超时。找到最短解。"""
    cols = config["cols"]
    rows = config["rows"]
    start = tuple(config["start"])
    end = tuple(config["end"])

    # 解析 squares
    squares = {}
    for k, v in config["squares"].items():
        parts = k.split(",")
        squares[(int(parts[0]), int(parts[1]))] = v

    import time
    t0 = time.time()
    best_solution = [None]
    best_len = [(cols + 1) * (rows + 1) + 1]

    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    def dfs(path, path_set):
        if time.time() - t0 > timeout:
            return
        if len(path) >= best_len[0]:
            return

        node = path[-1]

        for dc, dr in directions:
            nc, nr = node[0] + dc, node[1] + dr
            next_node = (nc, nr)

            if not (0 <= nc <= cols and 0 <= nr <= rows):
                continue
            if next_node in path_set:
                continue

            path.append(next_node)
            path_set.add(next_node)

            if next_node == end:
                if _check_colorsplit(path, squares, cols, rows):
                    if len(path) < best_len[0]:
                        best_len[0] = len(path)
                        best_solution[0] = list(path)
            else:
                if len(path) < best_len[0] - 1:
                    dfs(path, path_set)

            path.pop()
            path_set.remove(next_node)

    dfs([start], {start})
    return best_solution[0]


# ====================================================================
# tw04 SymDraw Solver — BFS with mirrored moves
# ====================================================================

def solve_tw04(config: dict, timeout: float = 10.0) -> Optional[List[Tuple[int, int]]]:
    """BFS 求解 tw04 SymDraw 谜题，返回 blue 路径。"""
    import time
    t0 = time.time()

    cols = config["cols"]
    rows = config["rows"]
    sym = config["symmetry"]

    blue_start = tuple(config["blue_start"])
    blue_end = tuple(config["blue_end"])
    yellow_start = tuple(config["yellow_start"])
    yellow_end = tuple(config["yellow_end"])
    blue_dots = set(tuple(d) for d in config["blue_dots"])
    yellow_dots = set(tuple(d) for d in config["yellow_dots"])

    def mirror_delta(dc, dr):
        if sym == "horizontal":
            return (-dc, dr)
        elif sym == "vertical":
            return (dc, -dr)
        elif sym == "rotational":
            return (-dc, -dr)
        return (dc, dr)

    def valid_node(n):
        return 0 <= n[0] <= cols and 0 <= n[1] <= rows

    # State: (blue_node, yellow_node, blue_visited_dots, yellow_visited_dots)
    b_init_dots = frozenset({blue_start} & blue_dots)
    y_init_dots = frozenset({yellow_start} & yellow_dots)

    initial = (blue_start, yellow_start, b_init_dots, y_init_dots)
    queue = deque()
    queue.append((initial, [blue_start]))
    seen = {(blue_start, yellow_start, b_init_dots, y_init_dots)}

    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    while queue:
        if time.time() - t0 > timeout:
            return None

        (b_node, y_node, b_visited, y_visited), b_path = queue.popleft()

        for dc, dr in directions:
            b_next = (b_node[0] + dc, b_node[1] + dr)
            ydc, ydr = mirror_delta(dc, dr)
            y_next = (y_node[0] + ydc, y_node[1] + ydr)

            if not valid_node(b_next) or not valid_node(y_next):
                continue
            if b_next in set(b_path):
                continue
            # Check yellow path collision
            y_path = _compute_yellow_path(b_path + [b_next], yellow_start, sym, cols, rows)
            if y_next in set(y_path[:-1]):
                continue
            # Blue and yellow can't be on same node
            if b_next == y_next:
                continue

            new_b_visited = b_visited | ({b_next} & blue_dots)
            new_y_visited = y_visited | ({y_next} & yellow_dots)
            new_b_path = b_path + [b_next]

            # Check win
            if (b_next == blue_end and y_next == yellow_end and
                    new_b_visited == blue_dots and new_y_visited == yellow_dots):
                return new_b_path

            state = (b_next, y_next, new_b_visited, new_y_visited)
            if state not in seen:
                seen.add(state)
                queue.append(((b_next, y_next, new_b_visited, new_y_visited), new_b_path))

    return None


def _compute_yellow_path(blue_path, yellow_start, sym, cols, rows):
    """从 blue 路径计算 yellow 路径。"""
    y_path = [yellow_start]
    for i in range(1, len(blue_path)):
        bc, br = blue_path[i]
        pc, pr = blue_path[i - 1]
        dc, dr = bc - pc, br - pr
        if sym == "horizontal":
            ydc, ydr = -dc, dr
        elif sym == "vertical":
            ydc, ydr = dc, -dr
        elif sym == "rotational":
            ydc, ydr = -dc, -dr
        else:
            ydc, ydr = dc, dr
        last = y_path[-1]
        y_path.append((last[0] + ydc, last[1] + ydr))
    return y_path


# ====================================================================
# Baseline calibration
# ====================================================================

def calibrate_baseline(solution_path: List[Tuple[int, int]]) -> int:
    """计算 baseline_actions。

    baseline = ceil((moves + 1) * 1.2)
    其中 moves = len(path) - 1（路径步数），+1 for CONFIRM
    """
    moves = len(solution_path) - 1  # 移动次数
    total_actions = moves + 1  # +1 for CONFIRM
    baseline = math.ceil(total_actions * 1.2)
    return baseline


def validate_config(config: dict, game_type: str, timeout: float = 5.0) -> dict:
    """验证一个 level_config，返回验证结果。

    Returns:
        {
            "valid": bool,
            "solution": list or None,
            "moves": int,
            "baseline": int,
            "error": str or None,
        }
    """
    solvers = {
        "tw01": solve_tw01,
        "tw02": solve_tw02,
        "tw04": solve_tw04,
    }

    solver = solvers.get(game_type)
    if not solver:
        return {"valid": False, "solution": None, "moves": 0, "baseline": 0,
                "error": f"Unknown game type: {game_type}"}

    try:
        solution = solver(config, timeout=timeout)
    except Exception as e:
        return {"valid": False, "solution": None, "moves": 0, "baseline": 0,
                "error": str(e)}

    if solution is None:
        return {"valid": False, "solution": None, "moves": 0, "baseline": 0,
                "error": "No solution found"}

    moves = len(solution) - 1
    baseline = calibrate_baseline(solution)

    return {
        "valid": True,
        "solution": solution,
        "moves": moves,
        "baseline": baseline,
        "error": None,
    }


def solution_to_actions(solution: List[Tuple[int, int]]) -> List[int]:
    """将路径节点序列转换为动作 ID 序列（用于 test_games.py）。

    ACTION1=UP(dr=-1), ACTION2=DOWN(dr=+1), ACTION3=LEFT(dc=-1), ACTION4=RIGHT(dc=+1), ACTION5=CONFIRM
    """
    actions = []
    for i in range(1, len(solution)):
        pc, pr = solution[i - 1]
        nc, nr = solution[i]
        dc, dr = nc - pc, nr - pr
        if dr == -1:
            actions.append(1)  # UP
        elif dr == 1:
            actions.append(2)  # DOWN
        elif dc == -1:
            actions.append(3)  # LEFT
        elif dc == 1:
            actions.append(4)  # RIGHT
    actions.append(5)  # CONFIRM
    return actions


if __name__ == "__main__":
    # Test with existing hardcoded levels
    print("=== Testing tw01 solver ===")
    tw01_configs = [
        {"cols": 3, "rows": 3, "start": [0, 0], "end": [3, 0], "dots": [[2, 0]]},
        {"cols": 3, "rows": 3, "start": [0, 0], "end": [3, 0], "dots": [[1, 1]]},
        {"cols": 4, "rows": 4, "start": [0, 0], "end": [4, 4], "dots": [[2, 0], [2, 4]]},
    ]
    for i, config in enumerate(tw01_configs):
        result = validate_config(config, "tw01")
        print(f"  Level {i+1}: valid={result['valid']}, moves={result['moves']}, "
              f"baseline={result['baseline']}")
        if result['solution']:
            acts = solution_to_actions(result['solution'])
            print(f"    actions={acts}")

    print("\n=== Testing tw02 solver ===")
    tw02_configs = [
        {"cols": 3, "rows": 3, "start": [0, 0], "end": [0, 3],
         "squares": {"0,1": 6, "2,1": 10}},
    ]
    for i, config in enumerate(tw02_configs):
        result = validate_config(config, "tw02")
        print(f"  Level {i+1}: valid={result['valid']}, moves={result['moves']}, "
              f"baseline={result['baseline']}")
        if result['solution']:
            acts = solution_to_actions(result['solution'])
            print(f"    actions={acts}")

    print("\n=== Testing tw04 solver ===")
    tw04_configs = [
        {"cols": 4, "rows": 3, "symmetry": "horizontal",
         "blue_start": [0, 0], "blue_end": [0, 3],
         "yellow_start": [4, 0], "yellow_end": [4, 3],
         "blue_dots": [], "yellow_dots": []},
    ]
    for i, config in enumerate(tw04_configs):
        result = validate_config(config, "tw04")
        print(f"  Level {i+1}: valid={result['valid']}, moves={result['moves']}, "
              f"baseline={result['baseline']}")
        if result['solution']:
            acts = solution_to_actions(result['solution'])
            print(f"    actions={acts}")
