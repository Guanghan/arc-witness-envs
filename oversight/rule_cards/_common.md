# Witness rule-card conventions (shared)

- **Actions:** `1`=UP, `2`=DOWN, `3`=LEFT, `4`=RIGHT, `5`=CONFIRM. `0`=RESET (restarts the current level).
- The player draws a **path** as a sequence of grid nodes; one move action extends the path by one node. A node cannot be revisited and the path cannot cross a **breakpoint** (a blocked edge between two nodes).
- **CONFIRM** submits the current path. If every constraint holds, the level is solved and the game advances to the next level.
- **Multiple starts:** some levels expose more than one start node; the first move auto-selects the start consistent with that direction.
- These cards are ground truth for the *oversight* Oracle only — they are never shown to a bare-eval agent.
