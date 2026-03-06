"""
Test script for all Witness-inspired games (tw01-tw10).
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
    """Load test solutions from JSON levels file.

    Only loads validated levels (skips unvalidated ones).
    Returns (solutions, total_levels) tuple or None.
    """
    filepath = os.path.join(LEVELS_DIR, f"{game_id}_levels.json")
    if not os.path.exists(filepath):
        return None

    with open(filepath) as f:
        data = json.load(f)

    solutions = []
    total_levels = len(data["levels"])
    for entry in data["levels"]:
        # Skip unvalidated levels (no solution to test against)
        if not entry.get("validated", True):
            continue
        actions = entry["solution_actions"]
        if not actions:
            continue
        cfg = entry["config"]
        desc = (f"{cfg['cols']}x{cfg['rows']}, "
                f"moves={entry['moves']}, source={entry['source']}")
        solutions.append((actions, desc))

    return (solutions, total_levels)


def test_game(game_class, game_name, level_solutions, total_levels=None):
    """Test a game with known solutions.

    Args:
        total_levels: total levels in game (including unvalidated).
            When there are unvalidated levels, we don't expect WIN state.
    """
    n_tested = len(level_solutions)
    extra = ""
    if total_levels and total_levels > n_tested:
        extra = f", {total_levels - n_tested} unvalidated skipped"
    print(f"\n{'='*60}")
    print(f"Testing {game_name} ({n_tested} validated levels{extra})")
    print(f"{'='*60}")

    game = game_class(seed=0)

    # Verify init fix: _grid should not be None
    assert game._grid is not None, "FAIL: _grid is None after init (constructor bug not fixed!)"
    print(f"  Init check: _grid is set")
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
            print(f"    PASSED")
        else:
            print(f"    FAILED (expected levels_completed>={expected_completed})")
            return False

    print(f"\n  Final: levels_completed={frame.levels_completed}, state={frame.state}")
    if frame.state == GameState.WIN:
        print(f"  Game WON")
    else:
        has_unvalidated = total_levels and total_levels > n_tested
        if has_unvalidated:
            print(f"  Validated levels all passed (game not WON due to unvalidated levels)")
    return True


def test_tw01():
    from tw01_pathdots import Tw01
    result = load_solutions_from_json("tw01")
    if result:
        solutions, total = result
        print(f"  (Using JSON level solutions: {len(solutions)} validated / {total} total)")
        return test_game(Tw01, "tw01_pathdots", solutions, total)
    level1 = ([RIGHT, RIGHT, RIGHT, CONFIRM], "3x3, 1 dot on straight path")
    level2 = ([DOWN, RIGHT, RIGHT, UP, RIGHT, CONFIRM], "3x3, 1 dot needs detour")
    level3 = ([RIGHT, RIGHT, DOWN, DOWN, DOWN, DOWN, RIGHT, RIGHT, CONFIRM], "4x4, 2 dots")
    level4 = ([DOWN, DOWN, DOWN, DOWN, RIGHT, RIGHT, UP, UP, RIGHT, RIGHT, DOWN, DOWN, CONFIRM], "4x4, 3 dots")
    level5 = ([RIGHT, RIGHT, RIGHT, RIGHT, RIGHT, DOWN, LEFT, LEFT, LEFT, LEFT, LEFT,
               DOWN, DOWN, DOWN, DOWN, RIGHT, RIGHT, RIGHT, RIGHT, RIGHT, CONFIRM], "5x5, 4 dots")
    return test_game(Tw01, "tw01_pathdots", [level1, level2, level3, level4, level5])


def test_tw02():
    from tw02_colorsplit import Tw02
    result = load_solutions_from_json("tw02")
    if result:
        solutions, total = result
        print(f"  (Using JSON level solutions: {len(solutions)} validated / {total} total)")
        return test_game(Tw02, "tw02_colorsplit", solutions, total)
    level1 = ([RIGHT, DOWN, DOWN, DOWN, LEFT, CONFIRM], "3x3, 2 colors")
    return test_game(Tw02, "tw02_colorsplit", [level1])


def test_tw03():
    from tw03_shapefill import Tw03
    result = load_solutions_from_json("tw03")
    if result:
        solutions, total = result
        print(f"  (Using JSON level solutions: {len(solutions)} validated / {total} total)")
        return test_game(Tw03, "tw03_shapefill", solutions, total)
    print("  (No JSON levels, using hardcoded fallback)")
    level1 = ([DOWN, DOWN, RIGHT, DOWN, RIGHT, RIGHT, CONFIRM], "3x3, 2 shapes")
    return test_game(Tw03, "tw03_shapefill", [level1])


def test_tw04():
    from tw04_symdraw import Tw04
    result = load_solutions_from_json("tw04")
    if result:
        solutions, total = result
        print(f"  (Using JSON level solutions: {len(solutions)} validated / {total} total)")
        return test_game(Tw04, "tw04_symdraw", solutions, total)
    level1 = ([DOWN, DOWN, DOWN, CONFIRM], "4x3, horizontal mirror")
    return test_game(Tw04, "tw04_symdraw", [level1])


def test_tw05():
    from tw05_starpair import Tw05
    result = load_solutions_from_json("tw05")
    if result:
        solutions, total = result
        print(f"  (Using JSON level solutions: {len(solutions)} validated / {total} total)")
        return test_game(Tw05, "tw05_starpair", solutions, total)
    print("  (No JSON levels, using hardcoded fallback)")
    level1 = ([DOWN, DOWN, DOWN, RIGHT, RIGHT, RIGHT, CONFIRM], "3x3, 2 color pairs")
    return test_game(Tw05, "tw05_starpair", [level1])


def test_tw06():
    from tw06_tricount import Tw06
    result = load_solutions_from_json("tw06")
    if result:
        solutions, total = result
        print(f"  (Using JSON level solutions: {len(solutions)} validated / {total} total)")
        return test_game(Tw06, "tw06_tricount", solutions, total)
    print("  (No JSON levels, using hardcoded fallback)")
    level1 = ([DOWN, RIGHT, DOWN, RIGHT, DOWN, RIGHT, CONFIRM], "3x3, 1 triangle")
    return test_game(Tw06, "tw06_tricount", [level1])


def test_tw07():
    from tw07_eraserlogic import Tw07
    result = load_solutions_from_json("tw07")
    if result:
        solutions, total = result
        print(f"  (Using JSON level solutions: {len(solutions)} validated / {total} total)")
        return test_game(Tw07, "tw07_eraserlogic", solutions, total)
    print("  (No JSON levels, using hardcoded fallback)")
    level1 = ([DOWN, DOWN, DOWN, RIGHT, RIGHT, RIGHT, CONFIRM], "3x3, 1 eraser")
    return test_game(Tw07, "tw07_eraserlogic", [level1])


def test_tw08():
    from tw08_combobasic import Tw08
    result = load_solutions_from_json("tw08")
    if result:
        solutions, total = result
        print(f"  (Using JSON level solutions: {len(solutions)} validated / {total} total)")
        return test_game(Tw08, "tw08_combobasic", solutions, total)
    print("  (No JSON levels, using hardcoded fallback)")
    level1 = ([DOWN, DOWN, RIGHT, RIGHT, DOWN, DOWN, RIGHT, RIGHT, CONFIRM], "4x4, combo")
    return test_game(Tw08, "tw08_combobasic", [level1])


def test_tw09():
    from tw09_cylinderwrap import Tw09
    result = load_solutions_from_json("tw09")
    if result:
        solutions, total = result
        print(f"  (Using JSON level solutions: {len(solutions)} validated / {total} total)")
        return test_game(Tw09, "tw09_cylinderwrap", solutions, total)
    print("  (No JSON levels available)")
    return True  # Skip if no levels


def test_tw10():
    from tw10_colorfilter import Tw10
    result = load_solutions_from_json("tw10")
    if result:
        solutions, total = result
        print(f"  (Using JSON level solutions: {len(solutions)} validated / {total} total)")
        return test_game(Tw10, "tw10_colorfilter", solutions, total)
    print("  (No JSON levels available)")
    return True  # Skip if no levels


def test_tw11():
    from tw11_multiregion import Tw11
    result = load_solutions_from_json("tw11")
    if result:
        solutions, total = result
        print(f"  (Using JSON level solutions: {len(solutions)} validated / {total} total)")
        return test_game(Tw11, "tw11_multiregion", solutions, total)
    print("  (No JSON levels available)")
    return True  # Skip if no levels


def test_tw12():
    from tw12_hexcombo import Tw12
    result = load_solutions_from_json("tw12")
    if result:
        solutions, total = result
        print(f"  (Using JSON level solutions: {len(solutions)} validated / {total} total)")
        return test_game(Tw12, "tw12_hexcombo", solutions, total)
    print("  (No JSON levels available)")
    return True  # Skip if no levels


def test_tw13():
    from tw13_eraserall import Tw13
    result = load_solutions_from_json("tw13")
    if result:
        solutions, total = result
        print(f"  (Using JSON level solutions: {len(solutions)} validated / {total} total)")
        return test_game(Tw13, "tw13_eraserall", solutions, total)
    print("  (No JSON levels available)")
    return True  # Skip if no levels


if __name__ == "__main__":
    print("=" * 60)
    print("ARC-AGI-3 Witness Games — Test Suite")
    print("=" * 60)

    all_tests = [
        ("tw01", test_tw01),
        ("tw02", test_tw02),
        ("tw03", test_tw03),
        ("tw04", test_tw04),
        ("tw05", test_tw05),
        ("tw06", test_tw06),
        ("tw07", test_tw07),
        ("tw08", test_tw08),
        ("tw09", test_tw09),
        ("tw10", test_tw10),
        ("tw11", test_tw11),
        ("tw12", test_tw12),
        ("tw13", test_tw13),
    ]

    results = {}
    for name, test_fn in all_tests:
        try:
            ok = test_fn()
            results[name] = "PASSED" if ok else "FAILED"
            status = "passed" if ok else "FAILED"
            print(f"\n{'PASS' if ok else 'FAIL'} {name} {status}")
        except Exception as e:
            results[name] = f"ERROR: {e}"
            print(f"\nFAIL {name} ERROR: {e}")
            import traceback; traceback.print_exc()

    print(f"\n{'='*60}")
    print("Summary:")
    passed = sum(1 for v in results.values() if v == "PASSED")
    total = len(results)
    for name, result in results.items():
        print(f"  {name}: {result}")
    print(f"\n  {passed}/{total} passed")
