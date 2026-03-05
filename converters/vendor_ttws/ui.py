import math, random, time, copy
import pygame
import pygame.gfxdraw
from ttws_types import *
from puzzle import Puzzle
from loader import decode_pb

# Taken from http://pygame.org/project-AAfilledRoundedRect-2349-.html
def aafilled_rounded_rect(surface, rect, colour, radius=0.4, angle=0):
    """
    Radius is corner radius, 0 for a square corner, 1 for a semi-circle end

    Angle is the rotation of the final object, rotated about the center point

    If smooth is true, smoothing is attempted by scaling up the surface,
    rotating and then downscaling.  This looks better for some rotations but not
    others.
    """

    rect         = pygame.Rect(rect)
    colour       = pygame.Color(*colour)
    alpha        = colour.a
    colour.a     = 0
    center       = rect.center
    rect.topleft = 0, 0
    rect_surf    = pygame.Surface(rect.size, pygame.SRCALPHA)

    circle       = pygame.Surface([min(rect.size) * 3] * 2, pygame.SRCALPHA)
    pygame.draw.ellipse(circle, (0, 0, 0),circle.get_rect(), 0)
    circle       = pygame.transform.smoothscale(circle, [int(min(rect.size) * radius)] * 2)

    radius              = rect_surf.blit(circle, (0, 0))
    radius.bottomright  = rect.bottomright
    rect_surf.blit(circle,radius)
    radius.topright     = rect.topright
    rect_surf.blit(circle,radius)
    radius.bottomleft   = rect.bottomleft
    rect_surf.blit(circle,radius)

    rect_surf.fill((0, 0, 0), rect.inflate(-radius.w, 0))
    rect_surf.fill((0, 0, 0), rect.inflate(0, -radius.h))

    rect_surf.fill(colour, special_flags=pygame.BLEND_RGBA_MAX)
    rect_surf.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MIN)

    # Rotate about the center point, with smooth scaling to provide
    # anti-aliasing if the angle is not likely to produce a good result
    smooth = angle % 90 != 0

    if smooth:
      rect_surf = pygame.transform.smoothscale(rect_surf, (rect_surf.get_width() * 2, rect_surf.get_height() * 2))
    rect_surf = pygame.transform.rotate(rect_surf, angle)
    if smooth:
      rect_surf = pygame.transform.smoothscale(rect_surf, (rect_surf.get_width() / 2, rect_surf.get_height() / 2))

    rotated_rect = rect_surf.get_rect()
    rotated_rect.center = center

    return surface.blit(rect_surf, rotated_rect)


def shade_rgb(colour, percent):
  """
  Lighten or darken an (R, G, B) colour
  percent of -1 is maximum darkening (black)
  percent of 1 is maximum lightening (white)

  Adapted from http://stackoverflow.com/questions/5560248/programmatically-lighten-or-darken-a-hex-color-or-rgb-and-blend-colors
  """
  t = 0.0 if percent < 0.0 else 255.0
  p = percent * -1.0 if percent < 0.0 else percent
  r, g, b = colour
  r = ((t - r) * p) + r
  g = ((t - g) * p) + g
  b = ((t - b) * p) + b
  return (int(r), int(g), int(b))

class UI(object):
  def __init__(self, puzzles=[]):
    self.current_puzzle = 0
    self.puzzle_codes = puzzles

    pygame.init()

    # Create a resizable screen area
    self.screen = pygame.display.set_mode((600, 600), pygame.RESIZABLE)

    pygame.scrap.init()

    clock = pygame.time.Clock()

    if self.puzzle_codes:
      self.puzzle = decode_pb(self.puzzle_codes[0])
    else:
      # Randomise first puzzle
      self.puzzle = Puzzle(random.randint(1, 6), random.randint(1, 5))
      self.puzzle.randomise()
      pygame.event.post(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_r}))

    self.initialise()
    # As soon as the event loop start, begin solving the first puzzle
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_s}))

    # Start main loop
    self.quit = False
    while not self.quit:
      # Limit frames per second
      clock.tick(30)
      self.process_events()

    pygame.quit()

  def process_events(self):
    # Fetch any waiting events
    events = pygame.event.get([pygame.VIDEORESIZE, pygame.QUIT, pygame.KEYDOWN, pygame.USEREVENT])
    for event in events:
      if event.type == pygame.VIDEORESIZE:
        self.screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
        self.calculate_sizes()

      elif event.type == pygame.QUIT:
        self.puzzle.keep_solving = False
        self.quit = True

      elif event.type == pygame.KEYDOWN:
        if pygame.key.name(event.key) == "q":
          self.puzzle.keep_solving = False
          self.quit = True
        elif pygame.key.name(event.key) == "n":
          self.puzzle.keep_solving = False
          self.puzzle = Puzzle(random.randint(1, 6), random.randint(1, 5))
          self.puzzle.randomise()
          self.initialise()
          self.puzzle.solve()
        elif pygame.key.name(event.key) == "s":
          self.puzzle.solve()
        elif pygame.key.name(event.key) == "r":
          self.puzzle.keep_solving = False
          self.puzzle.solve(randomise=True)
        elif pygame.key.name(event.key) == "right":
          # Load next puzzle
          if self.current_puzzle < len(self.puzzle_codes) - 1:
            self.puzzle.keep_solving = False
            self.current_puzzle += 1
            print "loading puzzle %s" % (self.current_puzzle + 1)
            self.puzzle = decode_pb(self.puzzle_codes[self.current_puzzle])
            self.initialise()
            self.puzzle.solve()
        elif pygame.key.name(event.key) == "left":
          # Load previous puzzle
          if self.current_puzzle > 0:
            self.puzzle.keep_solving = False
            self.current_puzzle -= 1
            print "loading puzzle %s" % (self.current_puzzle + 1)
            self.puzzle = decode_pb(self.puzzle_codes[self.current_puzzle])
            self.initialise()
            self.puzzle.solve()
        elif pygame.key.name(event.key) == "p":
          # Grab clipboard text
          text = pygame.scrap.get(pygame.SCRAP_TEXT)
          if not text:
            break

          try:
            # TODO: make the save/load mechanism better!
            self.puzzle = decode_pb(text)
          except:
            print "Cannot load puzzle from text '%s'" % text
            break

          # Puzzle is loadable - store it in a file
          f = open("pasted_puzzles", "a")
          f.write(text + "\n")
          f.close()
          self.puzzle_codes.insert(self.current_puzzle+1, text)
          self.initialise()
          self.puzzle.solve()

    # Clear events we're not interested in (e.g. mouse movements)
    pygame.event.clear()

    if events:
      # Don't redraw screen if no events have been processed
      self.draw_frame()

  def force_update(self):
    pygame.event.post(pygame.event.Event(pygame.USEREVENT))
    self.process_events()

  def initialise(self):
    self.calculate_sizes()
    self.puzzle.register_observer(self.force_update)

  def calculate_sizes(self):
    """Define some variables for scaling the puzzle"""
    width = self.screen.get_width()
    height = self.screen.get_height()

    # line_width determines all other sizes
    #
    # Resize whole puzzle to fit on screen, but not smaller than a line width of 5
    #   "4 + " is for the left/top margin (2 line widths) and bottom/right margin (2 line widths)
    #   "5 *" is for each cell
    #   height - 100 means there will always be 100 pixels at the bottom of
    #                the screen for status info
    self.line_width = max(5, min(width          / (4 + (5 * self.puzzle.width)),
                                 (height - 100) / (4 + (5 * self.puzzle.height))))

    # line_width needs to be odd otherwise nodes can extend beyond edges
    if self.line_width % 2 == 0:
      self.line_width += 1

    # Left and top margin - 2 line widths
    self.margin = self.line_width * 2

    # Each cell is 5 line widths, assuming the line_width was even!
    self.cell_size = (self.line_width - 1) * 5

    # For edges with a gap, this is the width of that gap
    self.gap_size = self.cell_size / 5

    # Each node is a circle (e.g. draws the corners of the puzzle) the
    # diameter of which must be the line width
    self.node_radius = self.line_width / 2

    self.ang = 0


  def find_v_edge_coords(self, x, y):
    """
    Given an (x, y) position in the puzzle, find the x_start, y_start, x_end,
    y_end coordinates of this vertical edge.
    """
    x_start = self.margin + (x * self.cell_size)
    x_end   = x_start + self.cell_size
    y_start = self.margin + (y * self.cell_size)
    y_end   = y_start

    return x_start, y_start, x_end, y_end

  def find_h_edge_coords(self, x, y):
    """
    Given an (x, y) position in the puzzle, find the x_start, y_start, x_end,
    y_end coordinates of this horizontal edge.
    """
    x_start = self.margin + (x * self.cell_size)
    x_end   = x_start
    y_start = self.margin + (y * self.cell_size)
    y_end   = y_start + self.cell_size

    return x_start, y_start, x_end, y_end

  def find_node_coords(self, x, y):
    """
    Given an (x, y) position in the puzzle, find the x_start, y_start, x_end,
    y_end coordinates of this node.
    """
    x_start = x_end = self.margin + (x * self.cell_size)
    y_start = y_end = self.margin + (y * self.cell_size)

    # End nodes are drawn differently around the edges so require a start
    # and end point
    if x == 0:
      # Node is on the left
      x_end -= self.line_width
    elif x == self.puzzle.width:
      # Node is on the right
      x_end += self.line_width

    if y == 0:
      # Node is at the top
      y_end -= self.line_width
    elif y == self.puzzle.height:
      # Node is at the bottom
      y_end += self.line_width

    return x_start, y_start, x_end, y_end


  def draw_path(self, path, colour):
    """Draw a path in the given colour."""

    for n in range(len(path)):
      x, y = path[n]

      # Draw edge from this path node to the next one
      if n < len(path) - 1:
        # Make sure start is top-left, end is bottom-right
        x_start = min(path[n][0], path[n + 1][0])
        x_end =   max(path[n][0], path[n + 1][0])
        y_start = min(path[n][1], path[n + 1][1])
        y_end =   max(path[n][1], path[n + 1][1])
        if x_start != x_end:
          # If there is a hexagon, lighten the colour so it looks like it's under
          # the path
          edge = copy.deepcopy(self.puzzle.v_edges[y_start][x_start])
          edge.colour = colour
          if edge.is_hexagon():
            edge.hexagon.colour = shade_rgb(edge.hexagon.colour, 0.75)
          x_start, y_start, x_end, y_end = self.find_v_edge_coords(x_start, y_start)
          self.draw_v_edge(edge, x_start, y_start, x_end, y_end)
        elif y_start != y_end:
          # If there is a hexagon, lighten the colour so it looks like it's under
          # the path
          edge = copy.deepcopy(self.puzzle.h_edges[y_start][x_start])
          edge.colour = colour
          if edge.is_hexagon():
            edge.hexagon.colour = shade_rgb(edge.hexagon.colour, 0.75)
          x_start, y_start, x_end, y_end = self.find_h_edge_coords(x_start, y_start)
          self.draw_h_edge(edge, x_start, y_start, x_end, y_end)

      # Draw node
      x_start, y_start, x_end, y_end = self.find_node_coords(x, y)
      # If there is a hexagon, lighten the colour so it looks like it's under
      # the path
      node = copy.deepcopy(self.puzzle.nodes[y][x])
      if node.is_hexagon():
        node.hexagon.colour = shade_rgb(node.hexagon.colour, 0.75)

      # If this is not the end of the path, remove end bit
      if n < len(path) - 1:
        node.remove_type(NodeType.END)
      else:
        # This is the end of the path - draw an extra circle to fill in the
        # corners (otherwise there's a gap at the corner nodes)
        end_node = Node(colour=colour)
        self.draw_node(end_node, x_start, y_start, x_end, y_end)

      node.colour = colour
      self.draw_node(node, x_start, y_start, x_end, y_end)


  def draw_frame(self):
    """Draw a single frame."""

    self.screen.fill(Colour.BACKGROUND)

    # Draw vertical edges
    for y in range(self.puzzle.height + 1):
      for x in range(self.puzzle.width):
        # Mark hexagons as in error or not
        edge = self.puzzle.v_edges[y][x]
        if edge.is_hexagon():
          edge.hexagon.has_error = False
          if self.puzzle.solution_found and (x, y) in self.puzzle.removed_v_edges:
            edge.hexagon.has_error = True
        x_start, y_start, x_end, y_end = self.find_v_edge_coords(x, y)
        self.draw_v_edge(edge, x_start, y_start, x_end, y_end)

    # Draw horizontal edges
    for y in range(self.puzzle.height):
      for x in range(self.puzzle.width + 1):
        # Mark hexagons as in error or not
        edge = self.puzzle.h_edges[y][x]
        if edge.is_hexagon():
          edge.hexagon.has_error = False
          if self.puzzle.solution_found and (x, y) in self.puzzle.removed_h_edges:
            edge.hexagon.has_error = True      
        x_start, y_start, x_end, y_end = self.find_h_edge_coords(x, y)
        self.draw_h_edge(edge, x_start, y_start, x_end, y_end)

    # Draw nodes
    for y in range(self.puzzle.height + 1):
      for x in range(self.puzzle.width + 1):
        # Mark hexagons as in error or not
        node = self.puzzle.nodes[y][x]
        if node.is_hexagon():
          node.hexagon.has_error = False
          if self.puzzle.solution_found and (x, y) in self.puzzle.removed_nodes:
            node.hexagon.has_error = True      
        x_start, y_start, x_end, y_end = self.find_node_coords(x, y)
        self.draw_node(node, x_start, y_start, x_end, y_end)

    # Draw cells
    for y in range(self.puzzle.height):
      for x in range(self.puzzle.width):
        # Find middle of the cell
        x_centre = self.margin + (x * self.cell_size) + (self.cell_size / 2)
        y_centre = self.margin + (y * self.cell_size) + (self.cell_size / 2)
        # TODO: remove this - for debugging only
        if 0:
          # If this cell is part of an area, colour it in so we can see which areas have been defined
          bg_colour = Colour.BACKGROUND
          bg_colour_map = {0: Colour.BACKGROUND,
                           1: (245,255,212),
                           2: (212,255,232),
                           3: (218,250,255),
                           4: (232,239,255),
                           5: (250,223,255)}
          for n, area in enumerate(self.puzzle.areas):
            if (x, y) in area:
              if n in bg_colour_map:
                bg_colour = bg_colour_map[n]
              else:
                bg_colour = Colour.BACKGROUND
        bg_colour = Colour.BACKGROUND

        if self.puzzle.solution_found and (x, y) in self.puzzle.removed_pieces:
          bg_colour = Colour.ERROR

        self.draw_cell(self.puzzle.cells[y][x], x_centre, y_centre, bg_colour)

    # Draw path
    if self.puzzle.solution_found:
      colour = Colour.PATH
    else:
      # An intermediate path, draw dimmer and slighlty transparent
      colour = shade_rgb(Colour.LINE, 0.5)

    self.draw_path(self.puzzle.path, colour)
    self.draw_path(self.puzzle.symmetry_path(self.puzzle.path), colour)

    # Draw status bar
    status_top = self.screen.get_height() - 100
    pygame.draw.rect(self.screen, Colour.DARK_GREY, (0, status_top, self.screen.get_width(), 100))
    font = pygame.font.SysFont("Arial", 20, bold=True)
    text_surf = font.render("%s" % self.puzzle.message, True, (0,0,0))
    self.screen.blit(text_surf, (20, status_top + 5))
    text_surf = font.render("Time taken: %0.2fs" % (self.puzzle.time_taken), True, (0,0,0))
    self.screen.blit(text_surf, (20, status_top + 30))
    text_surf = font.render("Paths attempted: {:,}".format(self.puzzle.path_attempts), True, (0,0,0))
    self.screen.blit(text_surf, (20, status_top + 55))

    pygame.display.flip()

    # helpful little debug circle
    #pygame.draw.circle(self.screen, Colour.BLUE, (100, 100), 2)

  def draw_hexagon(self, x, y, colour):
    """Draw a hexagon, centered around (x, y)."""

    # Takes up 70% of a line, i.e. radius is 35%
    r = self.line_width * 0.35
    points = []
    # (0, 360, 60) would make the point be at the top, we want it flat on top
    for ang in range(-30, 330, 60):
      x_offset = r * math.sin(math.radians(ang))
      y_offset = r * math.cos(math.radians(ang))
      points.append((x + x_offset, y + y_offset))

    pygame.gfxdraw.aapolygon(self.screen, points, colour)
    pygame.gfxdraw.filled_polygon(self.screen, points, colour)

  def draw_triangle(self, x, y, number):
    """Draw one, two or three triangles, centered around (x, y)."""

    # Takes up 70% of a line, i.e. radius is 35%
    r = self.line_width * 0.35
    x = x - (self.line_width / 2) * (number - 1)

    for _ in range(number):
      points = []
      for ang in range(-60, 300, 120):
        x_offset = r * math.sin(math.radians(ang))
        y_offset = r * math.cos(math.radians(ang))
        points.append((x + x_offset, y + y_offset))

      pygame.gfxdraw.aapolygon(self.screen, points, Colour.ORANGE)
      pygame.gfxdraw.filled_polygon(self.screen, points, Colour.ORANGE)

      x += self.line_width

  def draw_tetris(self, x, y, tetris, blue=False):
    """
    Draw a tetris shape (yellow or blue) onto a new surface, then placing the
    surface onto the screen, centered at (x, y), with appropriate rotation.
    """

    surface = pygame.Surface((self.cell_size, self.cell_size), pygame.SRCALPHA)
    margin = self.line_width
    # Remaining space for tetris squares, into which we have to fit 5 squares
    # and 4 gaps
    piece_size = (self.cell_size - (margin * 2.0)) / 6.0
    gap = piece_size / 4.0

    # Draw the first shape in the list (the given, non-rotated one)
    shape = tetris.shapes[0]

    # TODO: center tetris pieces better
    # Calculate offsets required to center the shape
    avg = lambda vals: sum(vals, 0.0) / len(vals)
    tx_offset = avg(set([tx for tx, ty in shape]))
    ty_offset = avg(set([ty for tx, ty in shape]))

    for tx, ty in shape:
      tx = (self.cell_size / 2.0) - (piece_size / 2.0) + \
           ((tx - tx_offset) * (piece_size + gap))
      ty = (self.cell_size / 2.0) - (piece_size / 2.0) + \
           ((ty - ty_offset) * (piece_size + gap))
      if blue:
        thickness = self.line_width / 8
        # Draw several 1-width rectangles inside each other to get
        # rectangles with thickness (overcomes several problems with draw.rect thickness)
        for t in range(0, thickness):
          pygame.draw.rect(surface, Colour.BLUE, (tx+t, ty+t, piece_size-2*t, piece_size-2*t), 1)
      else:
        pygame.draw.rect(surface, Colour.YELLOW, (tx, ty, piece_size, piece_size))

    # Put the surface on the screen
    top = y - (self.cell_size / 2)
    left = x - (self.cell_size / 2)
    if tetris.rotated:
      # Attempt to rotate a little more smoothly by scaling up first
      surface = pygame.transform.smoothscale(surface, (surface.get_width() * 2, surface.get_height() * 2))
      surface = pygame.transform.rotate(surface, 15)
      surface = pygame.transform.smoothscale(surface, (surface.get_width() / 2, surface.get_height() / 2))

      x_offset = (surface.get_width() / 2) - (self.cell_size / 2)
      y_offset = (surface.get_height() / 2) - (self.cell_size / 2)

      self.screen.blit(surface, (left - x_offset, top - y_offset))
    else:
      self.screen.blit(surface, (left, top))


  def draw_y(self, x, y):
    """
    Draw an elimination mark (an upside-down Y shape), as three overlapping
    rectangles.
    """
    width = self.line_width / 2.0
    length = width * 2

    # For each rectangle
    r = width / 2.0
    for ang in (60, 180, 300):
      # Find centre point
      x_offset = r * math.sin(math.radians(ang))
      y_offset = r * math.cos(math.radians(ang))

      x_centre = x + x_offset
      y_centre = y + y_offset

      # Use the centre point to find the top-left of the rectangle to draw
      left = x_centre - (length / 2.0)
      top = y_centre - (width / 2.0)

      # Draw rectangle, appropriately rotated around the centre point
      aafilled_rounded_rect(self.screen, (left, top, length, width), Colour.WHITE, radius=0, angle=ang-90)

  def draw_v_edge(self, edge, x_start, y_start, x_end, y_end):
    """Draw a vertical edge, which may have a gap or contain a hexagon."""
    if not edge.is_missing():
      pygame.draw.line(self.screen, edge.colour, (x_start, y_start), (x_end, y_end), self.line_width)
    elif edge.type == EdgeType.MISSING:
      x_gap = self.cell_size / 2 - self.gap_size / 2
      pygame.draw.line(self.screen, edge.colour, (x_start, y_start), (x_start + x_gap, y_end), self.line_width)
      pygame.draw.line(self.screen, edge.colour, (x_end, y_start), (x_end - x_gap, y_end), self.line_width)

    if edge.is_hexagon():
      if edge.hexagon.has_error:
        colour = Colour.ERROR
      else:
        colour = edge.hexagon.colour
      self.draw_hexagon(x_start + self.cell_size / 2, y_start, colour)

  def draw_h_edge(self, edge, x_start, y_start, x_end, y_end):
    """Draw a horizontal edge, which may have a gap or contain a hexagon."""
    if not edge.is_missing():
      pygame.draw.line(self.screen, edge.colour, (x_start, y_start), (x_end, y_end), self.line_width)
    elif edge.type == EdgeType.MISSING:
      y_gap = self.cell_size / 2 - self.gap_size / 2
      pygame.draw.line(self.screen, edge.colour, (x_start, y_start), (x_end, y_start + y_gap), self.line_width)
      pygame.draw.line(self.screen, edge.colour, (x_start, y_end), (x_end, y_end - y_gap), self.line_width)

    if edge.is_hexagon():
      if edge.hexagon.has_error:
        colour = Colour.ERROR
      else:
        colour = edge.hexagon.colour    
      self.draw_hexagon(x_start, y_start + self.cell_size / 2, colour)

  def draw_node(self, node, x_start, y_start, x_end, y_end):
    """
    Draw a node, which may be a start or end node and/or contain a hexagon.
    """
    if not (node.is_start() or node.is_end()):
      # Normal nodes are just circles
      left = x_start - (self.node_radius)
      top = y_start - (self.node_radius)
      diameter = self.node_radius * 2
      aafilled_rounded_rect(self.screen, (left, top, diameter, diameter), node.colour, radius=1)

    elif node.is_start():
      # A start node is a larger circle
      left = x_start - (self.node_radius * 2)
      top = y_start - (self.node_radius * 2)
      diameter = self.node_radius * 4
      aafilled_rounded_rect(self.screen, (left, top, diameter, diameter), node.colour, radius=1)

    elif node.is_end():
      # An end node is a line with a round-end which extends outwards from the edge
      width = self.line_width
      length = width * 2
      # Find the centre of the object in order to rotate about that point
      x_centre = x_start + ((x_end - x_start) / 2.0)
      y_centre = y_start + ((y_end - y_start) / 2.0)
      # Use the centre points to find the top-left of the rectangle to draw
      left = x_centre - (length / 2.0)
      top = y_centre - (width / 2.0)

      # The rectangle is drawn along the x-axis and needs to be rotated about
      # its centre point depending on which sort of end node this is
      if x_start == x_end:
        # Top and bottom end points need to be rotated 90 degrees
        angle = 90
      elif y_start == y_end:
        # Left and right end points are already orientated correctly
        # Nasty hack to make end point line up
        top += 1
        angle = 0
      elif ((x_start - x_end) * (y_start - y_end)) > 1:
        # Top-left and bottom-right end points need to angle upwards
        angle = 135
      else:
        # Top-right and bottom-left end points need to angle downwards
        angle = 45

      aafilled_rounded_rect(self.screen, (left, top, length, width), node.colour, radius=1, angle=angle)

    if node.is_hexagon():
      if node.hexagon.has_error:
        colour = Colour.ERROR
      else:
        colour = node.hexagon.colour    
      self.draw_hexagon(x_start, y_start, colour)

  def draw_cell(self, cell, x, y, bg_colour=Colour.BACKGROUND):
    """Draw a cell, which contains a particular shape."""
    # Each square is 2 line_widths in size
    scale = 3
    x_start = x - (self.line_width * (scale / 2.0))
    y_start = y - (self.line_width * (scale / 2.0))
    width = height = self.line_width * scale
    aafilled_rounded_rect(self.screen, (x_start, y_start, width, height), bg_colour, radius=0)

    # x, y is the centre of the cell
    if cell.is_square():
      # Each square is 2 line_widths in size
      scale = 2
      x_start = x - (self.line_width * (scale / 2.0))
      y_start = y - (self.line_width * (scale / 2.0))
      width = height = self.line_width * scale
      aafilled_rounded_rect(self.screen, (x_start, y_start, width, height), cell.square.colour, radius=0.75)

    elif cell.is_triangle():
      self.draw_triangle(x, y, cell.triangle.number)

    elif cell.is_star():
      # Each star is 1.5 line_widths in size
      scale = 1.5
      x_start = x - (self.line_width * (scale / 2.0))
      y_start = y - (self.line_width * (scale / 2.0))
      width = height = self.line_width * scale
      # Draw a square with a rotated square on top of it
      aafilled_rounded_rect(self.screen, (x_start, y_start, width, height), cell.star.colour, radius=0)
      aafilled_rounded_rect(self.screen, (x_start, y_start, width, height), cell.star.colour, radius=0, angle=45)

    elif cell.is_tetris():
      self.draw_tetris(x, y, cell.tetris, blue=cell.tetris.negative)

    elif cell.is_y():
      self.draw_y(x, y)
