"""AW01 authored quote adapter over real AppWorld state and Amazon APIs."""
from copy import deepcopy
from datetime import date
from pathlib import Path
import json
import os
import shutil
from integrations.packet_stages.open_aw01 import OpenAW01
from integrations.packet_stages.english_aw01 import offers, fact
SIZES = {'S':'small','M':'medium','L':'large','XL':'extra-large','XS':'extra-small'}

def ensure_template():
    root=Path(os.environ['APPWORLD_ROOT']).resolve()
    repo=Path(__file__).resolve().parents[2]
    if root==repo or repo in root.parents:
        raise ValueError('Native runtime must be outside the repository')
    src,dst=root/'data/tasks/f99d726_1',root/'data/tasks/eaaw001_1'
    if not dst.exists():
        shutil.copytree(src,dst)
        specs=json.loads((dst/'specs.json').read_text())
        specs['datetime']='2026-09-29T12:00:00'
        (dst/'specs.json').write_text(json.dumps(specs,indent=2)+'\n')
    assert json.loads((dst/'specs.json').read_text())['datetime']=='2026-09-29T12:00:00'
    return 'eaaw001_1'

class NativeAW01(OpenAW01):
    validation_layer='native_api_with_authored_supplemental_checks'
    def __init__(self,variant='full',answers=None,ask_handler=None,experiment_name='aw01-supplemental'):
        super().__init__(variant,answers,ask_handler)
        from appworld import AppWorld
        from appworld.apps.amazon import models
        self.native=AppWorld(task_id=ensure_template(),experiment_name=experiment_name,load_ground_truth=False)
        self.models=models
        self.native_calls=[]
        self.order_map,self.product_map,self.quote_map={},{},{}
        self.return_map,self.purchase_map={},{}
        self._seed()
    def _seed(self):
        from appworld.common.datetime import DateTime
        m=self.models
        template=m.Order.by_id(3146)
        user=template.user
        self.user_id=user.id
        password=next(x['password'] for x in self.native.apis.supervisor.show_account_passwords() if x['account_name']=='amazon')
        self.card=user.payment_cards[0]
        self.card.expiry_year=2030
        self.card.save()
        from appworld.apps.admin import models as admin_models
        bank_card=admin_models.PaymentCard.find_one(card_number=self.card.card_number)
        bank_card.expiry_year=2030
        bank_card.balance=1000
        bank_card.save()
        self.address_id=user.addresses[0].id
        self.token=self.native.apis.amazon.login(username=self.native.task.supervisor.email,password=password)['access_token']
        self.native.apis.amazon.clear_cart(access_token=self.token)
        for subscription in user.prime_subscriptions:
            subscription.end_date=DateTime.parse('2030-01-01')
            subscription.save()
        assert user.is_prime, 'Seed requires a native Prime subscription'
        product_template=m.Product.by_id(195).to_dict(keep_computed=False)
        product_template.pop('id')
        quote_rows=offers(self.data)
        tuples={(q['style'],q['size'],q['color']) for q in quote_rows}
        for row in self.data['orders.csv']:
            size=fact(self.data,row['size'],'purchased_size',self.answers)
            tuples.add((row['style'],size,row['color']))
        for style,size,color in sorted(tuples):
            fields=dict(product_template,name=style,relative_size=SIZES[size],color=color,product_type='t-shirt',has_variations=False,inventory_quantity=100)
            product=m.Product.create_save(**fields)
            self.product_map[(style,size,color)]=product.id
        for q in quote_rows:
            self.quote_map[q['quote']]=self.product_map[(q['style'],q['size'],q['color'])]
        for row in self.data['orders.csv']:
            size=fact(self.data,row['size'],'purchased_size',self.answers)
            product_id=self.product_map[(row['style'],size,row['color'])]
            fields=template.to_dict(keep_computed=False)
            fields.pop('id')
            fields.update(created_at=DateTime.parse(row['placed']),tax=0,delivery_fee=0,payment_card_id=self.card.id)
            order=m.Order.create_save(**fields)
            delivered=fact(self.data,row['status'],'last_order_status',self.answers)=='delivered'
            m.OrderItem.create_save(order_id=order.id,product_id=product_id,ordered_quantity=1,returned_quantity=0,gift_wrap_quantity=0,price=int(row['paid_cents'])/100,expected_delivery_at=DateTime.parse(row['placed']),delivered_at=DateTime.parse(row['placed']) if delivered else None)
            self.order_map[row['order']]={'order_id':order.id,'product_id':product_id}
        self.baseline=self.native_snapshot()
    def native_snapshot(self):
        m=self.models
        return {'orders':{x.id:x.to_dict(keep_computed=False) for x in m.Order.all()},
                'items':{x.id:x.to_dict(keep_computed=False) for x in m.OrderItem.all()},
                'returns':{x.id:x.to_dict(keep_computed=False) for x in m.ProductReturn.all()},
                'inventory':{x.id:x.inventory_quantity for x in m.Product.all()},
                'balance_cents':round(self.card.balance*100)}

    def native_call(self,name,**kwargs):
        result=getattr(self.native.apis.amazon,name)(**kwargs)
        self.native_calls.append({'api':'amazon.'+name,'arguments':{k:v for k,v in kwargs.items() if k!='access_token'},'result':result})
        return result

    def initiate_return(self,arguments):
        before=deepcopy(self.state)
        record=super().initiate_return(arguments)
        mapping=self.order_map[arguments['order']]
        try:
            deliverer=self.native.apis.amazon.show_return_deliverers()[0]['deliverer_id']
            result=self.native_call('initiate_return',access_token=self.token,quantity=1,deliverer_id=deliverer,**mapping)
        except Exception:
            self.state=before
            raise
        self.return_map[record['id']]=result['return_id']
        return record

    def record_purchase(self,quote,quantity):
        product=self.models.Product.by_id(self.quote_map[quote['quote']])
        total=int(quote['total_cents'])*quantity
        # Exact native tax-inclusive debit. Authored quote includes shipping;
        # native Prime shipping is zero, with the selected shipping cost in net price.
        candidates=[c for c in range(max(1,total//quantity-1000),total//quantity+1)
                    if round(c*quantity+round(c*quantity/10))==total]
        if not candidates:
            raise ValueError('Quote total cannot be represented by native tax rounding')
        product.price=candidates[0]/100
        arrival=fact(self.data,quote['arrival'],'standard_arrival',self.confirmed)
        product.delivery_days=(date.fromisoformat(arrival)-date(2026,9,29)).days
        product.save()
        self.native_call('add_product_to_cart',access_token=self.token,product_id=product.id,quantity=quantity,clear_cart_first=True)
        result=self.native_call('place_order',access_token=self.token,payment_card_id=self.card.id,address_id=self.address_id)
        record=super().record_purchase(quote,quantity)
        self.purchase_map[record['id']]=result['order_id']
        return record
    def native_checks(self):
        s,b=self.native_snapshot(),self.baseline
        t=self.checker.target
        new_orders=set(s['orders'])-set(b['orders'])
        new_returns=set(s['returns'])-set(b['returns'])
        checks={'one_native_purchase':len(new_orders)==1,'one_native_return':len(new_returns)==1,
                'old_native_orders_unchanged':all(s['orders'].get(k)==v for k,v in b['orders'].items()),
                'original_native_returns_unchanged':all(s['returns'].get(k)==v for k,v in b['returns'].items()),
                'native_debit_exact':b['balance_cents']-s['balance_cents']==t['pay_cents']}
        expected_inventory=dict(b['inventory'])
        expected_inventory[self.quote_map[t['quote']]]-=1
        checks['native_inventory_exact']=s['inventory']==expected_inventory
        order_id=next(iter(new_orders),None)
        order=self.models.Order.by_id(order_id) if order_id is not None else None
        items=order.order_items if order else []
        checks['native_item_exact']=len(items)==1 and items[0].product_id==self.quote_map[t['quote']] and items[0].ordered_quantity==1
        checks['native_paid_amount_exact']=bool(order) and round(order.paid_amount*100)==t['pay_cents']
        checks['native_card_exact']=bool(order) and order.payment_card_id==self.card.id
        expected=self.order_map[t['return_order']]
        r=s['returns'].get(next(iter(new_returns),None),{})
        checks['native_return_target_exact']=r.get('order_id')==expected['order_id'] and r.get('product_id')==expected['product_id'] and r.get('quantity')==1
        old_items=deepcopy(b['items'])
        for row in old_items.values():
            if row['order_id']==expected['order_id'] and row['product_id']==expected['product_id']:
                row['returned_quantity']+=1
        checks['native_existing_items_exact']=all(s['items'].get(k)==v for k,v in old_items.items())
        checks['native_item_count_exact']=len(s['items'])==len(b['items'])+1
        return checks
    def finish_or_ask(self,action):
        reply=super().finish_or_ask(action)
        if action.get('tool')=='submit':
            self.native.execute('pass')
            checks=self.native_checks()
            self.result['native_effects']={'layer':self.validation_layer,'checks':checks,'success':all(checks.values()),'original_evaluator_used':False}
            self.result['success']=self.result['success'] and all(checks.values())
        return reply

    def close(self):
        self.native.close()
