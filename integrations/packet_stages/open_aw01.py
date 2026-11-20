"""Ordinary AW01 business tools; hidden worlds never drive public API replies."""
from copy import deepcopy
from datetime import date
from pathlib import PurePosixPath
from .english_aw01 import load, offers, fact, NeedFact
from .english_packet import inputs
from .aw01_state import AW01Checker, initial_state, same
from .open_aw06 import SYSTEM, OUTPUT_FORMAT

API_FORMATS = {
    'list_orders': {},
    'list_offers': {},
    'list_returns': {},
    'list_purchases': {},
    'initiate_return': {'order': 'order ID'},
    'buy_quote': {'quote': 'quote ID', 'quantity': 'positive integer',
                  'funding': 'available_funds or refund_credit'},
}
FACT_LABELS = {
    'last_order_status': 'Order fulfillment status',
    'exp_stock': 'Quote inventory',
    'purchased_size': 'Purchased garment size',
    'standard_arrival': 'Delivery commitment',
    'deadline': 'Requested delivery deadline',
    'budget': 'Replacement budget',
}


class OpenAW01:
    validation_layer = 'authored_fixture'

    def __init__(self, variant='full', answers=None, ask_handler=None):
        self.folder = inputs('AW01', variant)
        self.data = load(variant)
        self.state = initial_state(self.data)
        self.answers = deepcopy(answers or {})
        self.confirmed = {}
        self.checker = AW01Checker(variant, self.answers, self)
        self.files = {p.name: p for p in self.folder.iterdir() if p.is_file()}
        self.events, self.calls, self.effects = [], [], {}
        self.done, self.result = False, None
        self.ask_handler = ask_handler
        self.variant = variant

    def snapshot(self):
        return deepcopy(self.state)

    def observation(self):
        return dict(task_description=(self.folder.parent / 'prompt.md').read_text(),
                    output_format=deepcopy(OUTPUT_FORMAT))

    def confirm(self, values):
        if any(k not in self.answers or not same(v, self.answers[k]) for k, v in values.items()):
            raise ValueError('Host answer does not match the selected world')
        self.confirmed.update(deepcopy(values))

    def step(self, action):
        if self.done:
            return {'error': 'session_finalized'}
        before = self.snapshot()
        terminal = isinstance(action, dict) and action.get('tool') == 'submit'
        try:
            reply = self.dispatch(action)
        except NeedFact as error:
            reply = {'error': FACT_LABELS[str(error)] + ' requires confirmation.'}
        except (KeyError, ValueError, TypeError) as error:
            reply = {'error': str(error)}
            if terminal:
                self.result = dict(success=False, status='invalid_submission')
        if terminal:
            self.done = True
            reply = {'submission_received': True, 'terminal': True}
        self.events.append(dict(action=deepcopy(action), reply=deepcopy(reply),
                                before=before, after=self.snapshot()))
        return reply

    def dispatch(self, action):
        if not isinstance(action, dict):
            raise ValueError('Expected one JSON object')
        tool = action.get('tool')
        if tool in {'list_files', 'list_tools'}:
            if set(action) != {'tool'}:
                raise ValueError('Unexpected argument')
            return {'files': sorted(self.files)} if tool == 'list_files' else {'apis': deepcopy(API_FORMATS)}
        if tool == 'read_file':
            name = action.get('path')
            if set(action) != {'tool', 'path'} or not isinstance(name, str):
                raise ValueError('Expected path string')
            if name not in self.files or PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts:
                raise ValueError('Unknown input file')
            return {'path': name, 'content': self.files[name].read_text()}
        if tool == 'call':
            if set(action) != {'tool', 'name', 'arguments'} or not isinstance(action['arguments'], dict):
                raise ValueError('Expected API name and arguments object')
            return self.call(action['name'], action['arguments'])
        return self.finish_or_ask(action)

    def finish_or_ask(self, action):
        if action.get('tool') == 'ask_user':
            if set(action) != {'tool', 'question'} or not isinstance(action['question'], str):
                raise ValueError('Expected question string')
            if self.ask_handler is None:
                raise RuntimeError('Clarification user is not configured')
            return self.ask_handler(action['question'])
        if action.get('tool') == 'submit':
            if set(action) != {'tool', 'result'}:
                raise ValueError('Expected result object')
            try:
                verdict = self.checker.final(action['result'])
            except Exception as error:
                raise RuntimeError('State evaluator failed') from error
            self.result = dict(status='submitted', success=verdict.status == 'passed',
                               acceptance=verdict.to_dict())
            return {'submission_received': True}
        raise ValueError('Unknown tool')

    def call(self, name, arguments):
        if name not in API_FORMATS:
            raise ValueError('Unknown API')
        if name.startswith('list_'):
            if arguments:
                raise ValueError('This API takes no arguments')
            if name == 'list_orders':
                return {'orders': deepcopy(self.state['source_orders'])}
            if name == 'list_offers':
                rows = offers(self.data)
                for row in rows:
                    if row['stock'] != '':
                        row['stock'] = str(int(row['stock']) + self.state['inventory_deltas'].get(row['quote'], 0))
                return {'offers': rows}
            return {name[5:]: deepcopy(self.state[name[5:]])}
        if name == 'initiate_return':
            return self.initiate_return(arguments)
        return self.buy_quote(arguments)

    def initiate_return(self, arguments):
        if set(arguments) != {'order'} or not isinstance(arguments['order'], str):
            raise ValueError('Expected order ID string')
        rows = [r for r in self.data['orders.csv'] if r['order'] == arguments['order']]
        if len(rows) != 1:
            raise ValueError('Unknown order')
        order = rows[0]
        status = fact(self.data, order['status'], 'last_order_status', self.confirmed)
        age = (date(2026, 9, 29) - date.fromisoformat(order['placed'])).days
        if status != 'delivered' or not 0 <= age <= 30:
            raise ValueError('Order is not eligible for return')
        if any(r['order'] == order['order'] for r in self.state['returns']):
            raise ValueError('Return already initiated')
        record = dict(id='return-' + str(len(self.state['returns']) + 1),
                      order=order['order'], status='initiated', label_fee_cents=200,
                      purchase_paid_cents=int(order['paid_cents']), refund_status='pending')
        self.state['returns'].append(record)
        self.calls.append('initiate_return')
        return deepcopy(record)

    def buy_quote(self, arguments):
        if set(arguments) != {'quote', 'quantity', 'funding'}:
            raise ValueError('Expected quote, quantity and funding')
        if not isinstance(arguments['quote'], str) or type(arguments['quantity']) is not int or arguments['quantity'] < 1:
            raise ValueError('Invalid quote or quantity')
        if arguments['funding'] not in {'available_funds', 'refund_credit'}:
            raise ValueError('Unknown funding source')
        if arguments['funding'] == 'refund_credit':
            raise ValueError('No settled refund credit is available')
        rows = [r for r in offers(self.data) if r['quote'] == arguments['quote']]
        if len(rows) != 1:
            raise ValueError('Unknown or expired quote')
        quote, quantity = rows[0], arguments['quantity']
        stock = int(fact(self.data, quote['stock'], 'exp_stock', self.confirmed))
        if stock + self.state['inventory_deltas'].get(quote['quote'], 0) < quantity:
            raise ValueError('Insufficient quote inventory')
        return self.record_purchase(quote, quantity)

    def record_purchase(self, quote, quantity):
        record = dict(id='purchase-' + str(len(self.state['purchases']) + 1),
                      quote=quote['quote'], quantity=quantity,
                      total_cents=int(quote['total_cents']) * quantity,
                      style=quote['style'], size=quote['size'], color=quote['color'])
        self.state['purchases'].append(record)
        self.state['payments'].append(dict(order_id=record['id'],
            amount_cents=record['total_cents'], funding='available_funds'))
        deltas = self.state['inventory_deltas']
        deltas[quote['quote']] = deltas.get(quote['quote'], 0) - quantity
        self.calls.append('buy_quote')
        return deepcopy(record)
