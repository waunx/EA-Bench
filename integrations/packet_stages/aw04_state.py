"""AW04 verifies four deliveries, subscription timing, fees and state effects."""
from copy import deepcopy
from .authored import reviewed_worlds
from .author_english_aw04 import ADDRESS_IDS
from .english_aw04 import load, solve, products, recipient_homes, fact, prime_price
from .acceptance import CheckResult
from .session import BindingError, canonical


def same(a, b):
    return canonical(a) == canonical(b)


def initial_state(data):
    if 'Prime status: inactive.' not in data['membership.md']:
        raise BindingError('Initial membership state not supported')
    return dict(source_data=deepcopy(data), prime_active=False, subscriptions=[], orders=[],
                payments=[], inventory_deltas={}, ledger=[])


class AW04Checker:
    def __init__(self, variant, answers, backend):
        self.data, self.answers = load(variant), deepcopy(answers)
        matches = [deepcopy(e) for a, e in reviewed_worlds('AW04', variant) if same(a, answers)]
        if len(matches) != 1:
            raise BindingError('Unknown AW04 world')
        matches[0]['grant_address'] = ADDRESS_IDS[matches[0]['grant_address']]
        self.target = solve(self.data, answers)
        if not same(matches[0], self.target):
            raise BindingError('AW04 differs from reviewed world')
        self.backend, self.initial = backend, backend.snapshot()
        if not same(self.initial, initial_state(self.data)):
            raise BindingError('Initial AW04 state mismatch')
        selected = next(r for r in products(self.data) if r['sku'] == self.target['sku'])
        self.expected_orders = {}
        rates = {r['zone']: r for r in self.data['quote_rules.csv']}
        for home in recipient_homes(self.data, self.target['grant_address']):
            rate = rates[home['zone']]
            shipping = 0 if self.target['prime'] else int(fact(self.data, rate['shipping_cents'], 'remote_shipping', answers))
            item, gift = int(selected['unit_cents']), int(rate['gift_cents'])
            self.expected_orders[home['person']] = dict(person=home['person'], address=home['address'],
                sku=selected['sku'], quantity=1, gift_wrap=True, item_cents=item, gift_cents=gift,
                shipping_cents=shipping, total_cents=item+gift+shipping, prime_applied=self.target['prime'])

    def final(self, report):
        state = self.backend.snapshot()
        orders, subs, payments = state.get('orders', []), state.get('subscriptions', []), state.get('payments', [])
        order_shape = isinstance(orders, list) and all(isinstance(r, dict) and isinstance(r.get('id'), str)
                      and bool(r['id']) and isinstance(r.get('person'), str) for r in orders)
        order_ok = order_shape and len(orders) == 4 and len({r['id'] for r in orders}) == 4
        order_ok = order_ok and {r['person'] for r in orders} == set(self.expected_orders)
        order_ok = order_ok and all(same(r, dict(self.expected_orders[r['person']], id=r['id'])) for r in orders)
        sub_ok = same(state.get('prime_active'), self.target['prime'])
        if self.target['prime']:
            sub_ok = sub_ok and len(subs) == 1 and isinstance(subs[0], dict) and isinstance(subs[0].get('id'), str) and bool(subs[0]['id'])
            sub_ok = sub_ok and same(subs[0], dict(id=subs[0]['id'], interval='monthly', amount_cents=prime_price(self.data, self.answers)))
        else:
            sub_ok = sub_ok and same(subs, [])
        expected_payments = []
        if order_shape:
            expected_payments += [dict(kind='order', ref=r['id'], amount_cents=r.get('total_cents')) for r in orders]
        if isinstance(subs, list) and all(isinstance(r, dict) and isinstance(r.get('id'), str) for r in subs):
            expected_payments += [dict(kind='subscription', ref=r['id'], amount_cents=r.get('amount_cents')) for r in subs]
        payment_ok = isinstance(payments, list) and sorted(map(canonical, payments)) == sorted(map(canonical, expected_payments))
        valid_amounts = isinstance(payments, list) and all(isinstance(r, dict) and type(r.get('amount_cents')) is int and r['amount_cents'] >= 0 for r in payments)
        total = sum(r['amount_cents'] for r in payments) if valid_amounts else None
        timing = self.timing(state, orders, subs)
        checks = dict(four_correct_gift_deliveries=bool(order_ok), membership_decision_and_price=bool(sub_ok),
                      payments_match_transactions=bool(payment_ok), total_cost_matches_required_purchase=total == self.target['total_cents'],
                      subscription_before_orders_when_required=timing,
                      inventory_effect=same(state.get('inventory_deltas'), {self.target['sku']: -4}),
                      source_records_preserved=same(state.get('source_data'), self.initial['source_data']),
                      state_fields_preserved=set(state) == set(self.initial),
                      report=isinstance(report, dict) and set(report) == {'summary'} and isinstance(report['summary'], str) and bool(report['summary'].strip()))
        return CheckResult.evaluated('authored_state', checks, backend='authored_fixture', actual_total_cents=total)

    def timing(self, state, orders, subs):
        if not isinstance(orders, list) or not isinstance(subs, list):
            return False
        if not all(isinstance(r, dict) and isinstance(r.get('id'), str) for r in orders + subs):
            return False
        ledger = state.get('ledger')
        expected = [dict(kind='order', id=r['id']) for r in orders] + [dict(kind='subscription', id=r['id']) for r in subs]
        if not isinstance(ledger, list) or sorted(map(canonical, ledger)) != sorted(map(canonical, expected)):
            return False
        if self.target['prime']:
            if len(subs) != 1 or not orders:
                return False
            start = ledger.index(dict(kind='subscription', id=subs[0]['id']))
            return all(start < ledger.index(dict(kind='order', id=r['id'])) for r in orders)
        return not subs
