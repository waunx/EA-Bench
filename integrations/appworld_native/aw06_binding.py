"""Explicit AW06 cart projection onto real AppWorld Amazon APIs."""
from copy import deepcopy
from pathlib import Path
import json,os,shutil,hashlib
from integrations.packet_stages.open_aw06 import OpenAW06

def ensure_template():
    root=Path(os.environ['APPWORLD_ROOT']).resolve();repo=Path(__file__).resolve().parents[2]
    if root==repo or repo in root.parents:raise ValueError('Native runtime must be outside repository')
    dst=root/'data/tasks/eaaw006_1'
    if not dst.exists():
        shutil.copytree(root/'data/tasks/4815c06_1',dst)
        specs=json.loads((dst/'specs.json').read_text());specs['datetime']='2026-09-29T12:00:00'
        (dst/'specs.json').write_text(json.dumps(specs,indent=2)+'\n')
    return 'eaaw006_1'

class NativeAW06(OpenAW06):
    def __init__(self,variant='full',answers=None,experiment_name='aw06-native'):
        super().__init__(variant=variant,answers=answers)
        from appworld import AppWorld
        from appworld.apps.amazon import models
        self.native=AppWorld(task_id=ensure_template(),experiment_name=experiment_name,load_ground_truth=False)
        self.models=models;self.native_calls=[];self.product_map={};self.card_map={};self._seed()
    def call_native(self,name,**kwargs):
        result=getattr(self.native.apis.amazon,name)(access_token=self.token,**kwargs)
        self.native_calls.append(dict(api='amazon.'+name,arguments=kwargs,result=result));return result
    def _seed(self):
        from appworld.apps.admin import models as admin
        from appworld.common.datetime import DateTime
        m=self.models;user=m.User.find_one(email=self.native.task.supervisor.email);self.user_id=user.id
        password=next(r['password'] for r in self.native.apis.supervisor.show_account_passwords() if r['account_name']=='amazon')
        self.token=self.native.apis.amazon.login(username=user.email,password=password)['access_token']
        self.address_id=next(a.id for a in user.addresses if a.name.lower()=='home')
        m.PrimeSubscription.create_save(user_id=user.id,start_date=DateTime.parse('2026-09-01'),end_date=DateTime.parse('2027-09-01'),payment_card_digits=user.payment_cards[0].last_four_digits,paid_amount=1)
        base=user.payment_cards[0];bank=admin.PaymentCard.find_one(card_number=base.card_number)
        for i,row in enumerate(self.reference_data['cards']):
            # Distinct authored owner labels satisfy native owner/network uniqueness.
            fields=base.to_dict(keep_computed=False);fields.pop('id')
            fields.update(card_number=6100000000060000+i,card_name=row['network'],owner_name='Authored AW06 '+row['card'],expiry_year=2030 if row['active']=='1' else 2020)
            card=m.PaymentCard.create_save(**fields);self.card_map[row['card']]=card.id
            fields2=bank.to_dict(keep_computed=False);fields2.pop('id')
            fields2.update({k:v for k,v in fields.items() if k!='user_id'});fields2['balance']=int(row['available_cents'])/100
            admin.PaymentCard.create_save(**fields2)
        old=self.confirmed;self.confirmed=deepcopy(self.answers)
        template=m.Product.all()[0].to_dict(keep_computed=False);template.pop('id')
        catalog={r['sku']:r for r in self.reference_data['catalog']}
        for sku in sorted(set(catalog)|{r['sku'] for r in self.backend.state['cart_rows']}):
            row=catalog.get(sku,dict(name=sku,price_cents=100,stock=100))
            price=row['price_cents'] if row['price_cents'] not in ('',None) else self.public_price()
            product=m.Product.create_save(**dict(template,name='EA AW06 '+row['name'],price=int(price)/100,inventory_quantity=int(row['stock']),has_variations=False,color=None,relative_size=None))
            self.product_map[sku]=product.id
        self.confirmed=old
        self.promo=m.Promo.create_save(type='percent',code='EA006',min_amount=0,discount=10)
        self.set_native_cart(self.backend.state['cart_rows'],self.backend.state['cart_metadata'])
        self.baseline=self.native_snapshot();self.native_calls=[]
    def set_native_cart(self,rows,metadata):
        self.call_native('clear_cart')
        quantities={};gifts={}
        for row in rows:
            pid=self.product_map[row['sku']];quantity=int(row['qty'])
            quantities[pid]=quantities.get(pid,0)+quantity
            gifts[pid]=gifts.get(pid,0)+(quantity if row['gift']=='1' else 0)
        for pid,quantity in quantities.items():
            self.call_native('add_product_to_cart',product_id=pid,quantity=quantity)
            if gifts[pid]:self.call_native('add_gift_wrapping_to_product',product_id=pid,quantity=gifts[pid])
        if self.models.User.by_id(self.user_id).cart_promo_code:
            self.call_native('remove_promo_code_from_cart')
        coupon=metadata.get('coupon')
        if coupon:
            # Native promo codes have a five-character limit; preserve authored
            # coupon identity through a stable private alias.
            code='EA006' if coupon=='EA006' else hashlib.sha256(coupon.encode()).hexdigest()[:5].upper()
            promo=self.models.Promo.find_one(code=code)
            if promo is None:promo=self.models.Promo.create_save(type='percent',code=code,min_amount=0,discount=10)
            self.call_native('apply_promo_code_to_cart',promo_code=promo.code)
    def replace_cart(self,arguments):
        result=super().replace_cart(arguments)
        self.set_native_cart(arguments['rows'],arguments['metadata']);return result
    def record_order(self,arguments,quantities,total):
        if arguments['address']!='HOME':raise ValueError('No native binding for non-home address')
        rows=[r for r in self.backend.state['cart_rows'] if r['selected']=='1']
        self.set_native_cart(rows,{'coupon':'EA006'})
        self.call_native('place_order',payment_card_id=self.card_map[arguments['card']],address_id=self.address_id)
        result=super().record_order(arguments,quantities,total)
        self.set_native_cart(self.backend.state['cart_rows'],self.backend.state['cart_metadata']);return result
    def native_snapshot(self):
        m=self.models;user=m.User.by_id(self.user_id)
        return dict(orders={r.id:r.to_dict(keep_computed=False) for r in m.Order.all()},items={r.id:r.to_dict(keep_computed=False) for r in m.OrderItem.all()},inventory={r.id:r.inventory_quantity for r in m.Product.all()},balances={name:round(m.PaymentCard.by_id(identity).balance*100) for name,identity in self.card_map.items()},cart=sorted((r.product_id,r.quantity,r.gift_wrap_quantity) for r in user.cart_entries),coupon=user.cart_promo_code)
    def native_checks(self):
        s,b=self.native_snapshot(),self.baseline;t=self.checker.target
        new=set(s['orders'])-set(b['orders']);order=self.models.Order.by_id(next(iter(new))) if len(new)==1 else None
        expected_inventory=dict(b['inventory'])
        for sku,qty in t['order'].items():expected_inventory[self.product_map[sku]]-=qty
        actual=sorted((r.product_id,r.ordered_quantity) for r in order.order_items) if order else []
        expected=sorted((self.product_map[sku],qty) for sku,qty in t['order'].items())
        balances=dict(b['balances']);balances[t['card']]-=t['total_cents']
        checks=dict(one_native_order=len(new)==1,native_basket_exact=actual==expected,native_card_address=bool(order) and order.payment_card_id==self.card_map[t['card']] and order.address_id==self.address_id,native_paid=bool(order) and round(order.paid_amount*100)==t['total_cents'],native_balances=s['balances']==balances,native_inventory=s['inventory']==expected_inventory,native_cart_restored=s['cart']==b['cart'],native_coupon_restored=s['coupon']==b['coupon'])
        checks.update(old_orders=all(s['orders'].get(k)==v for k,v in b['orders'].items()),old_items=all(s['items'].get(k)==v for k,v in b['items'].items()),native_item_count=len(s['items'])==len(b['items'])+len(t['order']))
        return checks
    def close(self):self.native.close()
