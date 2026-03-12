"""
unified_puzzle.py — Unified puzzle intermediate representation

Converts from ttws protobuf data to a unified format, then to game level_config.
"""
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Set


@dataclass
class UnifiedPuzzle:
    """Unified puzzle representation, source-agnostic."""
    # Grid dimensions (cell count)
    cols: int
    rows: int

    # Start and end points (node coordinates)
    starts: List[Tuple[int, int]] = field(default_factory=list)
    ends: List[Tuple[int, int]] = field(default_factory=list)

    # Constraint types
    hexagons: List[Tuple[int, int]] = field(default_factory=list)        # Required node waypoints
    hex_edges: List[Tuple[int, int, str]] = field(default_factory=list)  # Required edge waypoints: (x, y, 'h'|'v')
    squares: Dict[Tuple[int, int], str] = field(default_factory=dict)    # Colored squares cell->(color_name)
    stars: Dict[Tuple[int, int], str] = field(default_factory=dict)      # Stars cell->(color_name)
    triangles: Dict[Tuple[int, int], int] = field(default_factory=dict)  # Triangles cell->(count)
    tetris: Dict[Tuple[int, int], dict] = field(default_factory=dict)    # Polyominoes
    eliminations: List[Tuple[int, int]] = field(default_factory=list)    # Elimination markers

    # Symmetry
    symmetry: Optional[str] = None  # None, "horizontal", "vertical", "rotational"

    # Broken edges
    missing_edges: List[Tuple[int, int, str]] = field(default_factory=list)  # (x, y, 'h'|'v')

    # Metadata
    source: str = ""  # Source identifier
    source_index: int = 0  # Index within the source file

    def classify(self) -> str:
        """Classify puzzle type, returning the best-matching game identifier.

        Priority: tw07 (elim+other) > tw08 (sq+star) > tw01 (hex) > tw02 (sq) >
                  tw04 (sym) > tw05 (star) > tw06 (tri) > tw03 (tetris) > other
        """
        has_hex = bool(self.hexagons or self.hex_edges)
        has_sq = bool(self.squares)
        has_star = bool(self.stars)
        has_tri = bool(self.triangles)
        has_tetris = bool(self.tetris)
        has_elim = bool(self.eliminations)
        has_sym = self.symmetry is not None

        # tw07: elimination markers + at least one other constraint
        if has_elim and (has_sq or has_star or has_tri):
            return "tw07"

        # tw08: squares + stars combo (no other constraints)
        if has_sq and has_star and not has_hex and not has_tri and not has_tetris and not has_elim and not has_sym:
            return "tw08"

        # tw01: hexagon constraints only (required node waypoints)
        if has_hex and not has_sq and not has_star and not has_tri and not has_tetris and not has_elim and not has_sym:
            return "tw01"

        # tw02: square constraints only (colored square separation)
        if has_sq and not has_hex and not has_star and not has_tri and not has_tetris and not has_elim and not has_sym:
            return "tw02"

        # tw04: symmetry puzzles
        if has_sym:
            return "tw04"

        # tw05: stars only
        if has_star and not has_sq and not has_hex and not has_tri and not has_tetris and not has_elim:
            return "tw05"

        # tw06: triangles only
        if has_tri and not has_sq and not has_hex and not has_star and not has_tetris and not has_elim:
            return "tw06"

        # tw03: polyominoes only
        if has_tetris and not has_sq and not has_hex and not has_star and not has_tri and not has_elim:
            return "tw03"

        # tw13: remaining elim combos (tw07 already captures elim+(sq|star|tri))
        if has_elim:
            return "tw13"

        # tw12: hex + at least one region constraint (tw01 already captures pure hex)
        if has_hex and (has_sq or has_star or has_tri or has_tetris):
            return "tw12"

        # tw11: 2+ region constraints (no hex/elim/sym -- already captured above)
        region_count = sum([has_sq, has_star, has_tri, has_tetris])
        if region_count >= 2:
            return "tw11"

        return "other"

    def feature_set(self) -> Set[str]:
        """Return the set of features present in the puzzle."""
        features = set()
        if self.hexagons or self.hex_edges:
            features.add("hex")
        if self.squares:
            features.add("squares")
        if self.stars:
            features.add("stars")
        if self.triangles:
            features.add("triangles")
        if self.tetris:
            features.add("tetris")
        if self.eliminations:
            features.add("eliminations")
        if self.symmetry:
            features.add(f"sym_{self.symmetry}")
        if self.missing_edges:
            features.add("missing_edges")
        return features

    def unique_square_colors(self) -> int:
        """Number of distinct colors used by squares."""
        return len(set(self.squares.values()))
