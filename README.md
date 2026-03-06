# arc-witness-envs

Interactive reasoning environments for [ARC-AGI-3](https://arcprize.org/arc-agi/3/), inspired by the puzzle mechanics of [The Witness](https://en.wikipedia.org/wiki/The_Witness_(2016_video_game)).

Built on the official [ARC-AGI SDK](https://docs.arcprize.org) (`arcengine`). Each game renders to a 64x64 pixel grid with a 16-color palette, playable by both AI agents and humans.

## Why The Witness?

The Witness contains 523+ hand-crafted line-drawing puzzles that teach abstract rules through progressive difficulty — no text, no tutorials. Each puzzle type maps cleanly to ARC-AGI [Core Knowledge](https://arxiv.org/abs/1911.01547) priors:

| Puzzle Mechanic | Game | Core Knowledge |
|---|---|---|
| Hexagon dots (mandatory waypoints) | `tw01` PathDots | Objectness — preserving specific elements |
| Colored squares (region partition) | `tw02` ColorSplit | Objectness + Numbers — classify by attribute |
| Polyomino shapes (exact cover tiling) | `tw03` ShapeFill | Geometry — spatial composition |
| Symmetry (mirrored line drawing) | `tw04` SymDraw | Geometry — symmetry transforms, mental simulation |
| Stars (region pair counting) | `tw05` StarPair | Numbers — counting + classification |
| Triangles (edge counting) | `tw06` TriCount | Numbers — local counting constraints |
| Erasers (error absorption) | `tw07` EraserLogic | Meta-reasoning — constraint violation balancing |
| Squares + Stars (dual constraint) | `tw08` ComboBasic | Composition — multiple simultaneous rules |
| Cylinder wrap (topology) | `tw09` CylinderWrap | Topology — non-planar space |
| Color filters (perception transform) | `tw10` ColorFilter | Perception — transform-then-apply |

## Games

### tw01 — PathDots
Draw a path from start to end that passes through **all** marked waypoints (yellow dots).
- 16 levels (10 validated + 6 unvalidated), progressively harder
- Advanced levels include breakpoints (blocked edges) and multiple start points
- Trains: path planning, constraint satisfaction

### tw02 — ColorSplit
Draw a path that **partitions** the grid into regions where each region contains only one color of square.
- 62 levels (51 validated + 11 unvalidated, up to 3 colors)
- Advanced levels include breakpoints (blocked edges)
- Trains: classification, spatial reasoning, region analysis

### tw03 — ShapeFill
Draw a path that partitions the grid; each region's polyomino pieces must **exactly tile** the region.
- 248 levels (106 validated + 142 unvalidated)
- NP-complete tiling validation, advanced levels include breakpoints
- Trains: spatial composition, geometric reasoning

### tw04 — SymDraw
Control a **blue** line; a **yellow** line mirrors your moves automatically. Both must reach their respective endpoints simultaneously.
- 26 levels (20 validated + 6 unvalidated)
- Symmetry types: horizontal, vertical, 180° rotational
- Advanced levels include breakpoints affecting both paths
- Trains: symmetry transforms, dual-state mental simulation

### tw05 — StarPair
Draw a path that partitions the grid; each region must contain **exactly 2 stars** of each color present.
- 55 levels (46 validated + 9 unvalidated)
- Advanced levels include breakpoints
- Trains: counting, classification, region analysis

### tw06 — TriCount
Each cell with N triangles requires the path to touch **exactly N edges** of that cell.
- 123 levels (105 validated + 18 unvalidated)
- Trains: local counting, edge-cell relationship reasoning

### tw07 — EraserLogic
Eraser symbols absorb constraint violations. Each region must have `#erasers == #violations`.
- 294 levels (221 validated + 73 unvalidated) — largest game
- Combines with squares, stars, and triangle constraints
- Trains: meta-reasoning, error balancing

### tw08 — ComboBasic
Simultaneous **ColorSplit** (squares) + **StarPair** (stars) constraints.
- 73 levels (34 validated + 39 unvalidated)
- Trains: compositional reasoning, multi-constraint satisfaction

### tw09 — CylinderWrap
PathDots variant where the grid **wraps horizontally** (left edge = right edge).
- 5 hand-crafted levels
- Trains: topological reasoning, wrap-around navigation

### tw10 — ColorFilter
ColorSplit variant where **filter cells** change the perceived color of squares. Constraints apply to perceived colors.
- 5 hand-crafted levels
- Trains: perception transformation, transform-then-apply reasoning

## Dataset Statistics

### Coverage Summary

| Game | Mechanism | TTWS Classified | Validated | Unvalidated | **Total** | Coverage |
|------|-----------|----------------|-----------|-------------|-----------|----------|
| tw01 | PathDots | 44 | 10 | 6 | **16** | 36.4% |
| tw02 | ColorSplit | 76 | 27 | 9 | **36** | 47.4% |
| tw03 | ShapeFill | 272 | 47 | 92 | **139** | 51.1% |
| tw04 | SymDraw | 210 | 26 | 2 | **28** | 13.3% |
| tw05 | StarPair | 88 | 26 | 9 | **35** | 39.8% |
| tw06 | TriCount | 160 | 105 | 18 | **123** | 76.9% |
| tw07 | EraserLogic | 625 | 221 | 73 | **294** | 47.0% |
| tw08 | ComboBasic | 128 | 34 | 39 | **73** | 57.0% |
| tw09 | CylinderWrap | 0 | 5 | 0 | **5** | hand-crafted |
| tw10 | ColorFilter | 0 | 5 | 0 | **5** | hand-crafted |
| **other** | multi-constraint | **1,002** | — | — | **0** | 0% |
| **Total** | | **2,605** | **506** | **248** | **754** | |

> **Validated** levels have solver-verified solutions with action sequences and baseline scores.
> **Unvalidated** levels passed filtering but the solver timed out (NP-hard puzzles). They are playable and marked with an orange "?" indicator. When a human solves one in play_human.py, it is automatically marked as validated.

### TTWS Raw Constraint Distribution

Each puzzle may contain multiple constraint types simultaneously:

| Constraint | Count | Mapped To |
|-----------|-------|-----------|
| tetris (polyomino) | 1,195 | tw03 (solo), tw07/tw08 (combo) |
| stars | 1,177 | tw05 (solo), tw07/tw08 (combo) |
| missing_edges | 1,043 | Not supported (rejected by filter) |
| triangles | 972 | tw06 (solo), tw07 (combo) |
| squares | 936 | tw02 (solo), tw07/tw08 (combo) |
| hex (hexagons) | 809 | tw01 (solo) |
| eliminations | 776 | tw07 (combo only) |
| symmetry | 258 | tw04 |
| No constraints | 5 | — |

### Pipeline Funnel

```
TTWS total puzzles:           2,605   (100%)
 ├─ Classified (tw01-08):     1,603   (61.5%)
 │  ├─ Passed filter:          ~788   (30.2%)  ← includes multi-start
 │  │  ├─ Solver validated:     496   (19.0%)
 │  │  ├─ Unvalidated kept:     248   (9.5%)   ← solver timeout, still playable
 │  │  └─ Total levels:         744   (28.6%)
 │  └─ Filter rejected:        ~815
 ├─ "other" (multi-constraint):1,002   (38.5%)
 └─ Hand-crafted (tw09/10):     +10
───────────────────────────────
 Grand total:                   754 levels
```

### Major Loss Points

| Bottleneck | Lost | Cause | Status |
|-----------|------|-------|--------|
| "other" unclassified | 1,002 | Multi-constraint combos (e.g., tetris+stars, hex+tetris) | Pending (tw11+) |
| missing_edges rejected | ~400+ | Grid engine doesn't support broken edges | Pending |
| ~~multi-start rejected~~ | ~~\~180~~ | ~~Puzzles with 2+ start points~~ | **Resolved** |
| ~~Solver timeout~~ | ~~\~259~~ | ~~NP-hard puzzles exceed BFS/DFS time limit~~ | **Resolved** (kept as unvalidated) |

### Expansion Opportunities

| Direction | Potential Levels | Effort | Status |
|----------|-----------------|--------|--------|
| Support missing_edges (broken edges) | ~400+ | Medium (grid engine change) | Pending |
| New games for multi-constraint combos | ~170+ | High | Pending |

## Project Structure

```
arc-witness-envs/
├── witness_grid.py            # Shared grid renderer (64x64, 16-color)
├── tw01_pathdots.py           # PathDots game (ARCBaseGame subclass)
├── tw02_colorsplit.py         # ColorSplit game
├── tw03_shapefill.py          # ShapeFill game
├── tw04_symdraw.py            # SymDraw game
├── tw05_starpair.py           # StarPair game
├── tw06_tricount.py           # TriCount game
├── tw07_eraserlogic.py        # EraserLogic game
├── tw08_combobasic.py         # ComboBasic game
├── tw09_cylinderwrap.py       # CylinderWrap game
├── tw10_colorfilter.py        # ColorFilter game
├── test_games.py              # Automated test suite (506 validated levels)
├── play_human.py              # Local web server for browser play
├── environment_files/         # Game metadata (for SDK discovery)
│   ├── tw01/metadata.json
│   ├── tw02/metadata.json
│   ├── ...
│   └── tw10/metadata.json
├── levels/                    # Level configs with verified solutions
│   ├── tw01_levels.json       # 16 levels (10v + 6u)
│   ├── tw02_levels.json       # 36 levels (27v + 9u)
│   ├── tw03_levels.json       # 139 levels (47v + 92u)
│   ├── tw04_levels.json       # 28 levels (0v + 28u)
│   ├── tw05_levels.json       # 35 levels (26v + 9u)
│   ├── tw06_levels.json       # 123 levels (105v + 18u)
│   ├── tw07_levels.json       # 294 levels (221v + 73u)
│   ├── tw08_levels.json       # 73 levels (34v + 39u)
│   ├── tw09_levels.json       # 5 levels (hand-crafted)
│   └── tw10_levels.json       # 5 levels (hand-crafted)
└── converters/                # Puzzle extraction pipeline
    ├── unified_puzzle.py      # Intermediate data model + classifier
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
# 10/10 games, 506 validated levels verified (248 unvalidated skipped)
```

### Re-extract Levels

```bash
cd converters
python run_pipeline.py --keep-all
```

Pipeline: decode protobuf -> classify by game type -> convert coordinates -> solve with BFS/DFS -> calibrate baselines -> export JSON. Unsolved puzzles are kept as unvalidated levels.

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
├── draw_star()             → diamond-shaped star symbols
├── draw_triangle()         → 1-3 small triangles per cell
├── draw_polyomino()        → tetris piece preview
├── draw_eraser()           → Y-shaped eraser symbol
├── draw_unvalidated_indicator() → orange "?" for unverified levels
├── path_splits_regions()   → BFS region extraction
└── cell_edge_count()       → count path edges touching a cell
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
