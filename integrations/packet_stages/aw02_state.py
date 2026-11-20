"""AW02 transaction-state checker; no self-reported execution evidence."""
from copy import deepcopy
from .authored import reviewed_worlds
from .english_aw02 import load, solve, offers, resolve
from .acceptance import CheckResult
from .session import BindingError, canonical


def same(a, b):
    return canonical(a) == canonical(b)


def initial_state(data):
    return dict(source_data=deepcopy(data), orders=[], payments=[], inventory_deltas={})


class AW02Checker:
    def __init__(self, variant, answers, backend):
        self.data, self.answers = load(variant), deepcopy(answers)
        matches = [e for a, e in reviewed_worlds('AW02', variant) if same(a, answers)]
        self.target = solve(self.data, answers)
        if len(matches) != 1 or not same(matches[0], self.target):
            raise BindingError('AW02 world disagrees with reviewed outcomes')
        self.backend, self.initial = backend, backend.snapshot()
        if not same(self.initial, initial_state(self.data)):
            raise BindingError('AW02 initial state mismatch')
        products = {r['offer']: r for r in offers(self.data)}
        self.lines = []
        for row in self.target['plan']:
            product = products[row['offer']]
            pack = resolve(self.data, 'pad_pack', answers) if row['offer'] == 'P1' else int(product['pack'])
            self.lines.append(dict(offer=row['offer'], item=product['item'], packs=row['packs'],
                units=row['packs'] * pack, cost_cents=row['cost'], arrival=product['arrival']))

    def final(self, report):
        state = self.backend.snapshot()
        orders = state.get('orders')
        order_ok = False
        if isinstance(orders, list) and len(orders) == 1 and isinstance(orders[0], dict):
            order = deepcopy(orders[0])
            identity = order.get('id')
            if isinstance(order.get('lines'), list):
                order['lines'] = sorted(order['lines'], key=lambda r: r['offer'])
            order_ok = isinstance(identity, str) and bool(identity) and same(order, dict(
                id=identity, lines=sorted(self.lines, key=lambda r: r['offer']),
                destination='home', total_cents=self.target['total']))
        payment_ok = order_ok and same(state.get('payments'), [
            dict(order_id=orders[0]['id'], amount_cents=self.target['total'])])
        expected_deltas = {r['offer']: -r['packs'] for r in self.target['plan']}
        checks = dict(one_complete_correct_order=bool(order_ok),
                      linked_correct_payment=bool(payment_ok),
                      inventory_effect=same(state.get('inventory_deltas'), expected_deltas),
                      source_records_preserved=same(state.get('source_data'), self.initial['source_data']),
                      state_fields_preserved=set(state) == set(self.initial),
                      report=isinstance(report, dict) and set(report) == {'summary'} and
                             isinstance(report['summary'], str) and bool(report['summary'].strip()))
        return CheckResult.evaluated('authored_state', checks, backend='authored_fixture')
