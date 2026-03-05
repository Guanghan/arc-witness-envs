from puzzle import Puzzle
from ttws_types import *

def decode_pb(code):
  """
  Decode a string from https://windmill.thefifthmatt.com

  For any puzzle, click on "edit", then "checkpoint".  There will be a long
  code in the URL, usually starting with "CA" and ending with "_0".  This a
  representation of the puzzle encoded using google protobuf, then base64
  encoded with a couple of final adjustements to make it URL friendly.

  e.g.
  CAUSAigEEgIIBBIAEgQIBxABEgASBAgHEAESAigHEgQIBxABEgASBAgHEAISABICCAMSAigE_0
  """

  import base64
  import grid_pb2

  # Strip off everything before the final /, in case this is a complete URL
  code = code.replace("\x00", "").strip().split("/")[-1]

  # Provided code needs the _0 removed from the end and two replacements
  if code.endswith("_0"):
    code = code[:-2]
  code = code.replace("_", "/").replace("-", "+")

  storage = grid_pb2.Storage()
  storage.ParseFromString(base64.decodestring(code))

  # Storage is run-length encoded like this:
  # +---+---+---+    n-v-n-v-n-v-n
  # |   |   |   |    h c h c h c h
  # +---+---+---+ -> n-v-n-v-n-v-n
  # |   |   |   |    h c h c h c h
  # +---+---+---+    n-v-n-v-n-v-n
  # So reading each entity in order provides node, v-edge, node, v-edge...,
  #                                     then h-edge, cell, h-edge, cell...
  # An exception to this is, if count is > 0, that number of entities are
  # skipped

  storage_width = storage.width

  width = storage_width / 2
  total_count = 0
  for entity in storage.entity:
    if entity.count:
      total_count += entity.count
    else:
      total_count += 1
  height = (total_count / storage_width) / 2

  storage_height = total_count / storage_width

  symmetry_map = {grid_pb2.UNKNOWN_SYMMETRY: SymmetryType.NONE,
                  grid_pb2.NO_SYMMETRY: SymmetryType.NONE,
                  grid_pb2.HORIZONTAL: SymmetryType.HORIZONTAL,
                  grid_pb2.VERTICAL: SymmetryType.VERTICAL,
                  grid_pb2.ROTATIONAL: SymmetryType.ROTATIONAL}

  colour_map = {grid_pb2.BLACK: Colour.BLACK, grid_pb2.WHITE: Colour.WHITE,
                grid_pb2.CYAN: Colour.CYAN, grid_pb2.MAGENTA: Colour.MAGENTA,
                grid_pb2.YELLOW: Colour.YELLOW, grid_pb2.RED: Colour.RED,
                grid_pb2.GREEN: Colour.GREEN, grid_pb2.BLUE: Colour.BLUE,
                grid_pb2.ORANGE: Colour.ORANGE}

  node_map = {grid_pb2.UNKNOWN_ENUM: NodeType.NONE,
              grid_pb2.NONE: NodeType.NONE,
              grid_pb2.START: NodeType.START,
              grid_pb2.END: NodeType.END,
              grid_pb2.HEXAGON: NodeType.HEXAGON}

  edge_map = {grid_pb2.UNKNOWN_ENUM: EdgeType.NONE,
              grid_pb2.NONE: EdgeType.NONE,
              grid_pb2.DISJOINT: EdgeType.MISSING,
              grid_pb2.HEXAGON: EdgeType.HEXAGON}

  cell_map = {grid_pb2.UNKNOWN_ENUM: CellType.NONE,
              grid_pb2.NONE: CellType.NONE,
              grid_pb2.TRIANGLE: CellType.TRIANGLE,
              grid_pb2.SQUARE: CellType.SQUARE,
              grid_pb2.STAR: CellType.STAR,
              grid_pb2.ERROR: CellType.Y,
              grid_pb2.TETRIS: CellType.TETRIS}

  puzzle = Puzzle(width, height)

  puzzle.symmetry = symmetry_map[storage.symmetry]

  current_entity = 0
  for entity in storage.entity:
    if entity.count:
      # This entity just skips forward
      current_entity += entity.count
      continue

    # Navigate through the 2D entity array
    entity_y = current_entity / storage_width
    entity_x = current_entity % storage_width

    # Translate into x, y coordinates of the node, edge or cell array
    y = entity_y / 2
    x = entity_x / 2

    if entity_y % 2 == 0:
      # This is a node/v-edge line
      if entity_x % 2 == 0:
        # This is a node
        # Note: start and end nodes which are also hexagons are not supported
        # Note: hexagons can only be one colour
        puzzle.nodes[y][x] = Node(type=node_map[entity.type])

      else:
        # This is a v-edge
        # Note: hexagons can only be one colour
        puzzle.v_edges[y][x] = Edge(type=edge_map[entity.type])

    else:
      # This is an h-edge/cell line
      if entity_x % 2 == 0:
        # This is an h-edge
        # Note: hexagons can only be one colour
        puzzle.h_edges[y][x] = Edge(type=edge_map[entity.type])

      else:
        # This is a cell
        cell = Cell(type=cell_map[entity.type])

        if cell.is_triangle():
          cell.triangle.number = entity.triangle_count
        elif cell.is_square():
          cell.square.colour = colour_map[entity.color]
        elif cell.is_star():
          cell.star.colour = colour_map[entity.color]
        elif cell.is_tetris():
          shape = []
          index = 0
          for ty in range(len(entity.shape.grid) / entity.shape.width):
            for tx in range(5):
              if tx < entity.shape.width:
                if entity.shape.grid[index]:
                  shape.append((tx, ty))
                index += 1

          cell.tetris.shape = shape
          if entity.shape.free:
            cell.tetris.rotated = True
          if entity.shape.negative:
            cell.tetris.negative = True

        puzzle.cells[y][x] = cell

    current_entity += 1

  return puzzle
