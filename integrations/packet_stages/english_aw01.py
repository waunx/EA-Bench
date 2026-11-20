"""AW01 file decisions, from the selected packet and supplied answers."""
import csv
import json
import re
from copy import deepcopy
from datetime import date
from .english_packet import inputs


class NeedFact(Exception):
    pass


def load(variant):
    folder = inputs('AW01', variant)
    data = {}
    for path in folder.iterdir():
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
    name = 'inventory_copies.json' if key == 'exp_stock' else key + '_records.json'
    field = 'stock' if key == 'exp_stock' else 'value'
    records = data.get(name, [])
    if records:
        revision = max(row['revision'] for row in records)
        values = {row[field] for row in records if row['revision'] == revision}
        if len(values) == 1:
            return next(iter(values))
    if key not in answers:
        raise NeedFact(key)
    return answers[key]


def budget(data, answers):
    match = re.search(r'Replacement budget cap in cents: (\d+|unconfirmed)\.', data['return_terms.md'])
    if match is None:
        raise ValueError('Replacement budget rule missing')
    return int(fact(data, None, 'budget', answers) if match[1] == 'unconfirmed' else match[1])


def offers(data):
    rows = deepcopy(data['offers.csv'] + data.get('catalog_quotes.csv', []) +
                    data.get('allocation_offers.csv', []))
    rows += [deepcopy(r) for r in data.get('quote_history.csv', [])
             if r['valid_from'] <= '2026-09-29' <= r['valid_until']]
    return rows


def solve(data, answers):
    delivered = [row for row in data['orders.csv'] if row['kind'] == 'tshirt'
                 and fact(data, row['status'], 'last_order_status', answers) == 'delivered']
    old = max(delivered, key=lambda row: row['placed'])
    if (date(2026, 9, 29) - date.fromisoformat(old['placed'])).days > 30:
        raise ValueError('Last purchased T-shirt is outside the return window')
    purchased = fact(data, old['size'], 'purchased_size', answers)
    sizes = {row['size']: int(row['rank']) for row in data['size_chart.csv'] if row['style'] == old['style']}
    next_size = next(size for size, rank in sizes.items() if rank == sizes[purchased] + 1)
    deadline = (re.search(r'\d{4}-\d{2}-\d{2}', data['case_decision.md'])[0]
                if 'case_decision.md' in data else fact(data, None, 'deadline', answers))
    cap = budget(data, answers)
    for color in dict.fromkeys(['white', old['color']]):
        candidates = [row for row in offers(data) if row['style'] == old['style']
                      and row['size'] == next_size and row['color'] == color and int(row['total_cents']) <= cap]
        for row in sorted(candidates, key=lambda item: (int(item['total_cents']), item['quote'])):
            if fact(data, row['arrival'], 'standard_arrival', answers) > deadline:
                continue
            if int(fact(data, row['stock'], 'exp_stock', answers)) > 0:
                return dict(return_order=old['order'], quote=row['quote'], pay_cents=int(row['total_cents']))
    raise ValueError('No feasible replacement')


def run(data, world):
    answers, asked = {}, []
    while True:
        try:
            return solve(data, answers), asked
        except NeedFact as error:
            key = str(error)
            if key in asked:
                raise RuntimeError('Repeated unanswered fact')
            answers[key] = world[key]
            asked.append(key)
