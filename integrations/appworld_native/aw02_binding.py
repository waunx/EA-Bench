"""AW02 real native pack purchases, explicit Prime and tax-offset promotion."""
from copy import deepcopy
from datetime import date
from pathlib import Path
import json,os,shutil
from integrations.packet_stages.open_aw02 import OpenAW02
from integrations.packet_stages.english_aw02 import offers,resolve

def ensure_template():
    root=Path(os.environ['APPWORLD_ROOT']).resolve();repo=Path(__file__).resolve().parents[2]
    if root==repo or repo in root.parents:raise ValueError('Native runtime must be outside repository')
    dst=root/'data/tasks/eaaw002_1'
    if not dst.exists():
        shutil.copytree(root/'data/tasks/f3a6713_1',dst)
        specs=json.loads((dst/'specs.json').read_text());specs['datetime']='2026-09-29T12:00:00'
        (dst/'specs.json').write_text(json.dumps(specs,indent=2)+'\n')
    assert json.loads((dst/'specs.json').read_text())['datetime']=='2026-09-29T12:00:00'
    return 'eaaw002_1'

class NativeAW02(OpenAW02):
    validation_layer='native_api_with_authored_supplemental_checks'
    def __init__(self,variant='full',answers=None,ask_handler=None,experiment_name='aw02-supplemental'):
        super().__init__(variant,answers,ask_handler)
        from appworld import AppWorld
        from appworld.apps.amazon import models
        self.native=AppWorld(task_id=ensure_template(),experiment_name=experiment_name,load_ground_truth=False)
        self.models=models;self.native_calls=[];self.product_map={};self.order_map={};self._seed()
    def _seed(self):
        from appworld.common.datetime import DateTime
        m=self.models;user=m.User.find_one(email=self.native.task.supervisor.email);self.user_id=user.id
        from appworld.apps.admin import models as admin
        self.card=user.payment_cards[0];self.card.expiry_year=2030;self.card.save()
        bank=admin.PaymentCard.find_one(card_number=self.card.card_number);bank.expiry_year=2030;bank.balance=1000;bank.save()
        assert round(self.card.balance*100)==100000
        self.address_id=user.addresses[0].id
        m.PrimeSubscription.create_save(user_id=user.id,start_date=DateTime.parse('2026-09-01'),end_date=DateTime.parse('2027-09-01'),payment_card_digits=self.card.last_four_digits,paid_amount=1)
        password=next(x['password'] for x in self.native.apis.supervisor.show_account_passwords() if x['account_name']=='amazon')
        self.token=self.native.apis.amazon.login(username=self.native.task.supervisor.email,password=password)['access_token']
        self.native.apis.amazon.clear_cart(access_token=self.token)
        user.cart_promo_code=None;user.save()
        self.promo=m.Promo.create_save(type='percent',code='EA002',min_amount=0,discount=10)
        template=m.Product.all()[0].to_dict(keep_computed=False);template.pop('id');self.offer_projection={}
        for r in offers(self.data):
            pack=resolve(self.data,'pad_pack',self.answers) if r['offer']=='P1' else int(r['pack'])
            days=(date.fromisoformat(r['arrival'])-date(2026,9,29)).days
            fields=dict(template,name=f"EA AW02 {r['offer']} {r['item']} {pack}-unit pack",product_type=r['item'],description=f"Authored retail pack containing {pack} units; offer {r['offer']}",price=int(r['price_cents'])/100,delivery_days=days,inventory_quantity=int(r['stock_packs']),rating=int(r['rating'])/100,color=None,relative_size=None,has_variations=False)
            product=m.Product.create_save(**fields);self.product_map[r['offer']]=product.id
            self.offer_projection[r['offer']]=dict(product_id=product.id,units_per_pack=pack,price_cents=int(r['price_cents']),arrival=r['arrival'],stock_packs=int(r['stock_packs']))
        self.baseline=self.native_snapshot()
    def native_snapshot(self):
        m=self.models
        return dict(orders={x.id:x.to_dict(keep_computed=False) for x in m.Order.all()},items={x.id:x.to_dict(keep_computed=False) for x in m.OrderItem.all()},inventory={x.id:x.inventory_quantity for x in m.Product.all()},balance_cents=round(m.PaymentCard.by_id(self.card.id).balance*100))
    def native_call(self,name,**kwargs):
        result=getattr(self.native.apis.amazon,name)(**kwargs)
        self.native_calls.append(dict(api='amazon.'+name,arguments={k:v for k,v in kwargs.items() if k!='access_token'},result=result));return result
    def record_order(self,lines,destination):
        # Invoked only after authored argument/stock validation; never inject the target basket.
        self.native_call('clear_cart',access_token=self.token)
        for row in lines:self.native_call('add_product_to_cart',access_token=self.token,product_id=self.product_map[row['offer']],quantity=row['packs'])
        self.native_call('apply_promo_code_to_cart',access_token=self.token,promo_code=self.promo.code)
        result=self.native_call('place_order',access_token=self.token,payment_card_id=self.card.id,address_id=self.address_id)
        record=super().record_order(lines,destination);self.order_map[record['id']]=result['order_id'];return record
    def native_checks(self):
        s,b=self.native_snapshot(),self.baseline;t=self.checker.target;new=set(s['orders'])-set(b['orders'])
        order=self.models.Order.by_id(next(iter(new))) if len(new)==1 else None
        expected_inventory=dict(b['inventory'])
        for row in t['plan']:expected_inventory[self.product_map[row['offer']]]-=row['packs']
        actual_items=sorted((r.product_id,r.ordered_quantity,round(r.price*100)) for r in order.order_items) if order else []
        expected_items=sorted((self.product_map[r['offer']],r['packs'],self.offer_projection[r['offer']]['price_cents']) for r in t['plan'])
        arrivals=sorted((r.product_id,str(r.expected_delivery_at)[:10]) for r in order.order_items) if order else []
        expected_arrivals=sorted((self.product_map[r['offer']],self.offer_projection[r['offer']]['arrival']) for r in t['plan'])
        return dict(native_arrivals_exact=arrivals==expected_arrivals,one_native_order=len(new)==1,exact_native_basket=actual_items==expected_items,native_inventory_exact=s['inventory']==expected_inventory,native_debit_exact=b['balance_cents']-s['balance_cents']==t['total'],native_paid_exact=bool(order) and round(order.paid_amount*100)==t['total'],native_tax_offset_exact=bool(order) and round(order.tax*100)==round(order.discount*100) and order.delivery_fee==0,old_orders_preserved=all(s['orders'].get(k)==v for k,v in b['orders'].items()),old_items_preserved=all(s['items'].get(k)==v for k,v in b['items'].items()),native_item_count=len(s['items'])==len(b['items'])+len(t['plan']),native_card_and_address=bool(order) and order.payment_card_id==self.card.id and order.address_id==self.address_id)
