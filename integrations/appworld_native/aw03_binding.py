"""AW03 authored-world binding to real Amazon transactions; safe host entry point."""
from ea_bench.paths import APPWORLD_ROOT, APPWORLD_PYTHON
from pathlib import Path
from copy import deepcopy
from datetime import date
import json,os,shutil,subprocess,uuid,hashlib
from integrations.packet_stages.open_aw03 import OpenAW03
from integrations.packet_stages.english_aw03 import products,resolve
ROOT=Path(__file__).resolve().parents[2]
RUNTIME=Path(APPWORLD_ROOT)
PYTHON=Path(APPWORLD_PYTHON)

def ensure_template():
 root=Path(os.environ['APPWORLD_ROOT']).resolve()
 if root==ROOT or ROOT in root.parents:raise ValueError('Native runtime must be outside repository')
 src,dst=root/'data/tasks/efc3cea_1',root/'data/tasks/eaaw003_1'
 if not dst.exists():
  shutil.copytree(src,dst)
  specs=json.loads((dst/'specs.json').read_text());specs['datetime']='2026-09-29T12:00:00'
  (dst/'specs.json').write_text(json.dumps(specs,indent=2)+'\n')
 assert json.loads((dst/'specs.json').read_text())['datetime']=='2026-09-29T12:00:00'
 return 'eaaw003_1'

class NativeAW03(OpenAW03):
 validation_layer='native_api_with_authored_supplemental_checks'
 def __init__(self,variant='full',answers=None,ask_handler=None,experiment_name=None):
  super().__init__(variant,answers,ask_handler)
  from appworld import AppWorld
  from appworld.apps.amazon import models
  self.native=AppWorld(task_id=ensure_template(),experiment_name=experiment_name or 'aw03-'+uuid.uuid4().hex,load_ground_truth=False)
  self.models=models;self.native_calls=[];self.product_map={};self.order_map={};self.address_map={};self.quote_adjustments=[]
  self._seed()
 def _seed(self):
  from appworld.apps.admin import models as admin
  m=self.models;self.user=m.User.find_one(email=self.native.task.supervisor.email)
  password=next(x['password'] for x in self.native.apis.supervisor.show_account_passwords() if x['account_name']=='amazon')
  self.card=self.user.payment_cards[0];self.card.expiry_year=2030;self.card.save()
  self.bankcard=admin.PaymentCard.find_one(card_number=self.card.card_number)
  self.bankcard.expiry_year=2030;self.bankcard.balance=10000;self.bankcard.save()
  self.token=self.native.apis.amazon.login(username=self.native.task.supervisor.email,password=password)['access_token']
  self.native.apis.amazon.clear_cart(access_token=self.token)
  self.user.cart_promo_code=None;self.user.save()
  home=next(a for a in self.user.addresses if a.name.lower()=='home');self.address_map['home']=home.id
  template=m.Product.by_id(1480).to_dict(keep_computed=False);template.pop('id')
  for row in products(self.data):
   stock=resolve(self.data,'low_stock',self.answers) if row['sku']=='BP104' else int(row['stock'])
   p=m.Product.create_save(**dict(template,name='AW03 '+row['sku'],price=int(row['unit_cents'])/100,weight=int(row['net_g'])/1000,rating=int(row['rating'])/100,inventory_quantity=stock,delivery_days=(date.fromisoformat(row['arrival'])-date(2026,9,29)).days,has_variations=False))
   self.product_map[row['sku']]=p.id
  self.baseline=self.native_snapshot()
 def native_snapshot(self):
  m=self.models
  return dict(orders={x.id:x.to_dict(keep_computed=False) for x in m.Order.all()},items={x.id:x.to_dict(keep_computed=False) for x in m.OrderItem.all()},inventory={x.id:x.inventory_quantity for x in m.Product.all()},balance_cents=round(m.PaymentCard.by_id(self.card.id).balance*100))
 def native_call(self,name,**kwargs):
  result=getattr(self.native.apis.amazon,name)(**kwargs)
  self.native_calls.append(dict(api='amazon.'+name,arguments={k:v for k,v in kwargs.items() if k!='access_token'},result=result));return result
 def place_order(self,arguments):
  before=deepcopy(self.state)
  record=super().place_order(arguments)
  try:
   if record['destination'] not in self.address_map:raise ValueError('Destination has no native binding')
   self.native_call('clear_cart',access_token=self.token)
   self.user.cart_promo_code=None;self.user.save()
   pid=self.product_map[record['sku']];qty=record['quantity']
   self.native_call('add_product_to_cart',access_token=self.token,product_id=pid,quantity=qty)
   if record['gift_wrap']:self.native_call('add_gift_wrapping_to_product',access_token=self.token,product_id=pid,quantity=qty)
   quote=self.native_call('show_cart',access_token=self.token)
   offset=round(quote['tax']+quote['delivery_fee']+quote['gift_wrap_fee'],2)
   promo=self.models.Promo.create_save(type='flat',code='E'+uuid.uuid4().hex[:4],min_amount=0,discount=offset)
   self.native_call('apply_promo_code_to_cart',access_token=self.token,promo_code=promo.code)
   self.quote_adjustments.append(dict(quote=quote,authored_offset_cents=round(offset*100),reason='Authored inclusive unit quote; native fees offset by actual flat promo'))
   result=self.native_call('place_order',access_token=self.token,payment_card_id=self.card.id,address_id=self.address_map[record['destination']])
   self.order_map[record['id']]=result['order_id'];return record
  except Exception:
   self.state=before;raise
 def native_checks(self):
  s,b=self.native_snapshot(),self.baseline;t=self.checker.target;new=set(s['orders'])-set(b['orders'])
  order=self.models.Order.by_id(next(iter(new))) if len(new)==1 else None
  row=next(r for r in products(self.data) if r['sku']==t['sku']);pid=self.product_map[t['sku']]
  expected=dict(b['inventory']);expected[pid]-=t['quantity']
  actual=[(r.product_id,r.ordered_quantity,r.gift_wrap_quantity,round(r.price*100),str(r.expected_delivery_at)[:10]) for r in order.order_items] if order else []
  return dict(one_native_order=len(new)==1,exact_native_wrapped_basket=actual==[(pid,t['quantity'],t['quantity'],int(row['unit_cents']),row['arrival'])],native_inventory_exact=s['inventory']==expected,native_debit_exact=b['balance_cents']-s['balance_cents']==t['pay_cents'],native_paid_exact=bool(order) and round(order.paid_amount*100)==t['pay_cents'],native_quote_offset_exact=bool(order) and round(order.discount*100)==round((order.tax+order.delivery_fee+order.gift_wrap_fee)*100),native_home_and_card=bool(order) and order.address_id==self.address_map['home'] and order.payment_card_id==self.card.id,old_orders_preserved=all(s['orders'].get(k)==v for k,v in b['orders'].items()),old_items_preserved=all(s['items'].get(k)==v for k,v in b['items'].items()),native_item_count=len(s['items'])==len(b['items'])+1)
