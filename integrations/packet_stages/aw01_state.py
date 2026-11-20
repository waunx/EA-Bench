"""AW01 local state acceptance, independent of agent claims."""
from copy import deepcopy
import re
from .acceptance import CheckResult
from .authored import reviewed_worlds
from .english_aw01 import load, solve, offers
from .session import BindingError, canonical


def same(left, right):
    return canonical(left) == canonical(right)


def initial_state(data):
    return dict(source_orders=deepcopy(data['orders.csv']), returns=[], purchases=[],
                payments=[], inventory_deltas={}, refund_credit_cents=0)


class AW01Checker:
    def __init__(self, variant, answers, backend):
        self.data = load(variant)
        matches = [e for a, e in reviewed_worlds('AW01', variant) if same(a, answers)]
        if len(matches) != 1:
            raise BindingError('Unknown or ambiguous AW01 world')
        expected = deepcopy(matches[0])
        expected['quote'] = {'Q_WRONG_SIZE': 'Q_SIZE_XL',
                             'Q_OTHER_STYLE': 'Q_STYLE_URBAN'}.get(expected['quote'], expected['quote'])
        self.target = solve(self.data, answers)
        if not same(expected, self.target):
            raise BindingError('English AW01 disagrees with reviewed world')
        self.backend = backend
        self.initial = backend.snapshot()
        if not same(self.initial, initial_state(self.data)):
            raise BindingError('Initial AW01 state differs from selected packet')

    def final(self, report):
        state, t = self.backend.snapshot(), self.target
        old = next(r for r in self.data['orders.csv'] if r['order'] == t['return_order'])
        quote = next(r for r in offers(self.data) if r['quote'] == t['quote'])
        expected_return = dict(order=t['return_order'], status='initiated', label_fee_cents=200,
                               purchase_paid_cents=int(old['paid_cents']), refund_status='pending')
        expected_purchase = dict(quote=t['quote'], quantity=1, total_cents=t['pay_cents'],
                                 style=quote['style'], size=quote['size'], color=quote['color'])
        return_ok = self.one_record(state.get('returns'), expected_return)
        purchase_ok = self.one_record(state.get('purchases'), expected_purchase)
        payment_ok = purchase_ok and same(state.get('payments'), [
            dict(order_id=state['purchases'][0]['id'], amount_cents=t['pay_cents'],
                 funding='available_funds')])
        checks = dict(
            return_initiated_with_label_and_pending_refund=bool(return_ok),
            one_correct_replacement=bool(purchase_ok),
            correct_payment_from_available_funds=bool(payment_ok),
            inventory_effect=same(state.get('inventory_deltas'), {t['quote']: -1}),
            other_orders_preserved=same(state.get('source_orders'), self.initial['source_orders']),
            no_anticipated_refund_credit=same(state.get('refund_credit_cents'), 0),
            state_fields_preserved=set(state) == set(self.initial),
            report_identifies_actions=self.report_ok(report))
        return CheckResult.evaluated('authored_state', checks, backend='authored_fixture')

    @staticmethod
    def one_record(rows, expected):
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            return False
        identity = rows[0].get('id')
        return (isinstance(identity, str) and bool(identity) and
                same(rows[0], dict(expected, id=identity)))

    def report_ok(self, report):
        if not isinstance(report, dict) or set(report) != {'summary'} or not isinstance(report['summary'], str):
            return False
        text, t = report['summary'], self.target
        amount = t['pay_cents']
        tokens = [str(amount), format(amount, ','), format(amount / 100, '.2f')]
        mentioned = any(re.search(r'(?<![\d.])' + re.escape(s) + r'(?![\d.])', text) for s in tokens)
        return t['return_order'] in text and t['quote'] in text and mentioned
