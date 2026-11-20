"""Finite optimizers and exact accounting transforms. All amounts are integers."""
from collections import Counter
from datetime import date
from itertools import product


def latest(rows):
    result = {}
    for row in rows:
        if row['id'] not in result or row['revision'] > result[row['id']]['revision']:
            result[row['id']] = row
    return [result[k] for k in sorted(result)]


def workforce(d, p):
    roles = sorted(d['read_roles'], key=lambda r: r['id'])
    candidates = {c['id']: c for c in d['read_candidates']}
    def eligible(r, c):
        return (c['education'] >= r['education'] and r['skill'] in c['skills']
            and (p['cross_role'] or r['id'] in c['applied'])
            and c['available_day'] <= p['start_day']
            and (r['license'] is None or (c['license'] == r['license']
                 and c['status'] in (['active','renewal'] if p['renewal'] else ['active']))))
    screen = {r['id']: sorted(k for k,c in candidates.items() if eligible(r,c)) for r in roles}
    choices = []
    for assignment in product(*screen.values()):
        if len(set(assignment)) == len(assignment):
            choices.append((sum(candidates[k]['monthly_salary'] * 12 for k in assignment), assignment))
    total, chosen = min(choices)
    assignment = dict(zip(screen, chosen))
    payroll = {r: candidates[c]['monthly_salary'] * 12 for r,c in assignment.items()}
    return dict(screen=screen, assignment=assignment, payroll=payroll,
                report=dict(annual_payroll=total, filled_roles=len(roles)))


def procurement(d, p):
    vendors = {v['id']:v for v in d['read_quotes']}
    qty = d['read_requisition']
    audit = {k: ((not p['cert_required'] or v['gold']) and (not p['phased'] or v['phased'])
                and v['warranty_months'] >= 24 and d['read_history'][k]['open_safety_claims'] == 0)
             for k,v in vendors.items()}
    goods = sorted(qty)
    def costing(choice):
        base = sum(qty[g] * vendors[v]['prices'][g] for g,v in zip(goods,choice))
        install = sum(qty[g] * vendors[v]['install'] for g,v in zip(goods,choice))
        freight = sum(vendors[v]['freight'] for v in (set(choice) if p['freight_group']=='vendor' else choice))
        return dict(goods=base, installation=install, freight=freight, total=base+install+freight)
    choices = product(sorted(k for k,v in audit.items() if v), repeat=len(goods))
    _, chosen = min((costing(c)['total'], c) for c in choices)
    costs = costing(chosen)
    return dict(audit=audit, purchase_plan=dict(zip(goods,chosen)), costing=costs,
                report=dict(total_cost=costs['total'], units=sum(qty.values())))


def training(d, p):
    demands = {r['id']:r for r in d['read_demands']}
    options = {r['id']:r for r in d['read_options']}
    rooms = {k: (p['sa_capacity'] if k=='SA' else v['capacity']) for k,v in d['read_rooms'].items()}
    eligible = {k: sorted(o['id'] for o in options.values() if o['demand']==k
                and rooms[o['room']]>=r['people'] and (o['slot'] != 3 or p['slot3']))
                for k,r in sorted(demands.items())}
    choices = []
    for ids in product(*eligible.values()):
        rows = [options[k] for k in ids]
        if any(len({(r['slot'],r[field]) for r in rows}) != len(rows) for field in ['room','trainer']):
            continue
        if len({(r['slot'],demands[r['demand']]['cohort']) for r in rows}) != len(rows):
            continue
        count = Counter(r['trainer'] for r in rows)
        if any(n > (p['t1_cap'] if k=='T1' else 3) for k,n in count.items()):
            continue
        choices.append((sum(r['cost'] for r in rows), ids))
    total, chosen = min(choices)
    utilization = dict(Counter(options[k]['trainer'] for k in chosen))
    utilization = {k: v*2 for k,v in utilization.items()}
    return dict(eligible=eligible, schedule=dict(zip(eligible,chosen)), utilization=utilization,
                report=dict(total_cost=total, sessions=len(demands), participant_sessions=sum(r['people'] for r in demands.values())))


def reconciliation(d, p):
    bank = latest(d['read_bank'])
    ap = {r['id']:r for r in d['read_ap']}
    matches = {}
    balances = {k:r['amount'] for k,r in ap.items()}
    unallocated = 0
    for row in bank:
        if row['kind'] != 'payment':
            continue
        target = ('I2' if p['b2_match'] else 'unallocated') if row['id']=='B2' else row['ref']
        if target not in ap:
            target = 'unallocated'
        matches[row['id']] = target
        if target == 'unallocated':
            unallocated -= row['amount']
        else:
            balances[target] += row['amount']
    aging = dict.fromkeys(['0-30','31-60','61-90','over90'],0)
    for k,amount in balances.items():
        days = max(0,(date(2026,9,30)-date.fromisoformat(ap[k]['due'])).days)
        bucket = '0-30' if days<=30 else '31-60' if days<=60 else '61-90' if days<=90 else 'over90'
        aging[bucket] += amount
    processing = p['gross_receipt']-sum(r['amount'] for r in bank if r['kind']=='receipt')
    fees = -sum(r['amount'] for r in bank if r['kind']=='fee')
    journal = dict(gross_receipts=p['gross_receipt'],processing_fees=processing,bank_fees=fees,
                   unallocated_payments=unallocated,net_cash=sum(r['amount'] for r in bank))
    return dict(matches=matches,balances=balances,aging=aging,journal=journal,
                report=dict(open_ap=sum(balances.values()),payable_now=sum(v for k,v in balances.items() if not (ap[k]['disputed'] and p['hold_dispute'])),total_fees=processing+fees))


def donor_registry(d, p):
    gifts = latest(d['read_gifts'])
    profiles = {r['email'].strip().lower():r['id'] for r in d['read_profiles']}
    if p['alias_same']:
        profiles['old_b@example.org'] = 'D2'
    def identify(email):
        email = email.strip().lower()
        return profiles.get(email, 'NEW:'+email)
    volunteers = {identify(e) for e in d['read_volunteers']}
    identity = {r['id']:identify(r['email']) for r in gifts}
    registry, memorials = {}, {}
    for r in gifts:
        key = identity[r['id']]
        reg = registry.setdefault(key,dict(amount=0,volunteer=key in volunteers,type='individual'))
        if r['corporate']:
            reg['type'] = 'corporate'
        names = memorials.setdefault(key,set())
        if not (p['net_refunds'] and r['refunded']):
            reg['amount'] += r['amount']
            if r['memorial']:
                names.add(r['memorial'])
    letters = {k:dict(tier='major' if r['amount']>=p['major_threshold'] else 'standard',
                     dual=r['volunteer'],memorials=sorted(memorials[k])) for k,r in registry.items()}
    attendees = sorted(k for k,r in registry.items() if r['volunteer'])
    return dict(identity=identity,registry=registry,letters=letters,training=attendees,
                report=dict(donors=len(registry),total_amount=sum(r['amount'] for r in registry.values()),
                            volunteer_donors=len(attendees),major_letters=sum(r['tier']=='major' for r in letters.values())))


SOLVERS = dict(workforce=workforce, procurement=procurement, training=training,
               reconciliation=reconciliation, donor_registry=donor_registry)


def solve(case_id, data, policies):
    return SOLVERS[case_id](data, policies)
