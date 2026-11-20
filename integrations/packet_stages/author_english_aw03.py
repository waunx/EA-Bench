"""AW03 English revision with neutral authored catalog identifiers."""
import hashlib
import json
import re
from .authored import SOURCE, read_json
from .english_packet import RELEASE

PACKET = RELEASE / 'AW03'
SKU_IDS = dict(LIGHT='BP101', HEAVY='BP102', BORDER='BP103', LOW_STOCK='BP104', LATE='BP105', COMPACT='BP106')
FACT_IDS = dict(allowance='outbound_allowance_g', border_wrap='bp103_gift_g', low_stock='bp104_stock')
CONSTRAINTS = (
    'Use the currently effective baggage entitlement for the outbound flight to Japan. '
    'All four backpacks and their gift wrapping must fit in the checked bag; the outer shipping carton will not travel. '
    'The order must arrive at home by October 4, 2026 and cost no more than 30,000 cents including wrapping. '
    'Among feasible identical-backpack choices, prefer the highest rating, then the lowest total price. '
    'A baggage-upgrade quotation does not establish an effective entitlement; do not purchase an upgrade for this task.'
)
RULES = (
    'All four identical backpacks must travel in the checked bag. Include gift wrapping in the checked weight; '
    'the outer shipping carton does not travel. Home delivery deadline: 2026-10-04. '
    'Combined purchase budget: 30000 cents. unit_cents includes gift wrapping. '
    'Prefer the highest-rated feasible product, then the lowest total price.\n'
)
UPGRADE = (
    'The original confirmed allowance for outbound leg FL1 is 23 kg. A quotation offers an additional 3 kg. '
    'Use the current effective entitlement confirmation; a quotation alone is not proof that the upgrade is effective.\n'
)


def build():
    if (PACKET / 'MANIFEST.json').exists():
        raise FileExistsError('English AW03 already exists')
    source = read_json(SOURCE / 'AW03/SOURCE.json')
    manifest = {}
    for variant, hashes in read_json(SOURCE / 'AW03/MANIFEST.json').items():
        manifest[variant] = {}
        for name, digest in hashes.items():
            raw = (SOURCE / 'AW03/variants' / variant / name).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == digest
            text = raw.decode()
            if name == 'prompt.md':
                text = source['original_text'] + ' ' + CONSTRAINTS + '\n'
            elif name == 'inputs/packing_rules.md':
                text = RULES
            elif name == 'inputs/baggage_upgrade.md':
                text = UPGRADE
            elif name == 'inputs/case_decision.md':
                assert re.search(r'23kg', text)
                text = 'The currently effective checked baggage allowance for FL1 is 23000 grams.\n'
            for old, new in SKU_IDS.items():
                text = re.sub(r'\b' + re.escape(old) + r'\b', new, text)
            if name == 'inputs/source_records.json':
                records = json.loads(text)
                for record in records:
                    record['fact'] = FACT_IDS[record['fact']]
                text = json.dumps(records, indent=2) + '\n'
            assert not re.search('[\u3400-\u9fff]', text), name
            content = text.encode()
            target = PACKET / 'variants' / variant / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            manifest[variant][name] = hashlib.sha256(content).hexdigest()
    source.update(presentation_revision='English narrative and neutral catalog/fact IDs',
                  authored_sku_id_mapping=SKU_IDS, authored_fact_id_mapping=FACT_IDS)
    (PACKET / 'SOURCE.json').write_text(json.dumps(source, indent=2) + '\n')
    (PACKET / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Authored AW03:', len(manifest), 'variants')


if __name__ == '__main__':
    build()
