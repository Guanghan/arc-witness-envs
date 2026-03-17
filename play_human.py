"""
play_human.py — Start a local web server for human players to play Witness games in the browser.

Usage:
    cd arc-witness-envs
    python play_human.py [port]

Then open your browser at http://localhost:<port> (default 8001)
"""
import os
import sys

# Ensure this directory is in sys.path so SDK exec() can find witness_grid
_code_dir = os.path.dirname(os.path.abspath(__file__))
if _code_dir not in sys.path:
    sys.path.insert(0, _code_dir)

import json

from arc_agi import Arcade, OperationMode
from flask import send_from_directory, jsonify, request

from teaching.collector import TeachingCollector
from teaching.models import TeachingStep, EpisodeOutcome


STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
LEVELS_DIR = os.path.join(os.path.dirname(__file__), "levels")
TEACHING_DIR = os.path.join(os.path.dirname(__file__), "teaching_data")

# Global teaching collector (initialized once)
_teaching_collector = TeachingCollector(data_dir=TEACHING_DIR)


def _load_levels_json(game_id):
    """Load the levels JSON file for a game."""
    filepath = os.path.join(LEVELS_DIR, f"{game_id}_levels.json")
    if not os.path.exists(filepath):
        return None
    with open(filepath) as f:
        return json.load(f)


def _save_levels_json(game_id, data):
    """Save the levels JSON file for a game."""
    filepath = os.path.join(LEVELS_DIR, f"{game_id}_levels.json")
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def add_frontend_routes(arcade, app):
    """Add frontend HTML page routes + custom API endpoints."""
    # Point Flask's built-in /static/ route to our static directory
    app.static_folder = STATIC_DIR

    @app.route("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.route("/static/<path:filename>")
    def static_files(filename):
        return send_from_directory(STATIC_DIR, filename)

    @app.route("/api/custom/level_status/<game_id>")
    def level_status(game_id):
        """Return the validation status for each level."""
        data = _load_levels_json(game_id)
        if not data:
            return jsonify({"error": f"No levels found for {game_id}"}), 404
        statuses = []
        for entry in data["levels"]:
            statuses.append({
                "level_index": entry["level_index"],
                "validated": entry.get("validated", True),
                "moves": entry.get("moves", 0),
                "has_solution": len(entry.get("solution_actions", [])) > 0,
            })
        return jsonify({
            "game_id": game_id,
            "total": len(statuses),
            "validated_count": sum(1 for s in statuses if s["validated"]),
            "unvalidated_count": sum(1 for s in statuses if not s["validated"]),
            "levels": statuses,
        })

    @app.route("/api/custom/validate_level", methods=["POST"])
    def validate_level():
        """After a user manually completes a level, mark it as validated and record the action sequence."""
        body = request.get_json(force=True)
        game_id = body.get("game_id")
        level_index = body.get("level_index")
        actions = body.get("actions", [])
        moves = body.get("moves", 0)

        if not game_id or level_index is None:
            return jsonify({"error": "Missing game_id or level_index"}), 400

        data = _load_levels_json(game_id)
        if not data:
            return jsonify({"error": f"No levels found for {game_id}"}), 404

        # Find the level entry
        target = None
        for entry in data["levels"]:
            if entry["level_index"] == level_index:
                target = entry
                break

        if not target:
            return jsonify({"error": f"Level {level_index} not found"}), 404

        if target.get("validated", True):
            return jsonify({"status": "already_validated", "level_index": level_index})

        # Update the level
        import math
        target["validated"] = True
        target["solution_actions"] = actions
        target["moves"] = moves
        target["baseline"] = math.ceil((moves + 1) * 1.2)

        _save_levels_json(game_id, data)

        return jsonify({
            "status": "validated",
            "level_index": level_index,
            "moves": moves,
            "baseline": target["baseline"],
        })

    # ── Teaching Data Collection API ──────────────────────

    @app.route("/api/teaching/start_episode", methods=["POST"])
    def teaching_start_episode():
        """Start a new teaching episode for a game/level."""
        body = request.get_json(force=True)
        game_id = body.get("game_id")
        level_index = body.get("level_index", 0)
        seed = body.get("seed", 0)
        if not game_id:
            return jsonify({"error": "Missing game_id"}), 400
        episode_id = _teaching_collector.start_episode(game_id, level_index, seed)
        return jsonify({"episode_id": episode_id, "status": "started"})

    @app.route("/api/teaching/step", methods=["POST"])
    def teaching_step():
        """Record one step with reasoning annotation."""
        body = request.get_json(force=True)
        step = TeachingStep(
            step_index=body.get("step_index", _teaching_collector.step_count),
            frame_hash=body.get("frame_hash", ""),
            action=body.get("action", 0),
            reasoning=body.get("reasoning", ""),
            confidence=body.get("confidence", 0.7),
            tags=body.get("tags", []),
        )
        ok = _teaching_collector.record_step(step)
        if not ok:
            return jsonify({"error": "No active episode"}), 400
        return jsonify({"status": "recorded", "step_index": step.step_index})

    @app.route("/api/teaching/outcome", methods=["POST"])
    def teaching_outcome():
        """Finish the active episode with an outcome annotation."""
        body = request.get_json(force=True)
        outcome = EpisodeOutcome(
            game_id=body.get("game_id", ""),
            level_index=body.get("level_index", 0),
            completed=body.get("completed", False),
            total_steps=body.get("total_steps", 0),
            baseline_steps=body.get("baseline_steps"),
            key_insights=body.get("key_insights", []),
            rules_discovered=body.get("rules_discovered", []),
            difficulty_rating=body.get("difficulty_rating", 3),
        )
        episode = _teaching_collector.finish_episode(outcome)
        if not episode:
            return jsonify({"error": "No active episode"}), 400
        return jsonify({
            "status": "finished",
            "episode_id": episode.episode_id,
            "steps": len(episode.steps),
        })

    @app.route("/api/teaching/episodes")
    def teaching_list_episodes():
        """List all teaching episodes across all games."""
        summaries = _teaching_collector.list_episodes_summary()
        return jsonify({"episodes": summaries, "total": len(summaries)})

    @app.route("/api/teaching/episode/<episode_id>")
    def teaching_get_episode(episode_id):
        """Get a specific teaching episode by ID."""
        ep = _teaching_collector.get_episode(episode_id)
        if not ep:
            return jsonify({"error": "Episode not found"}), 404
        return jsonify(ep.model_dump())


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8001

    # Point to the environment_files directory (contains metadata.json for tw01, tw02, tw04)
    env_dir = os.path.join(os.path.dirname(__file__), "environment_files")

    print("=" * 60)
    print("ARC-AGI-3 Witness Games — Human Play Server")
    print("=" * 60)
    print(f"Scanning games from: {env_dir}")

    # Use OFFLINE mode to only load local games
    arcade = Arcade(
        operation_mode=OperationMode.OFFLINE,
        environments_dir=env_dir,
    )

    # List discovered games
    envs = arcade.get_environments()
    print(f"\nFound {len(envs)} games:")
    for env in envs:
        print(f"  - {env.game_id}: {env.title}")

    print(f"\nStarting server on http://localhost:{port}")
    print("Open this URL in your browser to play!")
    print("Press Ctrl+C to stop.\n")

    arcade.listen_and_serve(
        host="0.0.0.0",
        port=port,
        extra_api_routes=add_frontend_routes,
    )


if __name__ == "__main__":
    main()
