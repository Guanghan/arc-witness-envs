import time, random
from collections import defaultdict
from itertools import combinations
from ttws_types import *

class Puzzle(object):
  def __init__(self, width, height):
    """
    For width = 3, height = 2:

    Cells            Nodes              V Edges          H Edges
    +---+---+---+    N---N---N---N      +-V-+-V-+-V-+    +---+---+---+
    | C | C | C |    |   |   |   |      |   |   |   |    H   H   H   H
    +---+---+---+    N---N---N---N      +-V-+-V-+-V-+    +---+---+---+
    | C | C | C |    |   |   |   |      |   |   |   |    H   H   H   H
    +---+---+---+    N---N---N---N      +-V-+-V-+-V-+    +---+---+---+
    3 x 2 - w x h    4 x 3 - w+1 x h+1  3 x 3 - w x h+1  4 x 2 - w+1 x h
    """
    self.width = width
    self.height = height

    self.symmetry = SymmetryType.NONE

    # Initialise to lists of the correct sizes
    self.cells   = [[Cell() for x in range(self.width)]
                     for y in range(self.height)]
    self.nodes   = [[Node() for x in range(self.width + 1)]
                     for y in range(self.height + 1)]
    self.v_edges = [[Edge() for x in range(self.width)]
                     for y in range(self.height + 1)]
    self.h_edges = [[Edge() for x in range(self.width + 1)]
                     for y in range(self.height)]

    # Path is a list of (x, y) node coordinates, e.g. path = [(0, 0), (0, 1)],
    # always ordered from start node to end node
    self.path = []
    self.path_attempts = 0
    self.solution_found = False

    # A list of areas calculated by the solver
    self.areas = []

    # Yield to observers after yield_interval to allow some other processing
    # to take place while the puzzle is being solved
    self.observers = []
    self.yield_time = None
    self.yield_interval = 0.1

    # Whether the puzzle is currently being solved or not
    self.keep_solving = False

    self.start_time = None
    self.time_taken = 0

    self.message = ""

  def register_observer(self, callback):
    self.observers.append(callback)

  def notify_observers(self):
    self.time_taken = time.time() - self.start_time
    for callback in self.observers:
      callback()

  def randomise(self):
    """Generate a random puzzle."""

    # Map of colours for randomisation
    colour_map = {0: Colour.WHITE, 1: Colour.BLACK, 2: Colour.RED,
                  3: Colour.GREEN, 4: Colour.BLUE, 5: Colour.CYAN,
                  6: Colour.YELLOW, 7: Colour.ORANGE, 8: Colour.MAGENTA}

    # Put in two start nodes, two end nodes, two node hexagons, one v edge
    # hexagon and one h edge hexagon
    rand_height = lambda x=0: random.randint(0, self.height - x)
    rand_width  = lambda x=0: random.randint(0, self.width - x)
    for i in range(2):
      self.nodes[rand_height()][rand_width()].type = NodeType.START
      node = Node(type=NodeType.HEXAGON, hexagon=Hexagon())
      self.nodes[rand_height()][rand_width()] = node
    edge = Edge(type=EdgeType.HEXAGON, hexagon=Hexagon())
    self.v_edges[rand_height()][rand_width(1)] = edge
    edge = Edge(type=EdgeType.HEXAGON, hexagon=Hexagon())
    self.h_edges[rand_height(1)][rand_width()] = edge
    for i in range(2):
      edge = random.randint(0, 3)
      if edge == 0:
        self.nodes[0][rand_width()].type = NodeType.END
      elif edge == 1:
        self.nodes[self.height][rand_width()].type = NodeType.END
      elif edge == 2:
        self.nodes[rand_height()][0].type = NodeType.END
      elif edge == 3:
        self.nodes[rand_height()][self.width].type = NodeType.END

    # Randomise cells
    for x in range(self.width):
      for y in range(self.height):
        # Cell types only go up to 5 - generating numbers up to 10 provides a
        # higher chance a cell will be empty
        cell_type = random.randint(0, 10)
        if cell_type > 5:
          cell = Cell()
        else:
          cell = Cell(cell_type)
        if cell.type == CellType.SQUARE:
          cell.square = Square(colour=colour_map[random.randint(0, 8)])
        elif cell.type == CellType.TRIANGLE:
          cell.triangle = Triangle(number=random.randint(1, 3))
        elif cell.type == CellType.STAR:
          cell.star = Star(colour=colour_map[random.randint(0, 8)])
        elif cell.type == CellType.TETRIS:
          cell.tetris = Tetris()
          shape = []
          # Generate up to 5 joined together cells
          xy = [0, 0]
          for n in range(0, random.randint(1, 5)):
            # Randomly move left, right, up, down
            xy[random.randint(0, 1)] += random.randint(-1, 1)
            shape.append(xy[:])
          cell.tetris.shape = shape
          cell.tetris.rotated = True if random.randint(0, 1) else False
          cell.tetris.negative = True if random.randint(0, 1) else False
        self.cells[y][x] = cell


  def define_areas(self, path_h_edges, path_v_edges):
    """Start from the top-left and flood fill to define each area."""

    # A list of the cells in each area
    areas = []

    # Keep track of every visited cell
    visited = set()

    # Look at every cell to see if it's the start a new area
    for visit_y in range(self.height):
      for visit_x in range(self.width):
        if (visit_x, visit_y) in visited:
          continue

        # Start a new area
        area = set()
        queue = [(visit_x, visit_y)]

        while queue:
          x, y = queue.pop(0)
          # Look for adjacent cells within the path that we have not already
          # visited
          if x > 0 and (x, y) not in path_h_edges.union(area):
            queue.append((x - 1, y))

          if x < self.width - 1 and (x + 1, y) not in path_h_edges.union(area):
            queue.append((x + 1, y))

          if y > 0 and (x, y) not in path_v_edges.union(area):
            queue.append((x, y - 1))

          if y < self.height - 1 and (x, y + 1) not in path_v_edges.union(area):
            queue.append((x, y + 1))

          area.add((x, y))
          visited.add((x, y))

        # This area is filled, add to the list of areas
        areas.append(area)

    return areas

  def solve_yellow_tetris(self, area, pieces):
    """
    Attempt to exactly fit all given tetris pieces into the given area using
    Algorithm X (https://en.wikipedia.org/wiki/Knuth%27s_Algorithm_X).
    """

    # Neat Python implementation of Algirthm X:
    # http://www.cs.mcgill.ca/~aassaf9/python/algorithm_x.html
    def exact_cover(X, Y, solution=[]):
        if not X:
            yield list(solution)
        else:
            c = min(X, key=lambda c: len(X[c]))
            for r in list(X[c]):
                # Yield to observers
                self.yield_check()
                if not self.keep_solving:
                    yield False
                solution.append(r)
                cols = select(X, Y, r)
                for s in exact_cover(X, Y, solution):
                    yield s
                deselect(X, Y, r, cols)
                solution.pop()

    def select(X, Y, r):
        cols = []
        for j in Y[r]:
            for i in X[j]:
                for k in Y[i]:
                    if k != j:
                        X[k].remove(i)
            cols.append(X.pop(j))
        return cols

    def deselect(X, Y, r, cols):
        for j in reversed(Y[r]):
            X[j] = cols.pop()
            for i in X[j]:
                for k in Y[i]:
                    if k != j:
                        X[k].add(i)

    # Solve using Algorithm X

    # Add each cell to columns
    cols = set()
    for x, y in area:
      cols.add((x, y))

    # Add each piece to columns
    for piece in pieces:
      cols.add(piece)

    # Add a row for every rotation of every piece (if it fits in the area)
    rows = {}
    for piece in pieces:
      for rotation in piece.shapes:
        for x, y in area:
          piece_area = set()
          for px, py in rotation:
            cell = (x + px, y + py)
            if cell in area:
              piece_area.add(cell)

          if len(piece_area) == piece.count:
            # This rotation fits, add the piece to the row
            n = (piece, tuple(rotation), (x, y))
            if n in rows and piece not in rows[n]:
              rows[n].append(piece)
            else:
              rows[n] = [piece]
            # Also add all cell locations
            rows[n].extend(piece_area)

    cols = {j: set() for j in cols}
    for i in rows:
        for j in rows[i]:
            cols[j].add(i)

    try:
      solution = exact_cover(cols, rows).next()
      if not solution:
        return False
      # A solution was found
      return True
    except StopIteration:
      # All possibilities exhausted
      return False


  def solve_blue_tetris(self, area, pieces):
    """
    Work out valid area shapes for a given set of tetris pieces containing at
    least one blue and one yellow piece.

    As a blue tetris piece can be in a valid position outside of an area, there
    is no way (that I can come up with) to validate an area containing a blue
    tetris piece.

    A further complication is that yellow tetris pieces can overlap and then be
    cancelled out by a blue tetris piece.

    So, here, we try every possible combination of tetris pieces which will fit
    onto the board and store all valid areas.
    """

    # Make the set of pieces sorted and immutable so we can store it and search
    # for it in a set
    pieces = tuple(sorted(pieces))

    def recurse(original_area, pieces, n=0):
      """
      Layer the pieces over the board in every combination
      - yellow pieces add one to the cell count
      - blue pieces subtract one from the cell count
      - if any cell falls outside the puzzle area, it is not a valid
        combination
      For every combination tested:
      - if the area contains only zeroes and ones, the ones form a valid
        area shape
      - if the area contains only zeroes, this combination of pieces is always
        valid (because blues and yellows cancel each other out).

      Only evaluate the area if it contains all given pieces and they all fit.
      """

      # Find remaining number of yellow and blue pieces (not including this one)
      remaining_yellows = 0
      remaining_blues = 0
      for p in range(n + 1, len(pieces)):
        if pieces[p].negative:
          remaining_blues += 1
        else:
          remaining_yellows += 1

      for rotation in pieces[n].shapes:
        for x in range(self.width):
          for y in range(self.height):
            self.yield_check()
            if not self.keep_solving:
              return
            area = original_area.copy()
            cells = []
            fits = True
            for px, py in rotation:
              cell = (x + px, y + py)
              if cell not in area:
                fits = False
                break
              cells.append(cell)

            if fits:
              valid = True

              # This piece fits, update area count
              for cell in cells:
                if pieces[n].negative:
                  area[cell] -= 1
                else:
                  area[cell] += 1

                # If there are not enough pieces left to ever get this cell back
                # to being valid, area is invalid
                if area[cell] != 0 \
                  and (remaining_yellows < -(area[cell] - 1) \
                       or remaining_blues < area[cell] - 1):
                  valid = False
                  break

              if valid:
                if n == len(pieces) - 1:
                  # All pieces fit into the area, see if this is a valid
                  # area and capture the shape
                  valid_area = []
                  for cell, count in area.iteritems():
                    if count < 0 or count > 1:
                      # This cannot be a valid area
                      valid = False
                      break
                    if count == 1:
                      valid_area.append(cell)
                  if valid:
                    self.blue_tetris_areas[pieces].add(frozenset(valid_area))
                else:
                  # There are still more pieces to go, recurse
                  recurse(area.copy(), pieces, n + 1)

    # Check if we've already worked out this combination of pieces
    if pieces not in self.blue_tetris_areas:
      # Add this combination of pieces to the map
      self.blue_tetris_areas[pieces] = set()

      # Build an area the size of the board, with all cells initially set to
      # 0
      board_area = {(x, y): 0 for x in range(self.width) \
                        for y in range(self.height)}

      recurse(board_area, pieces)

    if area in self.blue_tetris_areas[pieces] or \
         frozenset([]) in self.blue_tetris_areas[pieces]:
      # An empty set means yellow and blue cancel each other out
      # completely so any area is valid
      return True
    else:
      # Invalid area
      return False


  def solve_squares_and_stars(self, area, fixed, remaining_errors):
    """
    Look through all possible valid combinations of squares and stars, taking
    fixed pieces (triangles, yellow tetris and blue tetris pieces) into account.
    """

    # Keep track of which colours need to be considered
    colours = set()

    # Count the number of stars and squares in this area and store by colour
    stars = defaultdict(int)
    squares = defaultdict(int)
    for x, y in area:
      cell = self.cells[y][x]
      if cell.is_square():
        squares[cell.square.colour] += 1
        colours.add(cell.square.colour)
      elif cell.is_star() and (x, y) not in self.removed_pieces:
        # Do not consider stars which have already been removed
        stars[cell.star.colour] += 1
        colours.add(cell.star.colour)

    if not stars and not squares:
      return True, set()

    for colour in fixed:
      colours.add(colour)

    # Number of squares and stars of each colour which have been removed
    removed_square_count = defaultdict(int)
    removed_star_count = defaultdict(int)
    valid = False

    # If there are squares, just loop over squares as at least one square must
    # be involved in the solution
    # Otherwise, loop over every colour, i.e. stars and fixed items
    for colour in squares.keys() or colours:
      # The number of elimination marks required to make this colour valid
      errors = 0
      # Reset removed square count
      removed_square_count.clear()
      removed_star_count.clear()

      # If there are squares of this colour, all other squares must be
      # eliminated
      if squares[colour] > 0:
        for square_colour in colours:
          if square_colour != colour:
            removed_square_count[square_colour] += squares[square_colour]
            errors += squares[square_colour]

      # More squares need removing than we have elimination marks for
      if errors > remaining_errors:
        continue

      for star_colour in colours:
        # If there are no stars of this colour, do nothing

        # Number of fixed items of this star colour
        fixed_count = fixed[star_colour] \
          + (squares[star_colour] - removed_square_count[star_colour])

        # If there is one star there must be exactly one fixed item, otherwise
        # remove the star
        if stars[star_colour] == 1 and fixed_count != 1:
          removed_star_count[star_colour] = 1
          errors += 1

        # If there are two stars there must be exactly no fixed items, otherwise
        # remove both stars
        if stars[star_colour] == 2 and fixed_count != 0:
          removed_star_count[star_colour] = 2
          errors += 2

      # Check if this colour combination uses up all the elimination marks
      if errors == remaining_errors:
        valid = True
        break

    if not valid:
      return False, set()

    removed_stars_squares = set()
    # We have a count of how many of which colour of stars and squares can be
    # eliminated, so we need to find the cells of appropriate stars and squares
    # in the area
    for x, y in area:
      cell = self.cells[y][x]
      if cell.is_square() and removed_square_count[cell.square.colour] > 0:
        removed_stars_squares.add((x, y))
        removed_square_count[cell.square.colour] -= 1
      if cell.is_star() and removed_star_count[cell.star.colour] > 0 \
        and (x, y) not in self.removed_pieces:
        removed_stars_squares.add((x, y))
        removed_star_count[cell.star.colour] -= 1

    return True, removed_stars_squares


  def symmetry_path(self, path):
    """
    If this puzzle is symmetrical, return a symmetrical path to the one given.
    """
    symmetry_path = []
    if self.symmetry == SymmetryType.HORIZONTAL:
      symmetry_path = [(self.width - x, y) for x, y in path]
    elif self.symmetry == SymmetryType.VERTICAL:
      symmetry_path = [(x, self.height - y) for x, y in path]
    elif self.symmetry == SymmetryType.ROTATIONAL:
      symmetry_path = [(self.width - x, self.height - y) for x, y in path]

    return symmetry_path


  def symmetry_xy(self, x, y):
    """If this puzzle is symmetrical, return the symmetrical (x, y) node."""
    if self.symmetry == SymmetryType.HORIZONTAL:
      return (self.width - x, y)
    elif self.symmetry == SymmetryType.VERTICAL:
      return (x, self.height - y)
    elif self.symmetry == SymmetryType.ROTATIONAL:
      return (self.width - x, self.height - y)

    return None


  def validate_path(self, path, symmetry_path):
    """See if the given path is a valid solution."""

    invalid_areas = []

    # Step 1 - the last point in the path must be an end node
    if path[-1] not in self.end_nodes:
      return False, invalid_areas

    # Make this path available for observers to pick up
    self.path = path

    # Store the vertical and horizontal edges of the path
    path_v_edges = set()
    path_h_edges = set()
    x, y = path[0]
    for next_x, next_y in path[1:]:
      if x == next_x:
        path_h_edges.add((x, min(y, next_y)))
      elif y == next_y:
        path_v_edges.add((min(x, next_x), y))

      x = next_x
      y = next_y

    # Store the vertical and horizontal edges of the symmetrical path
    if self.symmetry != SymmetryType.NONE:
      x, y = symmetry_path[0]
      for next_x, next_y in symmetry_path[1:]:
        if x == next_x:
          path_h_edges.add((x, min(y, next_y)))
        elif y == next_y:
          path_v_edges.add((min(x, next_x), y))

        x = next_x
        y = next_y

    # Step 2 - work out which areas the path defines to help solve many of the
    # other cell types
    # Note, we cannot solve triangles or hexagons yet as they may depend on
    # elimination marks
    self.areas = self.define_areas(path_h_edges, path_v_edges)

    # Keep a set of which pieces have been removed by elimination marks
    self.removed_pieces = set()
    # And nodes and edges for removed hexagons
    self.removed_nodes = set()
    self.removed_v_edges = set()
    self.removed_h_edges = set()

    for area in self.areas:
      area_valid = True

      # Number of errors allowed, i.e. how many eliminations marks there are
      allowed_errors = 0
      for y in self.y:
        if y in area:
          # Record elimination marks as removed pieces
          self.removed_pieces.add(y)
          allowed_errors += 1

      # Count the total number of errors found in this area
      total_errors = 0

      # Number of coloured objects (which are not in error)
      colour_count = defaultdict(int)

      # Step 3 - triangles
      for triangle in self.triangles:
        if triangle in area:
          x, y = triangle
          # Count the edges around this triangle
          edge_count = 0
          if (x, y) in path_h_edges:
            edge_count += 1
          if (x, y) in path_v_edges:
            edge_count += 1
          if (x + 1, y) in path_h_edges:
            edge_count += 1
          if (x, y + 1) in path_v_edges:
            edge_count += 1
          # Edge count must equal the number of triangles in the cell
          if edge_count != self.cells[y][x].triangle.number:
            total_errors += 1
            self.removed_pieces.add(triangle)
          else:
            colour_count[Colour.ORANGE] += 1

          if total_errors > allowed_errors:
            area_valid = False
            break

      if not area_valid:
        invalid_areas.append(area)
        continue

      # Store the nodes, vertical and horizontal edges which are within the
      # area, i.e. not on the path
      area_nodes = set()
      area_v_edges = set()
      area_h_edges = set()
      for x, y in area:
        for node in [(x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)]:
          if node not in path + symmetry_path:
            area_nodes.add(node)

        for v_edge in [(x, y), (x, y + 1)]:
          if v_edge not in path_v_edges:
            area_v_edges.add(v_edge)

        for h_edge in [(x, y), (x + 1, y)]:
          if h_edge not in path_h_edges:
            area_h_edges.add(h_edge)

      # Step 4 - hexagons within the area (not on the path) are errors
      for hexagon_node in self.hexagon_nodes:
        if hexagon_node in area_nodes:
          total_errors += 1
          self.removed_nodes.add(hexagon_node)
      for hexagon_v_edge in self.hexagon_v_edges:
        if hexagon_v_edge in area_v_edges:
          total_errors += 1
          self.removed_v_edges.add(hexagon_v_edge)
      for hexagon_h_edge in self.hexagon_h_edges:
        if hexagon_h_edge in area_h_edges:
          total_errors += 1
          self.removed_h_edges.add(hexagon_h_edge)

      if total_errors > allowed_errors:
        invalid_areas.append(area)
        continue

      # Step 5 - eliminate stars if there are more than 2 of a given colour
      if self.stars:
        colour_map = defaultdict(int)
        for x, y in [cell for cell in area if cell in self.stars]:
          star = self.cells[y][x].star
          if colour_map[star.colour] > 1:
            # We've already counted 2 stars of this colour, eliminate extras
            total_errors += 1
            self.removed_pieces.add((x, y))
          colour_map[star.colour] += 1

      if total_errors > allowed_errors:
        invalid_areas.append(area)
        continue

      # Step 6 - tetris
      # We must work out tetris now because it's not possible to know which
      # yellow and blue squares and stars can be eliminated until we know which
      # combinations of tetris pieces may be removed

      # Find cells in this area containing tetris pieces
      tetris_cells = [cell for cell in area if cell in self.tetris]
      # Iterate over all possible combinations of tetris pieces, given that
      # zero or more may be eliminated
      tetris_solved = False
      # Consider removing from 0 to number of tetris pieces,
      # or from 0 to number of remaining elimination marks, whichever is smaller
      for tetris_errors in range(min(len(tetris_cells),
                                     allowed_errors - total_errors) + 1):
        for tetris_cells_combination in \
          combinations(tetris_cells, len(tetris_cells) - tetris_errors):
          # tetris_cells_combination is now all possible combinations of
          # tetris pieces given that tetris_errors have been eliminated

          # Remove previous attempts
          self.removed_pieces.difference_update(set(tetris_cells))

          # Collect tetris pieces and count total number of blue and yellow
          # cells
          blue_count = 0
          yellow_count = 0
          pieces = set()
          for x, y in tetris_cells_combination:
            piece = self.cells[y][x].tetris
            if piece.negative:
              blue_count += piece.count
            else:
              yellow_count += piece.count
            pieces.add(piece)

          valid_combination = True
          if blue_count == 0:
            # Just yellow pieces

            if yellow_count == 0:
              # No yellow or blue pieces, i.e. there are no tetris pieces in
              # this area
              pass

            # Make sure the number of tetris cells equals the size of the area
            elif yellow_count != len(area):
              valid_combination = False

            elif not self.solve_yellow_tetris(area, pieces):
              valid_combination = False

          else:
            if yellow_count == 0:
              # Just blue pieces, cannot solve
              valid_combination = False

            # Blue and yellow pieces

            # Make sure there are at least as many yellow cells as blue
            elif blue_count > yellow_count:
              valid_combination = False

            elif not self.solve_blue_tetris(area, pieces):
              valid_combination = False

          if not valid_combination:
            continue

          tetris_solved = True
          # This combination of tetris pieces is valid (or there are no tetris
          # pieces)

          # Record how many blue and yellow pieces must remain
          colour_count[Colour.BLUE] = 0
          colour_count[Colour.YELLOW] = 0
          for x, y in tetris_cells_combination:
            if self.cells[y][x].tetris.negative:
              colour_count[Colour.BLUE] += 1
            else:
              colour_count[Colour.YELLOW] += 1

          remaining_errors = allowed_errors - (total_errors + tetris_errors)

          # Step 7 - solve squares and stars which, if present, must use up all
          # remaining elimination marks
          valid, removed_squares_stars = \
            self.solve_squares_and_stars(area, colour_count,
              remaining_errors)

          if not valid or len(removed_squares_stars) != remaining_errors:
            area_valid = False
            break

          # Record tetris pieces, squares and stars which were removed
          self.removed_pieces.update(\
            set(tetris_cells) - set(tetris_cells_combination),
            removed_squares_stars)

        if not area_valid:
          break

      # No valid solutions
      if not area_valid or not tetris_solved:
        invalid_areas.append(area)
        continue

    if invalid_areas:
      return False, invalid_areas

    # A solution has been found
    return True, None


  def yield_check(self):
    """See if it's time to yield to observers."""

    if time.time() > self.yield_time:
      # Allow observers to do some processing
      self.notify_observers()
      self.yield_time = time.time() + self.yield_interval


  def check_all_paths(self, start_node):
    """Look at every possible path from the given start node."""

    # A queue of paths to search
    queue = [[start_node]]

    while queue:
      # Fetch the next path on the queue
      path = queue.pop()

      self.path_attempts += 1

      self.yield_check()

      # Solving has been cancelled
      if not self.keep_solving:
        return

      symmetry_path = self.symmetry_path(path)

      # Check this path for a solution
      # If this path is not valid, return which areas caused the problem
      valid, invalid_areas = self.validate_path(path, symmetry_path)

      if valid:
        self.solution_found = True
        return

      # Consider each invalid area
      for invalid_area in invalid_areas:

        # If there are multiple end nodes on the board, an area containing an
        # end node which is not part of that path can be incorrectly marked as
        # invalid, so these are identified and ignored
        ignore_end_node = False

        # Check that this area doesn't contain an end node not on the path
        if len(self.end_nodes) > 1:
          for x, y in invalid_area:
            for node in [(x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)]:
              if node in self.end_nodes \
                and (node != path[-1] \
                or (symmetry_path and node != symmetry_path[-1])):
                ignore_end_node = True
                # Drop out of inner loop
                break
            # Drop out of outer loop
            if ignore_end_node:
              break

        # Skip to the next invalid area
        if ignore_end_node:
          continue

        # Work out which portion of the path/symmetry path defines the invalid
        # area and remove matching entries from the queue
        invalid_path = set()
        for current_path in (path, symmetry_path):
          for x, y in current_path:
            for node in [(x, y), (x - 1, y), (x, y - 1), (x - 1, y - 1)]:
              if node in invalid_area:
                invalid_path.add((x, y))

        # Remove invalid paths from the queue
        for n in range(len(queue) - 1, -1, -1):
          if invalid_path.issubset(set(queue[n])):
            del queue[n]

      if invalid_areas and not ignore_end_node:
        continue

      # Check each direction from the end of this path
      x, y = path[-1]

      directions = [0, 1, 2, 3]
      if self.randomise:
        random.shuffle(directions)

      for direction in directions:
        if direction == 0 and x > 0:
          # Try left if we're not at the left wall
          next_node = (x - 1, y)

        elif direction == 1 and y > 0:
          # Try up if we're not at the top wall
          next_node = (x, y - 1)

        elif direction == 2 and x < self.width:
          # Try right if we're not at the right wall
          next_node = (x + 1, y)

        elif direction == 3 and y < self.height:
          # Try down if we're not at the bottom wall
          next_node = (x, y + 1)

        else:
          continue

        # See if the next node is already part of the path
        if next_node in path:
          continue

        # See if the next edge is a missing edge
        next_x, next_y = next_node
        if (x == next_x and                                              \
            self.h_edges[min(y, next_y)][x].type == EdgeType.MISSING) or \
           (y == next_y and                                              \
            self.v_edges[y][min(x, next_x)].type == EdgeType.MISSING):
          continue

        if self.symmetry != SymmetryType.NONE:
          # See if the next node is already part of the symmetry path or the
          # next node on the symmetry path
          next_symmetry_node = self.symmetry_xy(next_x, next_y)
          if next_node in symmetry_path + [next_symmetry_node]:
            continue

          # See if the next edge on the symmetry path is a missing edge
          sx, sy = symmetry_path[-1]
          next_x, next_y = next_symmetry_node
          if (sx == next_x and                                               \
              self.h_edges[min(sy, next_y)][sx].type == EdgeType.MISSING) or \
             (sy == next_y and                                               \
             self.v_edges[sy][min(sx, next_x)].type == EdgeType.MISSING):
            continue

        # Path is clear to analyse
        queue.append(path + [next_node])

    # All paths from this node have been tried and no solution was found
    return


  def populate_positions(self):
    """
    Searches through the puzzle once and stores the position of all node, edge
    and cell types in lists.  The solver can then just look in these lists
    lists rather than search through the puzzle.
    """

    # Lists of positions of various items, to help the solver iterate over
    # them more quickly
    self.start_nodes     = []
    self.end_nodes       = []
    self.hexagon_nodes   = []
    self.hexagon_v_edges = []
    self.hexagon_h_edges = []
    self.triangles       = []
    self.squares         = []
    self.stars           = []
    self.tetris          = []
    self.y               = []

    for x in range(self.width + 1):
      for y in range(self.height + 1):
        # Look for start and end nodes
        if self.nodes[y][x].is_start():
          # Do not process start nodes in half of the puzzle if there is
          # symmetry
          if self.symmetry == SymmetryType.NONE or           \
             (self.symmetry == SymmetryType.HORIZONTAL and   \
              x <= self.width / 2) or                        \
             (self.symmetry == SymmetryType.VERTICAL and     \
              y <= self.height / 2) or                       \
             (self.symmetry == SymmetryType.ROTATIONAL and   \
              (self.width - x, self.height - y) not in self.start_nodes):
            self.start_nodes.append((x, y))

        elif self.nodes[y][x].is_end():
          self.end_nodes.append((x, y))

        # Look for hexagons on edges and nodes
        if x < self.width and self.v_edges[y][x].is_hexagon():
          self.hexagon_v_edges.append((x, y))
        if y < self.height and self.h_edges[y][x].is_hexagon():
          self.hexagon_h_edges.append((x, y))
        if self.nodes[y][x].is_hexagon():
          self.hexagon_nodes.append((x, y))

        # Look in each cell
        if x < self.width and y < self.height:
          if self.cells[y][x].is_triangle():
            self.triangles.append((x, y))
          elif self.cells[y][x].is_square():
            self.squares.append((x, y))
          elif self.cells[y][x].is_star():
            self.stars.append((x, y))
          elif self.cells[y][x].is_tetris():
            self.tetris.append((x, y))
          elif self.cells[y][x].is_y():
            self.y.append((x, y))


  def solve(self, randomise=False):
    """
    Attempt to solve the puzzle.  If randomise is true, pick random start nodes
    and paths.  This can help if you can see the default paths are obviously
    poor.
    """

    # If puzzle is currently being solved, ignore further requests to solve it
    if self.keep_solving:
      return

    self.randomise = randomise
    self.message = "Solving..."
    self.solution_found = False
    self.keep_solving = True
    self.path = []
    self.path_attempts = 0
    self.time_taken = 0
    self.start_time = time.time()
    # Yield every yield_interval to allow observers to do some processing
    # (i.e. update screen)
    self.yield_time = self.start_time + self.yield_interval
    self.populate_positions()

    if not self.start_nodes:
      self.message = "Cannot solve: no start nodes"
      return

    if not self.end_nodes:
      self.message = "Cannot solve: no end nodes"
      return

    # A map from a set of tetris pieces to a set of valid areas
    self.blue_tetris_areas = {}

    # Sets of which pieces and edges were removed by elimination marks
    # (including the elimination marks)
    self.removed_pieces = set()
    self.removed_h_edges = set()
    self.removed_v_edges = set()

    if self.randomise:
      random.shuffle(self.start_nodes)
    for start_node in self.start_nodes:
      self.check_all_paths(start_node)
      if self.solution_found:
        break

    if not self.keep_solving:
      return

    if self.solution_found:
      self.message = "Solved!"

    else:
      self.path = []
      self.message = "Cannot solve: tried all possibilities"

    self.time_taken = time.time() - self.start_time
    self.keep_solving = False
