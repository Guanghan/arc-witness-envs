"""
play_human.py — 启动本地 Web 服务器，让人类玩家在浏览器中游玩 Witness 游戏。

用法:
    cd arc-witness-envs
    python play_human.py [port]

然后打开浏览器访问 http://localhost:<port> (默认 8001)
"""
import os
import sys

# 确保本目录在 sys.path 中，以便 SDK exec() 能找到 witness_grid
_code_dir = os.path.dirname(os.path.abspath(__file__))
if _code_dir not in sys.path:
    sys.path.insert(0, _code_dir)

from arc_agi import Arcade, OperationMode
from flask import send_from_directory


STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


def add_frontend_routes(arcade, app):
    """添加前端 HTML 页面路由。"""
    @app.route("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.route("/static/<path:filename>")
    def static_files(filename):
        return send_from_directory(STATIC_DIR, filename)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8001

    # 指向 environment_files 目录（包含 tw01, tw02, tw04 的 metadata.json）
    env_dir = os.path.join(os.path.dirname(__file__), "environment_files")

    print("=" * 60)
    print("ARC-AGI-3 Witness Games — Human Play Server")
    print("=" * 60)
    print(f"Scanning games from: {env_dir}")

    # 使用 OFFLINE 模式，只加载本地游戏
    arcade = Arcade(
        operation_mode=OperationMode.OFFLINE,
        environments_dir=env_dir,
    )

    # 列出发现的游戏
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
