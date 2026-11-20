"""AW03 GPT-5.5 runner with case-specific factual user knowledge."""
import argparse
import json
from pathlib import Path
from .run_aw01 import run
from .open_aw03 import OpenAW03


def knowledge(facts):
    answers = dict(
        allowance='The currently effective checked baggage allowance for FL1 is ' + str(facts['allowance']) + ' grams.',
        border_wrap='Gift wrapping for BP103 weighs ' + str(facts['border_wrap']) + ' grams per backpack.',
        low_stock='The current sellable inventory for BP104 is ' + str(facts['low_stock']) + ' backpacks.')
    return {k: dict(value=v, answer=answers[k]) for k, v in facts.items()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--variant', default='full')
    parser.add_argument('--world-json', type=Path)
    args = parser.parse_args()
    world = json.loads(args.world_json.read_text()) if args.world_json else None
    result = run(args.output.resolve(), args.variant, case='AW03', engine_factory=OpenAW03,
                 knowledge_builder=knowledge, world_answers=world)
    if result['status'] == 'service_or_runtime_error':
        raise SystemExit(2)
