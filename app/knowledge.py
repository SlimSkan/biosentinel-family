"""Loads the curated gene knowledge base and the demo personas.

The knowledge base (KB) is the ONLY source of medical facts the app uses.
The language model is never asked what a gene does; it is told, from here.
That is what "grounded" means in this project.
"""
import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


@lru_cache  # read the file once, then reuse it
def kb() -> dict:
    return json.loads((DATA / "panel_kb.json").read_text(encoding="utf-8"))


@lru_cache
def personas() -> dict:
    return json.loads((DATA / "personas.json").read_text(encoding="utf-8"))["personas"]


def gene(symbol: str) -> dict:
    """Return the KB entry for a gene, or raise KeyError if it is not on our panel."""
    return kb()["genes"][symbol]


def panel() -> list[str]:
    return sorted(kb()["genes"].keys())
