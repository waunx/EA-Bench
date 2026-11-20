"""AW03 account tools; private world values are not API data."""
from copy import deepcopy
from .packet_interface import PacketInterface, SYSTEM, OUTPUT_FORMAT
from .english_packet import inputs
from .english_aw03 import load, products, resolve, wrapping, NeedFact
from .aw03_state import AW03Checker, initial_state

API_FORMATS = {
    'list_products': {}, 'list_flights': {}, 'list_orders': {},
    'place_order': {'sku': 'product ID', 'quantity': 'positive integer',
                    'gift_wrap': 'boolean', 'destination': 'delivery destination label'},
}


class OpenAW03(PacketInterface):
    case = 'AW03'
    validation_layer = 'authored_fixture'
    api_formats = API_FORMATS
    need_fact_error = NeedFact
    fact_labels = {'allowance': 'Effective outbound baggage entitlement', 'border_wrap': 'Gift packaging weight',
                   'low_stock': 'Product inventory', 'Gift packaging discrepancy': 'Gift packaging specification',
                   'Outbound entitlement discrepancy': 'Outbound baggage entitlement'}

    def __init__(self, variant='full', answers=None, ask_handler=None):
        self.variant, self.folder = variant, inputs('AW03', variant)
        self.data = load(variant)
        self.state = initial_state(self.data)
        self.answers, self.confirmed = deepcopy(answers or {}), {}
        self.checker = AW03Checker(variant, self.answers, self)
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
        if name == 'list_orders':
            return {'orders': deepcopy(self.state['orders'])}
        if name == 'list_flights':
            return {'flights': deepcopy(self.data['itinerary.csv'])}
        rows = deepcopy(products(self.data))
        for row in rows:
            if row['stock'] != '':
                row['stock'] = str(int(row['stock']) + self.state['inventory_deltas'].get(row['sku'], 0))
        return {'products': rows}

    def place_order(self, arguments):
        if set(arguments) != {'sku', 'quantity', 'gift_wrap', 'destination'}:
            raise ValueError('Expected sku, quantity, gift_wrap and destination')
        sku, qty = arguments['sku'], arguments['quantity']
        if not isinstance(sku, str) or type(qty) is not int or qty <= 0:
            raise ValueError('Expected product ID and positive integer quantity')
        if type(arguments['gift_wrap']) is not bool or not isinstance(arguments['destination'], str) or not arguments['destination'].strip():
            raise ValueError('Expected gift-wrap boolean and destination string')
        rows = [r for r in products(self.data) if r['sku'] == sku]
        if len(rows) != 1:
            raise ValueError('Unknown product')
        row = rows[0]
        stock = resolve(self.data, 'low_stock', self.confirmed) if sku == 'BP104' else int(row['stock'])
        if stock + self.state['inventory_deltas'].get(sku, 0) < qty:
            raise ValueError('Insufficient inventory')
        gift_g = wrapping(self.data, row, self.confirmed) if arguments['gift_wrap'] else 0
        destination = arguments['destination'].strip().lower().replace('_', ' ')
        if destination in {'my home', 'home address'}:
            destination = 'home'
        order = dict(id='purchase-' + str(len(self.state['orders']) + 1), sku=sku, quantity=qty,
                     gift_wrap=arguments['gift_wrap'], destination=destination, unit_net_g=int(row['net_g']),
                     unit_gift_g=gift_g, arrival=row['arrival'], total_cents=qty * int(row['unit_cents']))
        self.state['orders'].append(order)
        self.state['payments'].append(dict(order_id=order['id'], amount_cents=order['total_cents']))
        self.state['inventory_deltas'][sku] = self.state['inventory_deltas'].get(sku, 0) - qty
        self.calls.append('place_order')
        return deepcopy(order)
