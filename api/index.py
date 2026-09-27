import sys
from pathlib import Path

# Add workspace root to sys.path so app imports work seamlessly in Vercel serverless functions
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from main import app
