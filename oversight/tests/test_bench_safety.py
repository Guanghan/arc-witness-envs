"""P1 acceptance gates — GATE-C/D/F (OversightEnv is transparent under bench's
_ResetCountingGame), GATE-R1 (removability), and the OpenEnv contract tripwire.

Run: python -m pytest oversight/tests/test_bench_safety.py
"""
import os
import subprocess
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO)

from bench.runner import _ResetCountingGame  # noqa: E402
from oversight import OversightEnv  # noqa: E402
from oversight.resolve import resolve_root_game  # noqa: E402
from oversight.tests.conftest import ALL_GAMES, ai, digest, first_solution, load_game  # noqa: E402


@pytest.mark.parametrize("gid", ALL_GAMES)
def test_oversightenv_transparent(gid):
    """GATE-C/D/F: interposing OversightEnv under _ResetCountingGame changes
    neither the frame stream, the reset count, nor attribute reachability."""
    actions = first_solution(gid) + [0] + first_solution(gid)[:4]  # includes a RESET

    a = _ResetCountingGame(load_game(gid, seed=0))                  # bench, today
    b = _ResetCountingGame(OversightEnv(load_game(gid, seed=0)))     # bench, with oversight

    assert digest(a, actions) == digest(b, actions), f"{gid}: OversightEnv altered frames"
    assert a.reset_count == b.reset_count == 1, f"{gid}: reset count drift"

    # GATE-F: bare-game attributes reach through BOTH proxy layers.
    assert b.level_index == a.level_index
    assert resolve_root_game(b) is b._game._bare
    assert b._seed == 0


def test_runner_has_import_guard():
    """The runner wraps with a guarded OversightEnv that falls back to identity."""
    import bench.runner as R

    assert hasattr(R, "_OversightEnv")
    # With oversight present, the guard resolves to the real class.
    assert R._OversightEnv is OversightEnv


def test_removability_subprocess():
    """GATE-R1: with the oversight package made unimportable, bench.runner still
    imports and a game still plays through the identity fallback."""
    code = f"""
import sys
sys.path.insert(0, {_REPO!r})

class _Block:
    def find_spec(self, name, path=None, target=None):
        if name == "oversight" or name.startswith("oversight."):
            raise ImportError("oversight blocked (removability test)")
        return None

sys.meta_path.insert(0, _Block())

import bench.runner as R
from bench.catalog import load_game
from arcengine import ActionInput, GameAction

g = R._ResetCountingGame(R._OversightEnv(load_game("tw01", 0)))
for n in (4, 4, 1, 3):
    g.perform_action(ActionInput(id=GameAction.from_id(n)))
# identity fallback -> bare game directly under the counter
assert type(g._game).__name__ == "Tw01", type(g._game).__name__
print("REMOVABILITY_OK")
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 0, f"removability subprocess failed:\n{out.stderr}"
    assert "REMOVABILITY_OK" in out.stdout


def test_openenv_contract_clean():
    """OpenEnv tripwire: no oversight symbol leaks into the RL contract/routes."""
    files = [
        "openenv_adapter/models.py",
        "openenv_adapter/server/witness_environment.py",
        "openenv_adapter/server/app.py",
    ]
    for rel in files:
        with open(os.path.join(_REPO, rel)) as f:
            src = f.read()
        assert "oversight" not in src.lower(), f"{rel} references oversight"
