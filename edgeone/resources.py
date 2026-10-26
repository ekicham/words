"""Source checkout resources; replaced by a generated constant in deployments."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESOURCES = {
    'phonetics': json.loads((ROOT/'data/phonetics.json').read_text()),
    'textbook_phonetics': dict(line.split('\t') for line in (ROOT/'data/sources/official/1212001601265-phonetics.tsv').read_text().splitlines()),
    'course': json.loads((ROOT/'data/phonetics-course.json').read_text()),
    'books': [json.loads(p.read_text()) for p in sorted((ROOT/'data/books').glob('*.json'))],
}
