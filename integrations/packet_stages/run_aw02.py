"""AW02 runner; shared transport, separately authored knowledge and state rules."""
import argparse
import json
from pathlib import Path
from .run_aw01 import run
from .open_aw02 import OpenAW02


def knowledge(facts):
    answers = dict(
        sam='Sam has ' + ('' if facts['sam'] else 'not ') +
            'confirmed that he will bring two pads for the 2026-10-07 trip.',
        lamps='The current camping checklist requires ' + str(facts['lamps']) + ' lamps.',
        pad_pack='Offer P1 contains ' + str(facts['pad_pack']) + ' pads per sealed retail pack.')
    return {k: dict(value=v, answer=answers[k]) for k, v in facts.items()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--variant', default='full')
    parser.add_argument('--world-json', type=Path)
    args = parser.parse_args()
    world = json.loads(args.world_json.read_text()) if args.world_json else None
    result = run(args.output.resolve(), args.variant, case='AW02', engine_factory=OpenAW02,
                 knowledge_builder=knowledge, world_answers=world)
    if result['status'] == 'service_or_runtime_error':
        raise SystemExit(2)
