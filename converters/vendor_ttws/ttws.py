import argparse
from ui import UI

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="""\
TTWS - The \"The Witness\" Solver""")
  parser.add_argument("-p", "--puzzle",
                      help="A single puzzle code (puzzle state encoded from "
                           "https://windmill.thefifthmatt.com)")
  parser.add_argument("-f", "--file",
                      help="File containing a list of puzzle codes")

  args = parser.parse_args()

  puzzles = []
  if args.puzzle:
    puzzles = [args.puzzle]
  elif args.file:
    puzzles = [line.strip() for line in open(args.file).readlines()]

  # Preload the UI with none, one or many puzzle codes
  UI(puzzles)
