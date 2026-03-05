"""
Test script for Witness-inspired games (tw01, tw02, tw04).
Uses the proper ARCBaseGame.perform_action() API.

Automatically loads test solutions from levels/*.json if available,
falls back to hardcoded solutions otherwise.
"""
import sys
import os
import json

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from arcengine import GameAction, ActionInput, GameState

UP = GameAction.ACTION1
DOWN = GameAction.ACTION2
LEFT = GameAction.ACTION3
RIGHT = GameAction.ACTION4
CONFIRM = GameAction.ACTION5
RESET = GameAction.RESET

ACTION_NAMES = {1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT", 5: "CONFIRM"}
LEVELS_DIR = os.path.join(_here, "levels")


def act(game, action_id):
    """Perform an action and return FrameDataRaw."""
    return game.perform_action(ActionInput(id=action_id), raw=True)


def load_solutions_from_json(game_id):
    """Load test solutions from JSON levels file."""
    filepath = os.path.join(LEVELS_DIR, f"{game_id}_levels.json")
    if not os.path.exists(filepath):
        return None

    with open(filepath) as f:
        data = json.load(f)

    solutions = []
    for entry in data["levels"]:
        actions = entry["solution_actions"]
        desc = (f"{entry['config']['cols']}x{entry['config']['rows']}, "
                f"moves={entry['moves']}, source={entry['source']}")
        solutions.append((actions, desc))

    return solutions


def test_game(game_class, game_name, level_solutions):
    print(f"\n{'='*60}")
    print(f"Testing {game_name}")
    print(f"{'='*60}")

    game = game_class(seed=0)

    # Verify init fix: _grid should not be None
    assert game._grid is not None, "FAIL: _grid is None after init (constructor bug not fixed!)"
    print(f"  Init check: _grid is set ✓")
    print(f"  level_index={game.level_index}, win_score={game.win_score}")

    # Get initial frame
    frame = act(game, RESET)
    print(f"  After RESET: levels_completed={frame.levels_completed}, state={frame.state}")

    for level_idx, (solution, desc) in enumerate(level_solutions):
        print(f"\n  --- Level {level_idx + 1}: {desc} ---")
        print(f"    level_index={game.level_index}")

        # Execute solution
        for action_id in solution:
            frame = act(game, action_id)

        print(f"    After solution: levels_completed={frame.levels_completed}, state={frame.state}")

        expected_completed = level_idx + 1
        if frame.levels_completed >= expected_completed:
            print(f"    PASSED ✓")
        else:
            print(f"    FAILED ✗ (expected levels_completed>={expected_completed})")
            return False

    print(f"\n  Final: levels_completed={frame.levels_completed}, state={frame.state}")
    if frame.state == GameState.WIN:
        print(f"  Game WON ✓")
    return True


def test_tw01():
    from tw01_pathdots import Tw01

    # Try JSON solutions first
    json_solutions = load_solutions_from_json("tw01")
    if json_solutions:
        print("  (Using JSON level solutions)")
        return test_game(Tw01, "tw01_pathdots", json_solutions)

    # Hardcoded fallback
    level1 = ([RIGHT, RIGHT, RIGHT, CONFIRM],
              "3×3, 1 dot on straight path")
    level2 = ([DOWN, RIGHT, RIGHT, UP, RIGHT, CONFIRM],
              "3×3, 1 dot needs detour")
    level3 = ([RIGHT, RIGHT, DOWN, DOWN, DOWN, DOWN, RIGHT, RIGHT, CONFIRM],
              "4×4, 2 dots")
    level4 = ([DOWN, DOWN, DOWN, DOWN, RIGHT, RIGHT, UP, UP, RIGHT, RIGHT, DOWN, DOWN, CONFIRM],
              "4×4, 3 dots")
    level5 = ([RIGHT, RIGHT, RIGHT, RIGHT, RIGHT, DOWN, LEFT, LEFT, LEFT, LEFT, LEFT,
               DOWN, DOWN, DOWN, DOWN, RIGHT, RIGHT, RIGHT, RIGHT, RIGHT, CONFIRM],
              "5×5, 4 dots")

    return test_game(Tw01, "tw01_pathdots", [level1, level2, level3, level4, level5])


def test_tw02():
    from tw02_colorsplit import Tw02

    json_solutions = load_solutions_from_json("tw02")
    if json_solutions:
        print("  (Using JSON level solutions)")
        return test_game(Tw02, "tw02_colorsplit", json_solutions)

    # Hardcoded fallback (only level 1)
    level1 = ([RIGHT, DOWN, DOWN, DOWN, LEFT, CONFIRM],
              "3×3, 2 colors, vertical split")
    return test_game(Tw02, "tw02_colorsplit", [level1])


def test_tw04():
    from tw04_symdraw import Tw04

    json_solutions = load_solutions_from_json("tw04")
    if json_solutions:
        print("  (Using JSON level solutions)")
        return test_game(Tw04, "tw04_symdraw", json_solutions)

    # Hardcoded fallback (only level 1)
    level1 = ([DOWN, DOWN, DOWN, CONFIRM],
              "4×3, horizontal mirror, straight down")
    return test_game(Tw04, "tw04_symdraw", [level1])


if __name__ == "__main__":
    print("=" * 60)
    print("ARC-AGI-3 Witness Games — Test Suite")
    print("=" * 60)

    results = {}
    for name, test_fn in [("tw01", test_tw01), ("tw02", test_tw02), ("tw04", test_tw04)]:
        try:
            ok = test_fn()
            results[name] = "PASSED" if ok else "FAILED"
            print(f"\n{'✓' if ok else '✗'} {name} {'passed' if ok else 'FAILED'}")
        except Exception as e:
            results[name] = f"ERROR: {e}"
            print(f"\n✗ {name} ERROR: {e}")
            import traceback; traceback.print_exc()

    print(f"\n{'='*60}")
    print("Summary:")
    for name, result in results.items():
        print(f"  {name}: {result}")
