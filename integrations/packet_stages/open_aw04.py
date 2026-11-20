"""AW04 ordinary membership and recipient-order operations."""
from copy import deepcopy
from .packet_interface import PacketInterface, SYSTEM, OUTPUT_FORMAT
from .english_packet import inputs
from .english_aw04 import load, products, fact, prime_price, NeedFact
from .aw04_state import AW04Checker, initial_state

API_FORMATS = {
    'list_products': {}, 'list_addresses': {}, 'list_tariffs': {}, 'get_membership': {}, 'list_orders': {},
    'subscribe_prime': {},
    'place_order': {'person': 'recipient name', 'address': 'address ID', 'sku': 'product ID',
                    'quantity': 'positive integer', 'gift_wrap': 'boolean'},
}


class OpenAW04(PacketInterface):
    case = 'AW04'
    validation_layer = 'authored_fixture'
    api_formats = API_FORMATS
    need_fact_error = NeedFact
    fact_labels = dict(grant_address='Recipient destination', b_stock='Product inventory',
                       c_gift='Gift-wrapping availability', remote_shipping='Delivery tariff',
                       prime_price='Monthly membership price', a_rating='Product rating')

    def __init__(self, variant='full', answers=None, ask_handler=None):
        self.variant, self.folder = variant, inputs('AW04', variant)
        self.data = load(variant)
        self.state = initial_state(self.data)
        self.answers, self.confirmed = deepcopy(answers or {}), {}
        self.checker = AW04Checker(variant, self.answers, self)
        self.files = {p.name: p for p in self.folder.iterdir() if p.is_file()}
        self.events, self.calls, self.effects = [], [], {}
        self.done, self.result, self.ask_handler = False, None, ask_handler

    def call(self, name, arguments):
        if name not in API_FORMATS:
            raise ValueError('Unknown API')
        if name == 'place_order':
            return self.place_order(arguments)
        if arguments:
            raise ValueError('This API takes no arguments')
        if name == 'subscribe_prime':
            return self.subscribe()
        if name == 'list_addresses':
            return {'addresses': deepcopy(self.data['addresses.csv'])}
        if name == 'list_tariffs':
            return {'tariffs': deepcopy(self.data['quote_rules.csv'])}
        if name == 'list_orders':
            return {'orders': deepcopy(self.state['orders'])}
        if name == 'get_membership':
            try:
                price = prime_price(self.data, self.confirmed)
            except NeedFact:
                price = None
            return dict(active=self.state['prime_active'], monthly_price_cents=price)
        rows = deepcopy(products(self.data))
        for row in rows:
            if row['stock'] != '':
                row['stock'] = str(int(row['stock']) + self.state['inventory_deltas'].get(row['sku'], 0))
        return {'products': rows}

    def subscribe(self):
        if self.state['prime_active']:
            raise ValueError('Prime is already active')
        price = prime_price(self.data, self.confirmed)
        record = dict(id='prime-' + str(len(self.state['subscriptions']) + 1), interval='monthly', amount_cents=price)
        self.state['subscriptions'].append(record)
        self.state['payments'].append(dict(kind='subscription', ref=record['id'], amount_cents=price))
        self.state['ledger'].append(dict(kind='subscription', id=record['id']))
        self.state['prime_active'] = True
        self.calls.append('subscribe_prime')
        return deepcopy(record)

    def place_order(self, arguments):
        if set(arguments) != {'person', 'address', 'sku', 'quantity', 'gift_wrap'}:
            raise ValueError('Expected person, address, sku, quantity and gift_wrap')
        if any(not isinstance(arguments[k], str) for k in ['person', 'address', 'sku']):
            raise ValueError('Expected recipient, address and product strings')
        qty = arguments['quantity']
        if type(qty) is not int or qty <= 0 or type(arguments['gift_wrap']) is not bool:
            raise ValueError('Expected positive integer quantity and gift-wrap boolean')
        homes = [r for r in self.data['addresses.csv'] if r['person'] == arguments['person'] and r['address'] == arguments['address']]
        rows = [r for r in products(self.data) if r['sku'] == arguments['sku']]
        if len(homes) != 1 or len(rows) != 1:
            raise ValueError('Unknown recipient address or current product')
        home, row = homes[0], rows[0]
        stock = int(fact(self.data, row['stock'], 'b_stock', self.confirmed))
        if stock + self.state['inventory_deltas'].get(row['sku'], 0) < qty:
            raise ValueError('Insufficient inventory')
        if arguments['gift_wrap'] and int(fact(self.data, row['gift'], 'c_gift', self.confirmed)) != 1:
            raise ValueError('Gift wrapping is unavailable')
        return self.record_order(arguments, home, row)

    def record_order(self, arguments, home, product):
        rate = next(r for r in self.data['quote_rules.csv'] if r['zone'] == home['zone'])
        shipping = 0 if self.state['prime_active'] else int(fact(self.data, rate['shipping_cents'], 'remote_shipping', self.confirmed))
        item = int(product['unit_cents']) * arguments['quantity']
        gift = int(rate['gift_cents']) * arguments['quantity'] if arguments['gift_wrap'] else 0
        record = dict(arguments, id='order-' + str(len(self.state['orders']) + 1), item_cents=item,
                      gift_cents=gift, shipping_cents=shipping, total_cents=item+gift+shipping,
                      prime_applied=self.state['prime_active'])
        self.state['orders'].append(record)
        self.state['payments'].append(dict(kind='order', ref=record['id'], amount_cents=record['total_cents']))
        self.state['ledger'].append(dict(kind='order', id=record['id']))
        sku = product['sku']
        self.state['inventory_deltas'][sku] = self.state['inventory_deltas'].get(sku, 0) - arguments['quantity']
        self.calls.append('place_order')
        return deepcopy(record)
