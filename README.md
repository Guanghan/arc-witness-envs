# arc-witness-envs

Interactive reasoning environments for [ARC-AGI-3](https://arcprize.org/arc-agi/3/), inspired by the puzzle mechanics of [The Witness](https://en.wikipedia.org/wiki/The_Witness_(2016_video_game)).

Built on the official [ARC-AGI SDK](https://docs.arcprize.org) (`arcengine`). Each game renders to a 64x64 pixel grid with a 16-color palette, playable by both AI agents and humans.

## Why The Witness?

The Witness contains 523+ hand-crafted line-drawing puzzles that teach abstract rules through progressive difficulty — no text, no tutorials. Each puzzle type maps cleanly to ARC-AGI [Core Knowledge](https://arxiv.org/abs/1911.01547) priors:

| Puzzle Mechanic | Game | Core Knowledge |
|---|---|---|
| Hexagon dots (mandatory waypoints) | `tw01` PathDots | Objectness — preserving specific elements |
| Colored squares (region partition) | `tw02` ColorSplit | Objectness + Numbers — classify by attribute |
| Symmetry (mirrored line drawing) | `tw04` SymDraw | Geometry — symmetry transforms, mental simulation |

## Games

### tw01 — PathDots

Draw a path from start to end that passes through **all** marked waypoints (yellow dots).

```
S-+-E       Level 1: 2x2 grid, 2 dots
| | |       8 moves to solve
o-+-o
| | |
+-+-+
```

- 5 levels, progressively harder (8 → 22 moves)
- Advanced levels include **breakpoints** (blocked edges)
- Trains: path planning, constraint satisfaction

### tw02 — ColorSplit

Draw a path that **partitions** the grid into regions where each region contains only one color of square.

```
S-+-+-+-+   Level 3: 4x4 grid, 12 squares
|A|B|B|B|   16 moves to solve
+-+-+-+-+
|A| | |A|
+-+-+-+-+
|A| | |A|
+-+-+-+-+
|B|B|B|A|
+-+-+-+-E
```

- 5 levels (3 → 20 moves)
- Up to 3 colors (magenta / light-blue / orange)
- Trains: classification, spatial reasoning, region analysis

### tw04 — SymDraw

Control a **blue** line; a **yellow** line mirrors your moves automatically. Both must reach their respective endpoints simultaneously.

- 5 levels (3 → 13 moves)
- Symmetry types: horizontal, vertical, 180° rotational
- Advanced levels add colored waypoints for both lines
- Trains: symmetry transforms, dual-state mental simulation

## Project Structure

```
arc-witness-envs/
├── witness_grid.py            # Shared grid renderer (64x64, 16-color)
├── tw01_pathdots.py           # PathDots game (ARCBaseGame subclass)
├── tw02_colorsplit.py         # ColorSplit game
├── tw04_symdraw.py            # SymDraw game
├── test_games.py              # Automated test suite (all 15 levels)
├── play_human.py              # Local web server for browser play
├── environment_files/         # Game metadata (for SDK discovery)
│   ├── tw01/metadata.json
│   ├── tw02/metadata.json
│   └── tw04/metadata.json
├── levels/                    # Level configs with verified solutions
│   ├── tw01_levels.json       # 5 levels from Witness community data
│   ├── tw02_levels.json
│   └── tw04_levels.json
└── converters/                # Puzzle extraction pipeline
    ├── unified_puzzle.py      # Intermediate data model
    ├── ingest_ttws.py         # Decode protobuf puzzles from ttws
    ├── filter.py              # Classify & filter by game type + grid size
    ├── to_level_config.py     # Convert to game-native level configs
    ├── validate.py            # BFS/DFS solver + baseline calibration
    ├── run_pipeline.py        # One-command extraction pipeline
    └── vendor_ttws/           # Community puzzle data (barrycohen/ttws)
```

## Quick Start

### Install

```bash
pip install arc-agi
```

### Play in Browser

```bash
cd arc-witness-envs
python play_human.py
# Open http://localhost:8001
```

### Use Programmatically

```python
from arcengine import GameAction, ActionInput
from tw01_pathdots import Tw01

game = Tw01(seed=0)

UP, DOWN, LEFT, RIGHT, CONFIRM = (
    GameAction.ACTION1, GameAction.ACTION2,
    GameAction.ACTION3, GameAction.ACTION4,
    GameAction.ACTION5,
)

# Play level 1: navigate to collect all dots, then confirm
for action in [RIGHT, RIGHT, UP, LEFT, LEFT, UP, RIGHT, RIGHT, CONFIRM]:
    frame = game.perform_action(ActionInput(id=action), raw=True)

print(f"Levels completed: {frame.levels_completed}")
print(f"State: {frame.state}")  # GameState.PLAYING or GameState.WIN
```

### Run Tests

```bash
python test_games.py
```

Verifies all 15 levels (5 per game) using solutions stored in `levels/*.json`.

## Level Data

Levels are sourced from real Witness community puzzles via the [ttws](https://github.com/barrycohen/ttws) project (2,605 decoded puzzles from the game and the Windmill fan community). Each level includes:

- **config** — Grid dimensions, start/end positions, constraints (dots/squares/symmetry)
- **solution_actions** — Verified optimal action sequence
- **baseline** — Human-calibrated action budget: `ceil((shortest_moves + 1) * 1.2)`
- **source** — Provenance (e.g., `witness:19` = puzzle #19 from the original game)

### Extraction Pipeline

Re-run to regenerate or expand levels:

```bash
cd converters
python run_pipeline.py --levels-per-game 10
```

Pipeline: decode protobuf → classify by game type → convert coordinates → solve with BFS/DFS → calibrate baselines → export JSON.

| Game | Decoded | After Filter | Solved | Selected |
|------|---------|-------------|--------|----------|
| tw01 | 2,605 | 13 | 7 | 5 |
| tw02 | 2,605 | 32 | 26 | 5 |
| tw04 | 2,605 | 28 | 26 | 5 |

## Architecture

All games inherit from `ARCBaseGame` and follow the SDK contract:

```
ARCBaseGame
├── __init__()    → create Level objects with Sprites
├── on_set_level() → initialize game state for current level
├── step()        → process one GameAction, update display
└── next_level()  → advance on correct solution
```

Rendering flows through `WitnessGrid`:

```
WitnessGrid(cols, rows)
├── render_grid()           → 64x64 int[][] (color indices)
├── draw_path_segment()     → render path between nodes
├── draw_dot() / draw_start() / draw_end()
├── draw_cell_symbol()      → colored squares in cell centers
└── path_splits_regions()   → BFS region extraction for tw02
```

### Coordinate System

- **Nodes**: `(col, row)` in `[0, cols] x [0, rows]` — path intersections
- **Cells**: `(col, row)` in `[0, cols-1] x [0, rows-1]` — spaces between nodes
- **Pixels**: 64x64 grid, nodes rendered as 1px dots, edges as 1px lines

### Action Space

| Action | ID | GameAction |
|---|---|---|
| Up | 1 | `ACTION1` |
| Down | 2 | `ACTION2` |
| Left | 3 | `ACTION3` |
| Right | 4 | `ACTION4` |
| Confirm | 5 | `ACTION5` |

## ARC-AGI-3 Context

This repository provides **training environments** for the [ARC-AGI-3 competition](https://arcprize.org/arc-agi/3/) — the first Interactive Reasoning Benchmark (IRB). Agents must:

1. **Explore** — discover game rules through interaction (no instructions provided)
2. **Learn** — infer abstract constraints from visual feedback
3. **Plan** — solve increasingly difficult levels within an action budget

Scoring: `score = max(0, 1 - actions_taken / baseline_actions)` per level, averaged across all levels.

## License

The game implementations and extraction pipeline are original work. Level data is derived from community contributions to [The Witness](https://store.steampowered.com/app/210970/The_Witness/) puzzle ecosystem via the [ttws](https://github.com/barrycohen/ttws) project.

## Author

**Guanghan Ning** — Independent AI researcher, Bay Area. PhD in ECE, former ByteDance Seed-Code LLM research scientist.
