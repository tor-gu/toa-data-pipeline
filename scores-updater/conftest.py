import sys
from pathlib import Path

# Make local modules importable (update.py)
sys.path.insert(0, str(Path(__file__).parent))

# Make the common layer importable (toa.*)
sys.path.insert(
    0, str(Path(__file__).parents[2] / "toa-lambda-layer-common" / "python")
)
