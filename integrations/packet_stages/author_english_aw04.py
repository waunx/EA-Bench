"""AW04 English presentation with neutral recipient-address identifiers."""
import hashlib
import json
import re
from .authored import SOURCE, read_json
from .english_packet import RELEASE

PACKET = RELEASE / 'AW04'
ADDRESS_IDS = dict(G_OLD='G_ADDR1', G_NEW='G_ADDR2')
CONSTRAINTS = (
    'All four gifts must use the same in-stock model eligible for gift wrapping. '
    'Use each recipient\'s confirmed home destination for this purchase. '
    'Compare the combined ordinary delivery fees with the account\'s monthly Prime price; '
    'gift-wrapping charges are separate from delivery fees and are not waived by Prime. '
    'Use quotations valid on September 29, 2026.'
)


def membership(price):
    return (
        'Prime status: inactive. Monthly price in cents: ' + price + '. '
        'An active subscription waives delivery fees for every zone in the attached tariff; gift-wrapping fees remain payable. '
        'Each friend receives one gift. All four units must be the same in-stock gift-wrappable model. '
        'Choose the highest-rated model that can supply all four gifts. Subscribe before ordering only when '
        'the combined ordinary delivery fees strictly exceed the monthly price. '
        'Use Grant\'s destination confirmation for this purchase.\n'
    )


def build():
    if (PACKET / 'MANIFEST.json').exists():
        raise FileExistsError('English AW04 already exists')
    source = read_json(SOURCE / 'AW04/SOURCE.json')
    manifest = {}
    for variant, hashes in read_json(SOURCE / 'AW04/MANIFEST.json').items():
        manifest[variant] = {}
        for name, digest in hashes.items():
            raw = (SOURCE / 'AW04/variants' / variant / name).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == digest
            text = raw.decode()
            if name == 'prompt.md':
                text = source['original_text'] + ' ' + CONSTRAINTS + '\n'
            elif name == 'inputs/membership.md':
                text = membership('unconfirmed' if '[not loaded]' in text else '1499')
            elif name == 'inputs/case_decision.md':
                assert 'G_NEW' in text
                text = "Grant's confirmed destination for this purchase is G_ADDR2.\n"
            elif name == 'inputs/quote_clock.md':
                text = 'Purchase date: 2026-09-29. Quotations must be within their validity period. Stock denotes units available for this purchase.\n'
            for old, new in ADDRESS_IDS.items():
                text = re.sub(r'\b' + old + r'\b', new, text)
            assert not re.search('[\u3400-\u9fff]', text), name
            target = PACKET / 'variants' / variant / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(text.encode())
            manifest[variant][name] = hashlib.sha256(text.encode()).hexdigest()
    source.update(presentation_revision='English narrative and neutral address IDs', authored_address_id_mapping=ADDRESS_IDS)
    (PACKET / 'SOURCE.json').write_text(json.dumps(source, indent=2) + '\n')
    (PACKET / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Authored AW04:', len(manifest), 'variants')


if __name__ == '__main__':
    build()
