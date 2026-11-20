"""AW04 GPT-5.5 run with separately authored recipient and tariff facts."""
import argparse
import json
from pathlib import Path
from .run_aw01 import run
from .open_aw04 import OpenAW04
from .author_english_aw04 import ADDRESS_IDS


def knowledge(facts):
    answers=dict(
        grant_address="Grant's confirmed destination for this purchase is "+ADDRESS_IDS.get(facts['grant_address'],facts['grant_address'])+'.',
        b_stock='The current available stock for POP_B is '+str(facts['b_stock'])+' units.',
        remote_shipping='The ordinary delivery fee for zone R is '+str(facts['remote_shipping'])+' cents.',
        c_gift='Gift wrapping for POP_C is '+('available.' if facts['c_gift'] else 'not available.'),
        prime_price='The monthly Prime price for this account is '+str(facts['prime_price'])+' cents.',
        a_rating='The current rating for POP_A is '+str(facts['a_rating'])+' in the catalog rating units.')
    return {k:dict(value=v,answer=answers[k]) for k,v in facts.items()}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--variant',default='full')
    parser.add_argument('--world-json',type=Path)
    args=parser.parse_args()
    world=json.loads(args.world_json.read_text()) if args.world_json else None
    result=run(args.output.resolve(),args.variant,case='AW04',engine_factory=OpenAW04,
               knowledge_builder=knowledge,world_answers=world)
    if result['status']=='service_or_runtime_error':
        raise SystemExit(2)
