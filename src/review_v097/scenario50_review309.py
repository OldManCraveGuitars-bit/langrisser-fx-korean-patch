"""Reviewed defaults for scenario50, related honorifics, and Master terminology."""
import json,sys
from pathlib import Path
from dataclasses import replace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'analysis/full-dialogue-review-307'))
import compile_review as cr
def selected_texts():
    source=json.loads((ROOT/'dialogue_editor/scenario50_ending_review309.json').read_bytes())['records']
    return {f'scenario{int(k.split("/")[0]):02d}/dialogue/{k.split("/")[1]}':cr.fit(v) for k,v in source.items()}
def apply_to_editor(records):
    texts=selected_texts()
    # Default speech only, never modify or resave the user's edits.
    return [replace(r,base_text=texts.get(r.id,r.base_text).replace('사부님','스승님')) for r in records]
