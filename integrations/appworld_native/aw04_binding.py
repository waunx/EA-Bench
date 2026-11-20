"""AW04 native recipient deliveries; authored tariff rules stay supplemental."""
from pathlib import Path
import json,os,shutil,uuid
from integrations.packet_stages.open_aw04 import OpenAW04
from integrations.packet_stages.english_aw04 import products,fact

def ensure_template():
 root=Path(os.environ['APPWORLD_ROOT']).resolve();repo=Path(__file__).resolve().parents[2]
 if root==repo or repo in root.parents:raise ValueError('Native runtime must be outside repository')
 dst=root/'data/tasks/eaaw004_1'
 if not dst.exists():
  shutil.copytree(root/'data/tasks/30e8586_1',dst)
  specs=json.loads((dst/'specs.json').read_text());specs['datetime']='2026-09-29T12:00:00'
  (dst/'specs.json').write_text(json.dumps(specs,indent=2)+'\n')
 return 'eaaw004_1'

class NativeAW04(OpenAW04):
 validation_layer='native_api_with_authored_supplemental_checks'
 def __init__(self,variant='full',answers=None,ask_handler=None,experiment_name=None):
  super().__init__(variant,answers,ask_handler)
  from appworld import AppWorld
  from appworld.apps.amazon import models
  self.models=models;self.native=AppWorld(task_id=ensure_template(),experiment_name=experiment_name or 'aw04-'+uuid.uuid4().hex,load_ground_truth=False)
  self.native_calls=[];self.product_map={};self.address_map={};self.order_map={};self._seed()
 def _seed(self):
  from appworld.apps.admin import models as admin
  m=self.models;self.user=m.User.find_one(email=self.native.task.supervisor.email)
  self.card=self.user.payment_cards[0];self.card.expiry_year=2030;self.card.save()
  bank=admin.PaymentCard.find_one(card_number=self.card.card_number);bank.expiry_year=2030;bank.balance=10000;bank.save()
  password=next(x['password'] for x in self.native.apis.supervisor.show_account_passwords() if x['account_name']=='amazon')
  self.token=self.native.apis.amazon.login(username=self.native.task.supervisor.email,password=password)['access_token']
  self.native.apis.amazon.clear_cart(access_token=self.token)
  self.user.cart_promo_code=None;self.user.save()
  assert not self.user.is_prime
  template=m.Product.all()[0].to_dict(keep_computed=False);template.pop('id')
  for row in products(self.data):
   p=m.Product.create_save(**dict(template,name='AW04 '+row['sku'],price=int(row['unit_cents'])/100,rating=int(fact(self.data,row['rating'],'a_rating',self.answers))/100,inventory_quantity=int(fact(self.data,row['stock'],'b_stock',self.answers)),delivery_days=3,has_variations=False))
   self.product_map[row['sku']]=p.id
  template=self.user.addresses[0].to_dict(keep_computed=False);template.pop('id')
  for row in self.data['addresses.csv']:
   address=m.Address.create_save(**dict(template,name=row['person']+' '+row['address'],street_address='Authored destination '+row['address']))
   self.address_map[(row['person'],row['address'])]=address.id
  self.baseline=self.native_snapshot()
 def native_call(self,name,**kwargs):
  result=getattr(self.native.apis.amazon,name)(**kwargs)
  self.native_calls.append(dict(api='amazon.'+name,arguments={k:v for k,v in kwargs.items() if k!='access_token'},result=result));return result
 def native_snapshot(self):
  m=self.models
  return dict(orders={x.id:x.to_dict(keep_computed=False) for x in m.Order.all()},items={x.id:x.to_dict(keep_computed=False) for x in m.OrderItem.all()},subscriptions={x.id:x.to_dict(keep_computed=False) for x in m.PrimeSubscription.all()},inventory={x.id:x.inventory_quantity for x in m.Product.all()},balance_cents=round(m.PaymentCard.by_id(self.card.id).balance*100))
 def subscribe(self):
  if self.state['prime_active']:raise ValueError('Prime is already active')
  self.native_call('subscribe_prime',access_token=self.token,payment_card_id=self.card.id,duration='monthly')
  return super().subscribe()
 def record_order(self,arguments,home,product):
  self.native_call('clear_cart',access_token=self.token)
  pid=self.product_map[product['sku']];qty=arguments['quantity']
  self.native_call('add_product_to_cart',access_token=self.token,product_id=pid,quantity=qty)
  if arguments['gift_wrap']:self.native_call('add_gift_wrapping_to_product',access_token=self.token,product_id=pid,quantity=qty)
  result=self.native_call('place_order',access_token=self.token,payment_card_id=self.card.id,address_id=self.address_map[(home['person'],home['address'])])
  record=super().record_order(arguments,home,product);self.order_map[record['id']]=result['order_id'];return record
 def native_checks(self):
  s,b=self.native_snapshot(),self.baseline;t=self.checker.target
  new=set(s['orders'])-set(b['orders']);subs=set(s['subscriptions'])-set(b['subscriptions'])
  actual=[];expected=[];paid=0
  for identity in new:
   order=self.models.Order.by_id(identity);paid+=round(order.paid_amount*100)
   actual.extend((order.address_id,r.product_id,r.ordered_quantity,r.gift_wrap_quantity,round(r.price*100),order.payment_card_id) for r in order.order_items)
  for row in self.checker.expected_orders.values():expected.append((self.address_map[(row['person'],row['address'])],self.product_map[row['sku']],1,1,row['item_cents'],self.card.id))
  inventory=dict(b['inventory']);inventory[self.product_map[t['sku']]]-=4
  subscription_paid=sum(round(self.models.PrimeSubscription.by_id(i).paid_amount*100) for i in subs)
  fees=all(round(self.models.Order.by_id(i).tax*100)==round(sum(r.price*r.ordered_quantity for r in self.models.Order.by_id(i).order_items)*10) and self.models.Order.by_id(i).discount==0 and round(self.models.Order.by_id(i).gift_wrap_fee*100)==500 for i in new)
  return dict(four_native_deliveries=len(new)==4,exact_native_destinations_basket=sorted(actual)==sorted(expected),native_membership_choice=len(subs)==int(t['prime']) and self.models.User.by_id(self.user.id).is_prime==t['prime'],native_subscription_price=subscription_paid==(1500 if t['prime'] else 0),native_debit_reconciled=b['balance_cents']-s['balance_cents']==paid+subscription_paid,native_inventory_exact=s['inventory']==inventory,native_fees_retained=fees,native_delivery_fees=all(self.models.Order.by_id(i).delivery_fee==(0 if t['prime'] else 5) for i in new),old_orders_preserved=all(s['orders'].get(k)==v for k,v in b['orders'].items()),old_items_preserved=all(s['items'].get(k)==v for k,v in b['items'].items()),old_subscriptions_preserved=all(s['subscriptions'].get(k)==v for k,v in b['subscriptions'].items()))
