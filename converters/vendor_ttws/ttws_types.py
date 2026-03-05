# General types

class Colour:
  LIGHT_GREY = (127, 127, 127)
  DARK_GREY  = ( 84,  84,  84)
  WHITE      = (255, 255, 255)
  BLACK      = (  0,   0,   0)
  RED        = (255,   0,   0)
  GREEN      = (  0, 128,   0)
  BLUE       = (  0,   0, 255)
  CYAN       = (  0, 255, 255)
  YELLOW     = (255, 255,   0)
  ORANGE     = (255, 165,   0)
  MAGENTA    = (255,   0, 255)
  ERROR      = (170, 127, 127)
  # Convenient aliases
  BACKGROUND = LIGHT_GREY
  LINE       = DARK_GREY
  TRIANGLE   = ORANGE
  TETRIS     = YELLOW
  PATH       = WHITE

# Cell, node and edge types

class CellType:
  NONE        = 0
  SQUARE      = 1
  TRIANGLE    = 2
  STAR        = 3
  TETRIS      = 4
  Y           = 5 # Elimination mark

class NodeType:
  NONE          = 0
  START         = 1
  END           = 2
  HEXAGON       = 4
  START_HEXAGON = START | HEXAGON
  END_HEXAGON   = END | HEXAGON

class EdgeType:
  NONE    = 0
  MISSING = 1
  HEXAGON = 2

class SymmetryType:
  NONE       = 0
  HORIZONTAL = 1
  VERTICAL   = 2
  ROTATIONAL = 3

# Cell, node and edge properties

class Cell(object):
  def __init__(self, type=CellType.NONE):
    self.type        = type
    # Initialise given type
    if self.type == CellType.SQUARE:
      self.square = Square()
    elif self.type == CellType.TRIANGLE:
      self.triangle = Triangle()
    elif self.type == CellType.STAR:
      self.star = Star()
    elif self.type == CellType.TETRIS:
      self.tetris = Tetris()
    # Y doesn't have any properties

  def is_square(self):
    return self.type == CellType.SQUARE

  def is_triangle(self):
    return self.type == CellType.TRIANGLE

  def is_star(self):
    return self.type == CellType.STAR

  def is_tetris(self):
    return self.type == CellType.TETRIS

  def is_y(self):
    return self.type == CellType.Y


class Node(object):
  def __init__(self, type=NodeType.NONE, colour=Colour.LINE, hexagon=None):
    self.type = type
    # A node has a colour, which may not just be the line colour if it's
    # being drawn as part of a path
    self.colour = colour
    self.hexagon = hexagon
    # Initialise hexagon if it is required but not provided
    if self.type & NodeType.HEXAGON and self.hexagon is None:
      self.hexagon = Hexagon()

  def is_start(self):
    return self.type & NodeType.START

  def is_end(self):
    return self.type & NodeType.END

  def is_hexagon(self):
    return self.type & NodeType.HEXAGON

  def add_type(self, type):
    # As a node can have more than one type (e.g. start and hexagon), one
    # property can be added
    self.type = self.type | type

  def remove_type(self, type):
    # As a node can have more than one type (e.g. start and hexagon), one
    # property can be removed
    self.type = self.type & ~type


class Edge(object):
  def __init__(self, type=EdgeType.NONE, colour=Colour.LINE, hexagon=None):
    self.type = type
    # An edge has a colour, which may not just be the line colour if it's
    # being drawn as part of a path
    self.colour = colour
    self.hexagon = hexagon
    # Initialise hexagon if it is required but not provided
    if self.type == EdgeType.HEXAGON and self.hexagon is None:
      self.hexagon = Hexagon()

  def is_missing(self):
    return self.type == EdgeType.MISSING

  def is_hexagon(self):
    return self.type == EdgeType.HEXAGON

# Cell shape properties

class Square(object):
  def __init__(self, colour=Colour.WHITE):
    # A square has a colour
    self.colour = colour

class Triangle(object):
  def __init__(self, number=1):
    # One, two or three triangles
    self.number = number

class Star(object):
  def __init__(self, colour=Colour.WHITE):
    # A star has a colour
    self.colour = colour

class Tetris(object):
  def __init__(self, shape=None, rotated=False, negative=False):
    """
    A tetris piece.

    'shape' is a set() of (x, y) cells, which can be given as a list
     - it doesn't matter where these are,
       e.g. [(14, 17), (14, 18), (14, 19), (13, 18)] is fine.

    'rotated' is True if this piece can fit it in an area in any orientation.

    'negative' is True if this is a blue piece.

    When a shape is set, all rotations are calculated (if necessary) and they
    are all translated so that one cell is anchored at (0, 0).  This means
    duplicates will be removed, e.g. a vertical bar [(4, 5), (4, 6)] is rotated
    to
      [(-5,  4), (-6,  4)]  # 90 degrees
      [(-4, -5), (-4, -6)]  # 180 degrees
      [(5,  -4), (6,  -4)]  # 270 degrees
    and then translated to (0, 0):
      [(0, 0), (0, 1)]
      [(0, 0), (1, 0)]
      [(0, 0), (0, 1)]
      [(0, 0), (1, 0)]
    Duplicates are removed to give [(0, 0), (0, 1)] and [(0, 0), (1, 0)]

    If one cell in the piece is always (0, 0), it means that translating that
    piece to every cell in an area will definitely find a fit if it is possible.

    'shapes' will return a list of all rotated, translated shapes this piece can
    take.
    """

    # The number of cells in this shape
    self.count = 0

    # The original, given shape
    self._shape = None

    # A list of all possible rotations
    self.shapes = []

    # It may be fitted in any orientation
    self._rotated = rotated
    # A blue tetris piece
    self.negative = negative

    # A tetris block has a shape which is a number of (x, y) coordinates
    if shape is None:
      self.shape = set([(0, 0)])
    else:
      self.shape = shape

  @property
  def rotated(self):
    return self._rotated

  @rotated.setter
  def rotated(self, value):
    self._rotated = value
    # Update shapes when rotated property is updated
    self._calculate_rotations()

  @property
  def shape(self):
    return self._shape

  @shape.setter
  def shape(self, value):
    self._shape = value
    self.count = len(self._shape)
    self._calculate_rotations()

  def _calculate_rotations(self):
    shapes = [self._shape]
    if self._rotated:
      # Rotate 90 degrees
      shapes.append([(-y, x) for x, y in self._shape])
      # Rotate 180 degrees
      shapes.append([(-x, -y) for x, y in self._shape])
      # Rotate 270 degrees
      shapes.append([(y, -x) for x, y in self._shape])

    # Translate each shape so that one cell is (0, 0)
    # This means:
    #   1) translating the piece over each cell in a valid area must fit
    #      somewhere
    #   2) as all pieces are anchored at (0, 0), duplicates will be removed
    self.shapes = []
    for shape in shapes:
      min_x, min_y = min(shape)
      translated_shape = set([(x - min_x, y - min_y) for x, y in shape])
      if translated_shape not in self.shapes:
        self.shapes.append(translated_shape)


class Hexagon(object):
  def __init__(self, colour=Colour.BLACK):
    # A hexagon has a colour
    self.colour = colour
    self.has_error = False
