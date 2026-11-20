"""AW06 task-only interface with host-side outcome checks, no exposed DAG."""
from copy import deepcopy
from pathlib import PurePosixPath
from .authored import DecisionChecker
from .english_aw06 import inputs as english_inputs
from .aw06 import AW06Checker, same
from .fixtures import AW06FixtureBackend

SYSTEM = 'Return exactly one JSON action per turn using the supplied output format.'
OUTPUT_FORMAT = {
    'list_files': {'tool': 'list_files'},
    'read_file': {'tool': 'read_file', 'path': 'relative input filename'},
    'list_tools': {'tool': 'list_tools'},
    'call': {'tool': 'call', 'name': 'API name', 'arguments': {}},
    'ask_user': {'tool': 'ask_user', 'question': 'question text'},
    'submit': {'tool': 'submit', 'result': {'summary': 'final response to the user'}},
}

API_FORMATS = {
    'list_products': {},
    'list_payment_cards': {},
    'show_cart': {},
    'replace_cart': {'rows': [{'line': 'string', 'sku': 'string', 'qty': 'positive integer string',
                             'selected': '0 or 1', 'seller': 'string', 'gift': '0 or 1'}],
                     'metadata': 'object'},
    'place_order': {'card': 'payment card ID', 'address': 'address ID'},
}


class OpenAW06:
    case = 'AW06'
    def __init__(self, ask_handler=None, *, variant='full', answers=None):
        self.variant = variant
        self.answers, self.confirmed = deepcopy(answers or {}), {}
        self.folder = english_inputs(variant)
        reference = DecisionChecker('AW06', variant, self.answers, input_directory=self.folder)
        self.backend = AW06FixtureBackend(reference.expected)
        self.checker = AW06Checker(variant, self.answers, self.backend, input_directory=self.folder)
        self.reference_data = deepcopy(reference.data)
        self.public_cart = dict(rows=deepcopy(reference.data['before']), metadata=deepcopy(reference.data['meta']))
        self.calls = self.backend.calls
        self.files = {str(p.relative_to(self.folder)): p for p in self.folder.rglob('*') if p.is_file()}
        self.products = {r['sku']: deepcopy(r) for r in reference.data['catalog']}
        self.cards = {r['card']: deepcopy(r) for r in reference.data['cards']}
        self.events, self.effects = [], {}
        self.done = False
        self.result = None
        self.ask_handler = ask_handler

    def snapshot(self):
        return self.backend.snapshot()

    def confirm(self, values):
        if any(k not in self.answers or not same(v, self.answers[k]) for k, v in values.items()):
            raise ValueError('Host answer does not match the selected world')
        self.confirmed.update(deepcopy(values))

    def observation(self):
        return {'task_description': (self.folder.parent / 'prompt.md').read_text(),
                'output_format': deepcopy(OUTPUT_FORMAT)}

    def step(self, action):
        if self.done:
            return {'error': 'session_finalized'}
        before = self.backend.snapshot()
        terminal = isinstance(action, dict) and action.get('tool') == 'submit'
        try:
            reply = self.dispatch(action)
        except (KeyError, ValueError, TypeError) as error:
            reply = {'error': str(error)}
            if terminal:
                self.result = {'success': False, 'status': 'invalid_submission'}
        if terminal:
            self.done = True
            reply = {'submission_received': True, 'terminal': True}
        self.events.append({'action': deepcopy(action), 'reply': deepcopy(reply),
                            'before': before, 'after': self.backend.snapshot()})
        return reply

    def dispatch(self, action):
        if not isinstance(action, dict):
            raise ValueError('Expected one JSON object')
        tool = action.get('tool')
        if tool in {'list_files', 'list_tools'}:
            if set(action) != {'tool'}:
                raise ValueError('Unexpected argument')
            if tool == 'list_files':
                return {'files': sorted(self.files)}
            return {'apis': {k: API_FORMATS[k] for k in sorted(API_FORMATS)}}
        if tool == 'read_file':
            if set(action) != {'tool', 'path'} or not isinstance(action['path'], str):
                raise ValueError('Expected path string')
            name = action['path']
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
            if set(action) != {'tool', 'result'} or not isinstance(action['result'], dict):
                raise ValueError('Expected result object')
            if set(action['result']) != {'summary'} or not isinstance(action['result']['summary'], str):
                raise ValueError('Expected summary string')
            try:
                acceptance = self.checker.final({}, {'completed': True}, layer='authored_state')
            except Exception as error:
                raise RuntimeError('State evaluator failed') from error
            self.result = {'status': 'submitted', 'success': acceptance.status == 'passed',
                           'acceptance': acceptance.to_dict()}
            return {'submission_received': True}
        raise ValueError('Unknown tool')

    def call(self, name, arguments):
        if name not in API_FORMATS:
            raise ValueError('Unknown API')
        if name in {'list_products', 'list_payment_cards', 'show_cart'}:
            if arguments:
                raise ValueError('This API takes no arguments')
            if name == 'list_products':
                return {'products': deepcopy(list(self.products.values()))}
            if name == 'list_payment_cards':
                return {'cards': deepcopy(list(self.cards.values()))}
            return deepcopy(self.public_cart)
        if name == 'replace_cart':
            return self.replace_cart(arguments)
        return self.place_order(arguments)

    def replace_cart(self, arguments):
        if set(arguments) != {'rows', 'metadata'}:
            raise ValueError('Expected rows and metadata')
        if not isinstance(arguments['rows'], list) or not isinstance(arguments['metadata'], dict):
            raise ValueError('Invalid cart data types')
        self.validate_rows(arguments['rows'])
        self.backend.state['cart_rows'] = deepcopy(arguments['rows'])
        self.backend.state['cart_metadata'] = deepcopy(arguments['metadata'])
        self.public_cart = deepcopy(arguments)
        self.backend.calls.append('replace_cart')
        if len(self.backend.state['orders']) > len(self.checker.initial['orders']):
            self.effects['restore'] = (same(self.backend.state['cart_rows'], self.checker.initial['cart_rows'])
                                       and same(self.backend.state['cart_metadata'], self.checker.initial['cart_metadata']))
        return {'updated': True}

    @staticmethod
    def validate_rows(rows):
        seen = set()
        for row in rows:
            if not isinstance(row, dict) or set(row) != {'line','sku','qty','selected','seller','gift'}:
                raise ValueError('Invalid cart row fields')
            if not all(isinstance(v, str) for v in row.values()) or not row['qty'].isdigit() or int(row['qty']) <= 0:
                raise ValueError('Invalid cart row values')
            if row['selected'] not in {'0','1'} or row['gift'] not in {'0','1'} or row['line'] in seen:
                raise ValueError('Invalid flags or duplicate cart line')
            seen.add(row['line'])

    def place_order(self, arguments):
        if set(arguments) != {'card', 'address'} or not all(isinstance(v,str) and v for v in arguments.values()):
            raise ValueError('Expected card and address strings')
        card = self.cards.get(arguments['card'])
        if card is None or card['active'] != '1':
            raise ValueError('Payment card unavailable')
        quantities = {}
        for row in self.backend.state['cart_rows']:
            if row['selected'] == '1':
                quantities[row['sku']] = quantities.get(row['sku'], 0) + int(row['qty'])
        if not quantities:
            raise ValueError('No selected items')
        total = 0
        for sku, qty in quantities.items():
            product = self.products.get(sku)
            if product is None or int(product['stock']) < qty:
                raise ValueError('Selected product unavailable')
            price = product['price_cents']
            if price in ('', None):
                price = self.public_price()
            total += int(price) * qty
        if int(card['available_cents']) < total:
            raise ValueError('Insufficient available balance')
        return self.record_order(arguments, quantities, total)

    def public_price(self):
        records = [r for r in self.reference_data['claims'] if r['fact'] == 'ps5_price']
        if records:
            revision = max(r['revision'] for r in records)
            values = {r['value'] for r in records if r['revision'] == revision}
            if len(values) == 1:
                return next(iter(values))
        if 'ps5_price' not in self.confirmed:
            raise ValueError('Current product price requires confirmation')
        return self.confirmed['ps5_price']

    def record_order(self, arguments, quantities, total):
        before = self.backend.snapshot()
        state = self.backend.state
        self.effects['preparation'] = same(quantities, self.checker.target['order'])
        identity = 'fixture-order-' + str(len(state['orders']))
        order = dict(id=identity, order=deepcopy(quantities), card=arguments['card'],
                     address=arguments['address'], total_cents=total)
        state['orders'].append(order)
        state['payments'].append(dict(order_id=identity, card=arguments['card'], total_cents=total))
        state['cart_rows'] = [r for r in state['cart_rows'] if r['selected'] != '1']
        self.public_cart['rows'] = [r for r in self.public_cart['rows'] if r['selected'] != '1']
        self.backend.calls.append('place_order')
        self.effects['order'] = self.checker.order_created(before, self.backend.snapshot())
        return deepcopy(order)
