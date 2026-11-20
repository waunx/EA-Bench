"""AW06 English variants with host-validated, fact-only clarification."""
import argparse
import json
from pathlib import Path
from .run_aw01 import run
from .open_aw06 import OpenAW06


def engine(variant, answers):
    return OpenAW06(variant=variant, answers=answers)


def knowledge(facts):
    answers = dict(
        card='For this purchase, the designated payment card is ' + facts['card'] + '.',
        ps5_price='The final delivered price of the standard PS5 is ' + str(facts['ps5_price']) + ' cents.',
        cart_coupon='Immediately before checkout, the cart coupon was ' + facts['cart_coupon'] + '.')
    return {k: dict(value=v, answer=answers[k]) for k, v in facts.items()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--variant', default='full')
    parser.add_argument('--world-json', type=Path)
    args = parser.parse_args()
    world = json.loads(args.world_json.read_text()) if args.world_json else None
    result = run(args.output.resolve(), args.variant, case='AW06', engine_factory=engine,
                 knowledge_builder=knowledge, world_answers=world)
    if result['status'] == 'service_or_runtime_error':
        raise SystemExit(2)
