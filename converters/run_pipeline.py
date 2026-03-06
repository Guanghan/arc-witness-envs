#!/usr/bin/env python3
"""
run_pipeline.py — 一键提取 The Witness 社区谜题到我们的游戏格式

用法: python converters/run_pipeline.py [--keep-all] [--max-solve-time 10] [--output-dir levels]

步骤:
1. 从 vendor_ttws/ 解码所有谜题
2. 分类筛选
3. 转换为 level_config 格式
4. BFS/DFS 求解验证 + baseline 校准
5. 按难度排序，选取关卡
6. 输出 JSON 文件 + 自动生成 metadata.json
"""
import sys
import os
import json
import time
import argparse
from typing import List, Dict
from collections import Counter
from datetime import datetime

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)

from ingest_ttws import ingest_all
from filter import filter_all
from to_level_config import convert_puzzle
from validate import validate_config, solution_to_actions, calibrate_baseline


# === 游戏元信息注册表 ===
GAME_REGISTRY = {
    "tw01": {
        "title": "PathDots - 路径必经点",
        "class_name": "Tw01",
        "tags": ["witness", "path-constraint", "spatial-reasoning"],
    },
    "tw02": {
        "title": "ColorSplit - 彩色方块分隔",
        "class_name": "Tw02",
        "tags": ["witness", "partition-constraint", "classification"],
    },
    "tw03": {
        "title": "ShapeFill - 多联骨牌铺满",
        "class_name": "Tw03",
        "tags": ["witness", "tiling", "exact-cover"],
    },
    "tw04": {
        "title": "SymDraw - 对称画线",
        "class_name": "Tw04",
        "tags": ["witness", "symmetry", "dual-control"],
    },
    "tw05": {
        "title": "StarPair - 星星配对",
        "class_name": "Tw05",
        "tags": ["witness", "pairing-constraint", "region-partition"],
    },
    "tw06": {
        "title": "TriCount - 三角形计数",
        "class_name": "Tw06",
        "tags": ["witness", "counting-constraint", "edge-awareness"],
    },
    "tw07": {
        "title": "EraserLogic - 消除逻辑",
        "class_name": "Tw07",
        "tags": ["witness", "meta-reasoning", "error-correction"],
    },
    "tw08": {
        "title": "ComboBasic - 基础组合",
        "class_name": "Tw08",
        "tags": ["witness", "multi-constraint", "squares-stars"],
    },
    "tw09": {
        "title": "CylinderWrap - 圆柱环绕",
        "class_name": "Tw09",
        "tags": ["witness", "topology", "wrap-around"],
    },
    "tw10": {
        "title": "ColorFilter - 颜色滤镜",
        "class_name": "Tw10",
        "tags": ["witness", "perception", "color-transform"],
    },
    "tw11": {
        "title": "MultiRegion - 多约束区域组合",
        "class_name": "Tw11",
        "tags": ["witness", "multi-constraint", "region-combo"],
    },
    "tw12": {
        "title": "HexCombo - 必经点+区域组合",
        "class_name": "Tw12",
        "tags": ["witness", "path-constraint", "region-combo"],
    },
    "tw13": {
        "title": "EraserAll - 全约束消除逻辑",
        "class_name": "Tw13",
        "tags": ["witness", "meta-reasoning", "error-correction", "extended"],
    },
}


def ascii_grid_tw01(config: dict, solution=None) -> str:
    """生成 tw01 ASCII 可视化。"""
    cols, rows = config["cols"], config["rows"]
    start = tuple(config["start"])
    end = tuple(config["end"])
    dots = set(tuple(d) for d in config["dots"])
    path_set = set(tuple(n) for n in solution) if solution else set()

    lines = []
    for r in range(rows + 1):
        line = ""
        for c in range(cols + 1):
            node = (c, r)
            if node == start:
                ch = "S"
            elif node == end:
                ch = "E"
            elif node in dots and node in path_set:
                ch = "*"
            elif node in dots:
                ch = "o"
            elif node in path_set:
                ch = "#"
            else:
                ch = "+"
            line += ch

            if c < cols:
                if solution and (c, r) in path_set and (c + 1, r) in path_set:
                    adjacent = False
                    for i in range(len(solution) - 1):
                        if (tuple(solution[i]) == (c, r) and tuple(solution[i+1]) == (c+1, r)) or \
                           (tuple(solution[i]) == (c+1, r) and tuple(solution[i+1]) == (c, r)):
                            adjacent = True
                            break
                    line += "=" if adjacent else "-"
                else:
                    line += "-"
        lines.append(line)
        if r < rows:
            vline = ""
            for c in range(cols + 1):
                if solution and (c, r) in path_set and (c, r + 1) in path_set:
                    adjacent = False
                    for i in range(len(solution) - 1):
                        if (tuple(solution[i]) == (c, r) and tuple(solution[i+1]) == (c, r+1)) or \
                           (tuple(solution[i]) == (c, r+1) and tuple(solution[i+1]) == (c, r)):
                            adjacent = True
                            break
                    vline += "|" if adjacent else " "
                else:
                    vline += " "
                if c < cols:
                    vline += " "
            lines.append(vline)
    return "\n".join(lines)


def ascii_grid_tw02(config: dict) -> str:
    """生成 tw02 ASCII 可视化。"""
    cols, rows = config["cols"], config["rows"]
    start = tuple(config["start"])
    end = tuple(config["end"])
    squares = {}
    for k, v in config["squares"].items():
        parts = k.split(",")
        squares[(int(parts[0]), int(parts[1]))] = v

    color_chars = {6: "A", 10: "B", 12: "C"}

    lines = []
    for r in range(rows + 1):
        line = ""
        for c in range(cols + 1):
            node = (c, r)
            if node == start:
                ch = "S"
            elif node == end:
                ch = "E"
            else:
                ch = "+"
            line += ch
            if c < cols:
                line += "-"
        lines.append(line)
        if r < rows:
            vline = ""
            for c in range(cols + 1):
                vline += "|"
                if c < cols:
                    cell = (c, r)
                    if cell in squares:
                        vline += color_chars.get(squares[cell], "?")
                    else:
                        vline += " "
            lines.append(vline)
    return "\n".join(lines)


def _generate_metadata(game_id: str, baselines: list, env_dir: str):
    """自动生成 metadata.json。"""
    info = GAME_REGISTRY.get(game_id, {})
    metadata = {
        "game_id": game_id,
        "title": info.get("title", game_id),
        "class_name": info.get("class_name", game_id.capitalize()),
        "tags": info.get("tags", ["witness"]),
        "baseline_actions": baselines,
        "date_downloaded": datetime.now().strftime("%Y-%m-%dT00:00:00Z"),
    }

    game_dir = os.path.join(env_dir, game_id)
    os.makedirs(game_dir, exist_ok=True)
    filepath = os.path.join(game_dir, "metadata.json")
    with open(filepath, "w") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)
    return filepath


def _estimate_baseline(config: dict) -> int:
    """基于网格尺寸估算 baseline（用于 solver 超时的未验证关卡）。

    估算逻辑：最短路径大约 = cols + rows 步，baseline = ceil((moves+1)*1.5)
    比已验证的 1.2 倍数稍宽松，因为我们不知道实际最短路径。
    """
    import math
    cols = config.get("cols", 3)
    rows = config.get("rows", 3)
    estimated_moves = cols + rows  # 最乐观的直线路径
    total_actions = estimated_moves + 1  # +1 for CONFIRM
    return math.ceil(total_actions * 1.5)


def run_pipeline(max_solve_time: float = 10.0, output_dir: str = "levels",
                 levels_per_game: int = 10, keep_all: bool = False) -> dict:
    """运行完整提取管线。"""
    print("=" * 60)
    print("ARC-AGI-3 Witness Puzzle Extraction Pipeline")
    if keep_all:
        print("  Mode: KEEP ALL validated levels")
    print("=" * 60)

    # Step 1: Ingest
    print("\n[1/6] Ingesting puzzles from vendor_ttws/...")
    t0 = time.time()
    all_puzzles = ingest_all()
    print(f"  Decoded: {len(all_puzzles)} puzzles ({time.time()-t0:.1f}s)")

    # Step 2: Filter
    print("\n[2/6] Filtering by game type...")
    filtered = filter_all(all_puzzles)
    for game, ps in sorted(filtered.items()):
        print(f"  {game}: {len(ps)} candidates")

    # Step 3: Convert
    print("\n[3/6] Converting to level_config format...")
    converted = {}
    for game, ps in filtered.items():
        configs = []
        for p in ps:
            config = convert_puzzle(p, game)
            if config:
                configs.append((config, p))
        converted[game] = configs
        print(f"  {game}: {len(configs)} converted")

    # Step 4: Validate + calibrate
    print("\n[4/6] Solving and calibrating baselines...")
    validated = {}
    unvalidated = {}
    stats = {"total_solved": 0, "total_failed": 0}

    for game, configs in sorted(converted.items()):
        valid_levels = []
        unvalid_levels = []
        for config, puzzle in configs:
            t0 = time.time()
            result = validate_config(config, game, timeout=max_solve_time)
            elapsed = time.time() - t0

            if result["valid"]:
                # 多起点：重排 starts 使 solver 选中的起点在首位
                if "starts" in config and result["solution"]:
                    solver_start = list(result["solution"][0])
                    starts = config["starts"]
                    if solver_start in starts and starts[0] != solver_start:
                        starts.remove(solver_start)
                        starts.insert(0, solver_start)
                valid_levels.append({
                    "config": config,
                    "moves": result["moves"],
                    "baseline": result["baseline"],
                    "solution": result["solution"],
                    "actions": solution_to_actions(result["solution"]),
                    "source": f"{puzzle.source}:{puzzle.source_index}",
                    "solve_time": elapsed,
                    "validated": True,
                })
                stats["total_solved"] += 1
            else:
                stats["total_failed"] += 1
                unvalid_levels.append({
                    "config": config,
                    "moves": 0,
                    "baseline": _estimate_baseline(config),
                    "solution": None,
                    "actions": [],
                    "source": f"{puzzle.source}:{puzzle.source_index}",
                    "solve_time": elapsed,
                    "validated": False,
                })
                if elapsed > 0.5:
                    print(f"    {game} [{puzzle.source}:{puzzle.source_index}] "
                          f"FAILED ({elapsed:.1f}s): {result['error']}")

        # Sort by difficulty (moves)
        valid_levels.sort(key=lambda x: x["moves"])
        # Sort unvalidated by grid size (smaller first)
        unvalid_levels.sort(key=lambda x: x["config"]["cols"] * x["config"]["rows"])
        validated[game] = valid_levels
        unvalidated[game] = unvalid_levels
        if valid_levels:
            print(f"  {game}: {len(valid_levels)} validated "
                  f"(moves range: {valid_levels[0]['moves']}-{valid_levels[-1]['moves']})")
        else:
            print(f"  {game}: 0 validated")
        if unvalid_levels:
            print(f"  {game}: {len(unvalid_levels)} unvalidated (solver timeout/fail)")

    print(f"\n  Total solved: {stats['total_solved']}, failed: {stats['total_failed']}")

    # Step 5: Select and export
    effective_count = 0 if keep_all else levels_per_game
    print(f"\n[5/6] Selecting levels and exporting JSON...")
    if keep_all:
        print("  (Keeping ALL validated levels + unvalidated levels)")

    abs_output = os.path.join(os.path.dirname(_here), output_dir)
    os.makedirs(abs_output, exist_ok=True)

    results = {}
    for game, levels in sorted(validated.items()):
        ulevels = unvalidated.get(game, [])

        if not levels and not ulevels:
            print(f"  {game}: NO levels at all!")
            continue

        # Select validated levels
        selected = _select_levels(levels, effective_count) if levels else []

        # Build output
        output = {
            "game": game,
            "total_candidates": len(filtered.get(game, [])),
            "total_validated": len(levels),
            "total_unvalidated": len(ulevels),
            "selected_count": len(selected) + len(ulevels),
            "levels": [],
        }

        # First: validated levels (sorted by difficulty)
        idx = 0
        for level in selected:
            level_entry = {
                "level_index": idx,
                "config": level["config"],
                "baseline": level["baseline"],
                "moves": level["moves"],
                "solution_actions": level["actions"],
                "source": level["source"],
                "validated": True,
            }
            output["levels"].append(level_entry)
            idx += 1

        # Then: unvalidated levels (sorted by grid size)
        for level in ulevels:
            level_entry = {
                "level_index": idx,
                "config": level["config"],
                "baseline": level["baseline"],
                "moves": 0,
                "solution_actions": [],
                "source": level["source"],
                "validated": False,
            }
            output["levels"].append(level_entry)
            idx += 1

        # Write JSON
        filepath = os.path.join(abs_output, f"{game}_levels.json")
        with open(filepath, "w") as f:
            json.dump(output, f, indent=2)

        results[game] = output
        baselines = [l["baseline"] for l in selected]
        n_validated = len(selected)
        n_unvalidated = len(ulevels)
        print(f"  {game}: {n_validated} validated + {n_unvalidated} unvalidated -> {filepath}")
        if baselines:
            print(f"    baselines (validated): {baselines}")
            print(f"    moves (validated): {[l['moves'] for l in selected]}")

    # Step 6: Generate metadata.json for each game
    print(f"\n[6/6] Generating metadata.json files...")
    env_dir = os.path.join(os.path.dirname(_here), "environment_files")
    for game, data in sorted(results.items()):
        # Include baselines for all levels (validated + unvalidated)
        baselines = [l["baseline"] for l in data["levels"]]
        meta_path = _generate_metadata(game, baselines, env_dir)
        print(f"  {game}: {meta_path}")

    return results


def _select_levels(levels: list, count: int, min_moves: int = 3) -> list:
    """从验证通过的关卡中选取关卡。count=0 表示保留全部。"""
    # 过滤太简单的关卡和去重
    filtered = []
    seen_configs = set()
    for level in levels:
        if level["moves"] < min_moves:
            continue
        config_key = json.dumps(level["config"], sort_keys=True)
        if config_key in seen_configs:
            continue
        seen_configs.add(config_key)
        filtered.append(level)

    # count=0 表示保留全部
    if count == 0 or len(filtered) <= count:
        return filtered

    # 均匀采样不同难度
    step = len(filtered) / count
    selected = []
    for i in range(count):
        idx = min(int(i * step), len(filtered) - 1)
        selected.append(filtered[idx])

    return selected


def main():
    parser = argparse.ArgumentParser(description="Extract Witness puzzles for ARC-AGI-3")
    parser.add_argument("--max-solve-time", type=float, default=10.0)
    parser.add_argument("--output-dir", default="levels")
    parser.add_argument("--levels-per-game", type=int, default=10)
    parser.add_argument("--keep-all", action="store_true",
                        help="Keep all validated levels instead of selecting a subset")
    args = parser.parse_args()

    results = run_pipeline(
        max_solve_time=args.max_solve_time,
        output_dir=args.output_dir,
        levels_per_game=args.levels_per_game,
        keep_all=args.keep_all,
    )

    print("\n" + "=" * 60)
    print("Pipeline complete!")
    print("=" * 60)
    total_v = 0
    total_u = 0
    for game, data in sorted(results.items()):
        nv = sum(1 for l in data["levels"] if l.get("validated", True))
        nu = sum(1 for l in data["levels"] if not l.get("validated", True))
        total_v += nv
        total_u += nu
        print(f"  {game}: {nv} validated + {nu} unvalidated "
              f"(from {data['total_candidates']} candidates)")
    print(f"\n  Total: {total_v} validated + {total_u} unvalidated = {total_v + total_u} levels")


if __name__ == "__main__":
    main()
