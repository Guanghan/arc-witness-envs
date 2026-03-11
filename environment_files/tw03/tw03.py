import sys, os
try:
    _root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
except NameError:
    _root = os.getcwd()
if _root not in sys.path:
    sys.path.insert(0, _root)
from tw03_shapefill import Tw03
