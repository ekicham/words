"""EdgeOne framework catch-all: /api/*, with /api stripped before Flask routing."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from flask import Flask
from wordisle_edge.server import configure_app

app = Flask(__name__)
configure_app(app)
