"""Case-specific camping demand and whole-pack selection."""
import csv
import json
import math
from .english_packet import inputs


class NeedFact(Exception):
    pass


def load(variant):
    data = {}
    for path in inputs('AW02', variant).iterdir():
        if path.suffix == '.csv':
            with path.open(newline='') as stream:
                data[path.name] = list(csv.DictReader(stream))
        elif path.suffix == '.json':
            data[path.name] = json.loads(path.read_text())
        else:
            data[path.name] = path.read_text()
    return data


def observe(data):
    text = data.get('case_decision.md', '').strip()
    positive = 'Sam has confirmed that he will bring two pads for the 2026-10-07 trip.'
    negative = 'Sam has not confirmed that he will bring two pads for the 2026-10-07 trip.'
    if text not in {'', positive, negative}:
        raise ValueError('Unrecognized final commitment record')
    lamps = next(r['needed'] for r in data['checklist.csv'] if r['item'] == 'lamp')
    pack = next(r['pack'] for r in data['offers.csv'] if r['offer'] == 'P1')
    return dict(sam=(text == positive) if text else None,
                lamps=int(lamps) if lamps else None, pad_pack=int(pack) if pack else None)


def resolve(data, key, answers):
    raw = observe(data)[key]
    if raw is not None:
        return raw
    records = [r for r in data.get('source_records.json', []) if r['fact'] == key]
    if records:
        revision = max(r['revision'] for r in records)
        values = {r['value'] for r in records if r['revision'] == revision}
        if len(values) == 1:
            return next(iter(values))
    if key not in answers:
        raise NeedFact(key)
    return answers[key]


def offers(data):
    return data['offers.csv'] + data.get('offer_allocations.csv', [])


def outcome(data, facts):
    if type(facts['sam']) is not bool:
        raise ValueError('Commitment must be a boolean')
    if any(type(facts[k]) is not int or facts[k] <= 0 for k in ['lamps', 'pad_pack']):
        raise ValueError('Requirement and pack size must be positive integers')
    pledges = data['pledges.csv'] + data.get('pledge_amendments.csv', [])
    pledges += [r for r in data.get('camp_pledge_archive.csv', []) if r['trip_departure'] == '2026-10-07']
    latest = {}
    for row in pledges:
        if row['pledge'] not in latest or int(row['revision']) > int(latest[row['pledge']]['revision']):
            latest[row['pledge']] = row
    need = {r['item']: facts['lamps'] if r['item'] == 'lamp' else int(r['needed'])
            for r in data['checklist.csv']}
    for row in latest.values():
        if row['status'] == 'confirmed' or (row['pledge'] == 'P3' and facts['sam']):
            need[row['item']] -= int(row['qty'])
    plan = []
    for item, quantity in sorted(need.items()):
        if quantity <= 0:
            continue
        candidates = []
        for row in offers(data):
            if row['item'] != item or row['arrival'] > '2026-10-06':
                continue
            pack = facts['pad_pack'] if row['offer'] == 'P1' else int(row['pack'])
            packs = math.ceil(quantity / pack)
            if packs <= int(row['stock_packs']):
                candidates.append((row, packs))
        if not candidates:
            raise ValueError('No timely offer can cover the outstanding quantity')
        row, packs = min(candidates, key=lambda pair: (
            -int(pair[0]['rating']), int(pair[0]['price_cents']) * pair[1]))
        plan.append(dict(offer=row['offer'], packs=packs, cost=packs * int(row['price_cents'])))
    total = sum(row['cost'] for row in plan)
    if total > 15000:
        raise ValueError('Combined purchase exceeds the budget')
    return dict(need=need, plan=plan, total=total)


def solve(data, answers):
    return outcome(data, {k: resolve(data, k, answers) for k in observe(data)})
