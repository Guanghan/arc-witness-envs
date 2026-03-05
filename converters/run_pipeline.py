#!/usr/bin/env python3
"""
run_pipeline.py — 一键提取 The Witness 社区谜题到我们的游戏格式

用法: python converters/run_pipeline.py [--max-solve-time 5] [--output-dir levels]

步骤:
1. 从 vendor_ttws/ 解码所有谜题
2. 分类筛选
3. 转换为 level_config 格式
4. BFS 求解验证 + baseline 校准
5. 按难度排序，选取关卡
6. 输出 JSON 文件
"""
import sys
import os
import json
import time
import argparse
from typing import List, Dict
from collections import Counter

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)

from ingest_ttws import ingest_all
from filter import filter_all
from to_level_config import convert_puzzle
from validate import validate_config, solution_to_actions, calibrate_baseline


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
                # Horizontal edge
                if solution and (c, r) in path_set and (c + 1, r) in path_set:
                    # Check if adjacent in solution
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


def run_pipeline(max_solve_time: float = 10.0, output_dir: str = "levels",
                 levels_per_game: int = 10) -> dict:
    """运行完整提取管线。"""
    print("=" * 60)
    print("ARC-AGI-3 Witness Puzzle Extraction Pipeline")
    print("=" * 60)

    # Step 1: Ingest
    print("\n[1/5] Ingesting puzzles from vendor_ttws/...")
    t0 = time.time()
    all_puzzles = ingest_all()
    print(f"  Decoded: {len(all_puzzles)} puzzles ({time.time()-t0:.1f}s)")

    # Step 2: Filter
    print("\n[2/5] Filtering by game type...")
    filtered = filter_all(all_puzzles)
    for game, ps in filtered.items():
        print(f"  {game}: {len(ps)} candidates")

    # Step 3: Convert
    print("\n[3/5] Converting to level_config format...")
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
    print("\n[4/5] Solving and calibrating baselines...")
    validated = {}
    stats = {"total_solved": 0, "total_failed": 0}

    for game, configs in converted.items():
        valid_levels = []
        for config, puzzle in configs:
            t0 = time.time()
            result = validate_config(config, game)
            elapsed = time.time() - t0

            if result["valid"]:
                valid_levels.append({
                    "config": config,
                    "moves": result["moves"],
                    "baseline": result["baseline"],
                    "solution": result["solution"],
                    "actions": solution_to_actions(result["solution"]),
                    "source": f"{puzzle.source}:{puzzle.source_index}",
                    "solve_time": elapsed,
                })
                stats["total_solved"] += 1
            else:
                stats["total_failed"] += 1
                if elapsed > 0.5:
                    print(f"    {game} [{puzzle.source}:{puzzle.source_index}] "
                          f"FAILED ({elapsed:.1f}s): {result['error']}")

        # Sort by difficulty (moves)
        valid_levels.sort(key=lambda x: x["moves"])
        validated[game] = valid_levels
        print(f"  {game}: {len(valid_levels)} validated "
              f"(moves range: {valid_levels[0]['moves']}-{valid_levels[-1]['moves']}"
              f" if valid_levels else 'N/A')")

    print(f"\n  Total solved: {stats['total_solved']}, failed: {stats['total_failed']}")

    # Step 5: Select and export
    print(f"\n[5/5] Selecting levels and exporting JSON...")

    abs_output = os.path.join(os.path.dirname(_here), output_dir)
    os.makedirs(abs_output, exist_ok=True)

    results = {}
    for game, levels in validated.items():
        if not levels:
            print(f"  {game}: NO valid levels!")
            continue

        # Select up to levels_per_game, spread across difficulty range
        selected = _select_levels(levels, levels_per_game)

        # Build output
        output = {
            "game": game,
            "total_candidates": len(filtered[game]),
            "total_validated": len(levels),
            "selected_count": len(selected),
            "levels": [],
        }

        for i, level in enumerate(selected):
            level_entry = {
                "level_index": i,
                "config": level["config"],
                "baseline": level["baseline"],
                "moves": level["moves"],
                "solution_actions": level["actions"],
                "source": level["source"],
            }
            output["levels"].append(level_entry)

        # Write JSON
        filepath = os.path.join(abs_output, f"{game}_levels.json")
        with open(filepath, "w") as f:
            json.dump(output, f, indent=2)

        results[game] = output
        baselines = [l["baseline"] for l in selected]
        print(f"  {game}: {len(selected)} levels -> {filepath}")
        print(f"    baselines: {baselines}")
        print(f"    moves: {[l['moves'] for l in selected]}")

        # Print ASCII art for each selected level
        for i, level in enumerate(selected):
            print(f"\n    --- {game} Level {i+1} ({level['config']['cols']}x{level['config']['rows']}, "
                  f"moves={level['moves']}, baseline={level['baseline']}) ---")
            if game == "tw01":
                print(ascii_grid_tw01(level["config"], level.get("solution")))
            elif game == "tw02":
                print(ascii_grid_tw02(level["config"]))

    return results


def _select_levels(levels: list, count: int, min_moves: int = 3) -> list:
    """从验证通过的关卡中选取 count 个，按难度渐进。"""
    # 过滤太简单的关卡和去重
    filtered = []
    seen_configs = set()
    for level in levels:
        if level["moves"] < min_moves:
            continue
        # 使用 config 的 JSON 字符串去重
        config_key = json.dumps(level["config"], sort_keys=True)
        if config_key in seen_configs:
            continue
        seen_configs.add(config_key)
        filtered.append(level)

    if len(filtered) <= count:
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
    args = parser.parse_args()

    results = run_pipeline(
        max_solve_time=args.max_solve_time,
        output_dir=args.output_dir,
        levels_per_game=args.levels_per_game,
    )

    print("\n" + "=" * 60)
    print("Pipeline complete!")
    print("=" * 60)
    for game, data in results.items():
        print(f"  {game}: {data['selected_count']} levels selected "
              f"(from {data['total_validated']} validated, {data['total_candidates']} candidates)")


if __name__ == "__main__":
    main()
