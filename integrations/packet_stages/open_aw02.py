"""AW02 ordinary account tools; unresolved facts are never filled from the oracle."""
from copy import deepcopy
from .packet_interface import PacketInterface, SYSTEM, OUTPUT_FORMAT
from .english_packet import inputs
from .english_aw02 import load, offers, resolve, NeedFact
from .aw02_state import AW02Checker, initial_state

API_FORMATS = {
    'list_checklist': {},
    'list_pledges': {},
    'list_offers': {},
    'list_orders': {},
    'place_order': {'lines': [{'offer': 'offer ID', 'packs': 'positive integer'}],
                    'destination': 'delivery destination label'},
}


class OpenAW02(PacketInterface):
    case = 'AW02'
    validation_layer = 'authored_fixture'
    api_formats = API_FORMATS
    need_fact_error = NeedFact
    fact_labels = dict(sam='Final pad commitment', lamps='Lamp requirement', pad_pack='Retail pack size')

    def __init__(self, variant='full', answers=None, ask_handler=None):
        self.variant, self.folder = variant, inputs('AW02', variant)
        self.data = load(variant)
        self.state = initial_state(self.data)
        self.answers, self.confirmed = deepcopy(answers or {}), {}
        self.checker = AW02Checker(variant, self.answers, self)
        self.files = {p.name: p for p in self.folder.iterdir() if p.is_file()}
        self.events, self.calls, self.effects = [], [], {}
        self.done, self.result = False, None
        self.ask_handler = ask_handler

    def call(self, name, arguments):
        if name not in API_FORMATS:
            raise ValueError('Unknown API')
        if name == 'place_order':
            return self.place_order(arguments)
        if arguments:
            raise ValueError('This API takes no arguments')
        if name == 'list_orders':
            return {'orders': deepcopy(self.state['orders'])}
        if name == 'list_checklist':
            return {'checklist': deepcopy(self.data['checklist.csv'])}
        if name == 'list_pledges':
            names = ['pledges.csv', 'pledge_amendments.csv', 'camp_pledge_archive.csv']
            return {n: deepcopy(self.data[n]) for n in names if n in self.data}
        rows = deepcopy(offers(self.data))
        for row in rows:
            row['stock_packs'] = str(int(row['stock_packs']) +
                                     self.state['inventory_deltas'].get(row['offer'], 0))
        return {'offers': rows}

    def place_order(self, arguments):
        if set(arguments) != {'lines', 'destination'}:
            raise ValueError('Expected lines and destination')
        if not isinstance(arguments['lines'], list) or not arguments['lines']:
            raise ValueError('Expected nonempty order lines')
        if not isinstance(arguments['destination'], str) or not arguments['destination'].strip():
            raise ValueError('Expected delivery destination string')
        selected = {}
        for line in arguments['lines']:
            if not isinstance(line, dict) or set(line) != {'offer', 'packs'}:
                raise ValueError('Expected offer and packs in each line')
            if not isinstance(line['offer'], str) or type(line['packs']) is not int or line['packs'] <= 0:
                raise ValueError('Expected offer ID and positive integer packs')
            selected[line['offer']] = selected.get(line['offer'], 0) + line['packs']
        products = {r['offer']: r for r in offers(self.data)}
        lines = []
        for identity, count in selected.items():
            if identity not in products:
                raise ValueError('Unknown offer')
            row = products[identity]
            remaining = int(row['stock_packs']) + self.state['inventory_deltas'].get(identity, 0)
            if count > remaining:
                raise ValueError('Insufficient stock')
            pack = resolve(self.data, 'pad_pack', self.confirmed) if identity == 'P1' else int(row['pack'])
            lines.append(dict(offer=identity, item=row['item'], packs=count, units=pack * count,
                              cost_cents=int(row['price_cents']) * count, arrival=row['arrival']))
        return self.record_order(lines, arguments['destination'])

    def record_order(self, lines, destination):
        destination = destination.strip().lower().replace('_', ' ')
        if destination in {'my home', 'home address'}:
            destination = 'home'
        total = sum(r['cost_cents'] for r in lines)
        record = dict(id='purchase-' + str(len(self.state['orders']) + 1),
                      lines=deepcopy(lines), destination=destination, total_cents=total)
        self.state['orders'].append(record)
        self.state['payments'].append(dict(order_id=record['id'], amount_cents=total))
        for row in lines:
            deltas = self.state['inventory_deltas']
            deltas[row['offer']] = deltas.get(row['offer'], 0) - row['packs']
        self.calls.append('place_order')
        return deepcopy(record)
