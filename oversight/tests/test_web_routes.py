"""P4 interactive oversight routes — tested via the Flask test client (no
browser, no SDK arcade).

Run: python -m pytest oversight/tests/test_web_routes.py
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

flask = pytest.importorskip("flask")  # routes need Flask (ships with play_human)


def _client():
    from flask import Flask

    from oversight.web_routes import register_oversight_routes

    app = Flask(__name__)
    register_oversight_routes(app)
    return app.test_client()


def test_load_step_snapshot_restore():
    c = _client()
    r = c.post("/api/oversight/load", json={"game_id": "tw01", "seed": 0})
    assert r.status_code == 200
    d = r.get_json()
    sess = d["session"]
    assert len(d["grid"]) == 64 and len(d["grid"][0]) == 64
    fh0 = d["frame_hash"]

    sid = c.post("/api/oversight/snapshot", json={"session": sess}).get_json()["sid"]
    assert len(sid) == 64

    fh1 = c.post("/api/oversight/step", json={"session": sess, "action": 4}).get_json()["frame_hash"]
    assert fh1 != fh0  # stepping changed the board

    fh2 = c.post("/api/oversight/restore", json={"session": sess, "sid": sid}).get_json()["frame_hash"]
    assert fh2 == fh0  # restore brought it back


def test_fork_is_independent():
    c = _client()
    sess = c.post("/api/oversight/load", json={"game_id": "tw01", "seed": 0}).get_json()["session"]
    snap = c.post("/api/oversight/snapshot", json={"session": sess}).get_json()["sid"]

    csess = c.post("/api/oversight/fork", json={"session": sess}).get_json()["session"]
    assert csess != sess
    # mutate the fork
    c.post("/api/oversight/step", json={"session": csess, "action": 4})
    # the parent is unchanged (still matches its snapshot)
    fh_parent = c.post("/api/oversight/restore", json={"session": sess, "sid": snap}).get_json()["frame_hash"]
    snap2 = c.post("/api/oversight/snapshot", json={"session": sess}).get_json()["sid"]
    assert snap2 == snap  # parent frame-state id unchanged


def test_route_errors():
    c = _client()
    assert c.post("/api/oversight/load", json={}).status_code == 400          # missing game_id
    assert c.post("/api/oversight/step", json={"session": "nope", "action": 1}).status_code == 404
    assert c.post("/api/oversight/restore", json={"session": "nope", "sid": "x"}).status_code == 404
