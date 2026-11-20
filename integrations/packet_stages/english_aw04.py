"""AW04 gift selection, recipient tariffs and strict Prime fee comparison."""
import csv
import json
import re
from .english_packet import inputs
from .author_english_aw04 import ADDRESS_IDS


class NeedFact(Exception):
    pass


def load(variant):
    data = {}
    for path in inputs('AW04', variant).iterdir():
        if path.suffix == '.csv':
            with path.open(newline='') as stream:
                data[path.name] = list(csv.DictReader(stream))
        elif path.suffix == '.json':
            data[path.name] = json.loads(path.read_text())
        else:
            data[path.name] = path.read_text()
    return data


def fact(data, raw, key, answers):
    if raw not in ('', None):
        return raw
    records = data.get(key + '_records.json', [])
    if records:
        revision = max(r['revision'] for r in records)
        values = {r['value'] for r in records if r['revision'] == revision}
        if len(values) == 1:
            return next(iter(values))
    if key not in answers:
        raise NeedFact(key)
    return answers[key]


def peek(data, raw, key, answers):
    try:
        return fact(data, raw, key, answers)
    except NeedFact:
        return None


def products(data):
    rows = data['products.csv'] + data.get('retail_quotes.csv', []) + data.get('allocation_quotes.csv', [])
    return rows + [r for r in data.get('quotation_history.csv', []) if r['valid_until'] >= '2026-09-29']


def rating_bounds(data, row, answers):
    value = peek(data, row['rating'], 'a_rating', answers)
    if value is not None:
        return int(value), int(value)
    records = data.get('a_rating_records.json', [])
    if not records:
        raise NeedFact('a_rating')
    revision = max(r['revision'] for r in records)
    values = [int(r['value']) for r in records if r['revision'] == revision]
    return min(values), max(values)


def choose(data, answers):
    candidates = []
    for row in products(data):
        stock = peek(data, row['stock'], 'b_stock', answers)
        gift = peek(data, row['gift'], 'c_gift', answers)
        if stock is not None and int(stock) < 4 or gift is not None and int(gift) != 1:
            continue
        candidates.append(row)
    candidates.sort(key=lambda r: -rating_bounds(data, r, answers)[1])
    best, best_rating = None, -1
    for index, row in enumerate(candidates):
        lower, upper = rating_bounds(data, row, answers)
        if upper <= best_rating:
            continue
        if int(fact(data, row['stock'], 'b_stock', answers)) < 4:
            continue
        if int(fact(data, row['gift'], 'c_gift', answers)) != 1:
            continue
        rest = max([rating_bounds(data, r, answers)[1] for r in candidates[index + 1:]] or [-1])
        if lower > best_rating and lower >= rest:
            return row
        rating = int(fact(data, row['rating'], 'a_rating', answers))
        if rating > best_rating:
            best, best_rating = row, rating
    if best is None:
        raise ValueError('No gift-wrappable model can supply all four gifts')
    return best


def prime_price(data, answers):
    match = re.search(r'Monthly price in cents: (\d+|unconfirmed)\.', data['membership.md'])
    if match is None:
        raise ValueError('Membership price term missing')
    return int(fact(data, None, 'prime_price', answers)) if match[1] == 'unconfirmed' else int(match[1])


def grant_address(data, answers):
    if 'case_decision.md' in data:
        match = re.search(r'destination for this purchase is (G_ADDR[12])\.', data['case_decision.md'])
        if match is None:
            raise ValueError('Unrecognized recipient confirmation')
        return match[1]
    value = fact(data, None, 'grant_address', answers)
    return ADDRESS_IDS.get(value, value)


def recipient_homes(data, address):
    return [r for r in data['addresses.csv'] if r['person'] != 'Grant' or r['address'] == address]


def solve(data, answers):
    chosen = choose(data, answers)
    address = grant_address(data, answers)
    homes = recipient_homes(data, address)
    if len(homes) != 4 or {r['person'] for r in homes} != {'Grant', 'Jose', 'Brenda', 'Nicholas'}:
        raise ValueError('Recipient destinations are incomplete')
    rates = {r['zone']: r for r in data['quote_rules.csv']}
    shipping = sum(int(fact(data, rates[h['zone']]['shipping_cents'], 'remote_shipping', answers)) for h in homes)
    gifts = sum(int(rates[h['zone']]['gift_cents']) for h in homes)
    price = prime_price(data, answers)
    prime = shipping > price
    return dict(grant_address=address, sku=chosen['sku'], shipping=shipping, prime=prime,
                total_cents=4 * int(chosen['unit_cents']) + gifts + (price if prime else shipping))
