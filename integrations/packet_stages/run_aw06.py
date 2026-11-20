"""Shared JSON-action model transport and artifact I/O."""
from pathlib import Path
from ea_bench.client import ChatClient, parse_json
from ea_bench.io import write, append
ROOT = Path(__file__).resolve().parents[2]
