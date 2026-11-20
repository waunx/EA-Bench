"""AW03 gift-weight, entitlement and whole-order selection with lazy facts."""
import csv
import json
import re
from .english_packet import inputs
from .author_english_aw03 import FACT_IDS


class NeedFact(Exception):
    pass


def load(variant):
    data = {}
    for path in inputs('AW03', variant).iterdir():
        if path.suffix == '.csv':
            with path.open(newline='') as stream:
                data[path.name] = list(csv.DictReader(stream))
        elif path.suffix == '.json':
            data[path.name] = json.loads(path.read_text())
        else:
            data[path.name] = path.read_text()
    return data


def observe(data):
    text = data.get('case_decision.md', '')
    match = re.search(r'allowance for FL1 is (\d+) grams', text)
    if text and match is None:
        raise ValueError('Unrecognized entitlement confirmation')
    products = {r['sku']: r for r in data['backpacks.csv']}
    wrap, stock = products['BP103']['gift_g'], products['BP104']['stock']
    return dict(allowance=int(match[1]) if match else None,
                border_wrap=int(wrap) if wrap else None, low_stock=int(stock) if stock else None)


def resolve(data, key, answers):
    raw = observe(data)[key]
    if raw is not None:
        return raw
    records = [r for r in data.get('source_records.json', []) if r['fact'] == FACT_IDS[key]]
    if records:
        revision = max(r['revision'] for r in records)
        values = {r['value'] for r in records if r['revision'] == revision}
        if len(values) == 1:
            return next(iter(values))
    if key not in answers:
        raise NeedFact(key)
    return answers[key]


def products(data):
    return data['backpacks.csv'] + data.get('warehouse_backpacks.csv', [])


def wrapping(data, row, answers):
    weight = resolve(data, 'border_wrap', answers) if row['sku'] == 'BP103' else int(row['gift_g'])
    extract = data.get('packing_extract.json')
    if (extract and extract['role'] == 'gift_wrap_per_unit' and
            extract['sku'] == row['sku'] and extract['grams'] != weight):
        raise NeedFact('Gift packaging discrepancy')
    return weight


def fits(data, weight, answers):
    flight = next(r for r in data['itinerary.csv'] if r['leg'] == 'FL1')
    try:
        allowance = resolve(data, 'allowance', answers)
    except NeedFact:
        # The confirmed base entitlement suffices if even the smallest current
        # equal-authority rendition accommodates this product. No upgrade is assumed.
        lower = int(flight['base_allowance_g'])
        records = [r for r in data.get('source_records.json', []) if r['fact'] == FACT_IDS['allowance']]
        if records:
            revision = max(r['revision'] for r in records)
            lower = min(r['value'] for r in records if r['revision'] == revision)
        if weight <= lower:
            return True
        raise
    receipt = data.get('baggage_receipt.json')
    if receipt and receipt['leg'] == 'FL1' and receipt['direction'] == 'outbound' and receipt['allowance_g'] != allowance:
        raise NeedFact('Outbound entitlement discrepancy')
    return weight <= allowance


def solve(data, answers):
    existing = int(next(r['existing_bag_g'] for r in data['itinerary.csv'] if r['leg'] == 'FL1'))
    for row in sorted(products(data), key=lambda r: (-int(r['rating']), 4 * int(r['unit_cents']))):
        total = 4 * int(row['unit_cents'])
        if row['arrival'] > '2026-10-04' or total > 30000:
            continue
        stock = resolve(data, 'low_stock', answers) if row['sku'] == 'BP104' else int(row['stock'])
        if stock < 4:
            continue
        weight = existing + 4 * (int(row['net_g']) + wrapping(data, row, answers))
        if fits(data, weight, answers):
            return dict(sku=row['sku'], quantity=4, checked_bag_g=weight, pay_cents=total)
    raise ValueError('No feasible gift-wrapped backpack order')
