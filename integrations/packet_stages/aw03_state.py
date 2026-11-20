"""AW03 order, payment, inventory and gift-mass acceptance."""
from copy import deepcopy
from .authored import reviewed_worlds
from .author_english_aw03 import SKU_IDS
from .english_aw03 import load, solve, resolve, products, wrapping
from .acceptance import CheckResult
from .session import BindingError, canonical


def same(a, b):
    return canonical(a) == canonical(b)


def initial_state(data):
    return dict(source_data=deepcopy(data), orders=[], payments=[], inventory_deltas={})


class AW03Checker:
    def __init__(self, variant, answers, backend):
        self.data, self.answers = load(variant), deepcopy(answers)
        matches = [deepcopy(e) for a, e in reviewed_worlds('AW03', variant) if same(a, answers)]
        self.target = solve(self.data, answers)
        if len(matches) != 1:
            raise BindingError('Unknown AW03 world')
        matches[0]['sku'] = SKU_IDS[matches[0]['sku']]
        if not same(matches[0], self.target):
            raise BindingError('AW03 decision differs from reviewed world')
        self.backend, self.initial = backend, backend.snapshot()
        if not same(self.initial, initial_state(self.data)):
            raise BindingError('AW03 initial state mismatch')
        row = next(r for r in products(self.data) if r['sku'] == self.target['sku'])
        self.order = dict(sku=row['sku'], quantity=4, gift_wrap=True, destination='home',
                          unit_net_g=int(row['net_g']), unit_gift_g=wrapping(self.data, row, answers),
                          arrival=row['arrival'], total_cents=self.target['pay_cents'])

    def final(self, report):
        state = self.backend.snapshot()
        orders = state.get('orders')
        order_ok = False
        if isinstance(orders, list) and len(orders) == 1 and isinstance(orders[0], dict):
            identity = orders[0].get('id')
            order_ok = isinstance(identity, str) and bool(identity) and same(orders[0], dict(self.order, id=identity))
        payment_ok = order_ok and same(state.get('payments'), [dict(order_id=orders[0]['id'], amount_cents=self.target['pay_cents'])])
        existing = int(next(r['existing_bag_g'] for r in self.data['itinerary.csv'] if r['leg'] == 'FL1'))
        valid_mass = isinstance(orders, list) and all(
            isinstance(r, dict) and type(r.get('quantity')) is int and r['quantity'] > 0 and
            all(type(r.get(k)) is int and r[k] >= 0 for k in ['unit_net_g', 'unit_gift_g'])
            for r in orders)
        actual_mass = (existing + sum(r['quantity'] * (r['unit_net_g'] + r['unit_gift_g'])
                                     for r in orders)) if valid_mass else None
        weight_ok = valid_mass and actual_mass <= resolve(self.data, 'allowance', self.answers)
        checks = dict(one_correct_gift_order=bool(order_ok), linked_payment=bool(payment_ok),
                      checked_weight_within_entitlement=bool(weight_ok),
                      inventory_effect=same(state.get('inventory_deltas'), {self.target['sku']: -4}),
                      source_records_preserved=same(state.get('source_data'), self.initial['source_data']),
                      state_fields_preserved=set(state) == set(self.initial),
                      report=isinstance(report, dict) and set(report) == {'summary'} and isinstance(report['summary'], str) and bool(report['summary'].strip()))
        return CheckResult.evaluated('authored_state', checks, backend='authored_fixture',
                                     actual_checked_bag_g=actual_mass)
