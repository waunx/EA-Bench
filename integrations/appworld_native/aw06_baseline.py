"""Private original AW06 replay, separate from supplemental task/model evidence."""
import argparse,json
from pathlib import Path

def run(output):
    from appworld import AppWorld
    output.mkdir(parents=True,exist_ok=True)
    reports={}
    for branch in ['positive','no_op','cart_not_restored']:
        with AppWorld(task_id='4815c06_1',experiment_name='aw06-original-'+branch) as world:
            calls=[]
            def call(name,**kwargs):
                reply=getattr(world.apis.amazon,name)(**kwargs)
                calls.append(dict(api='amazon.'+name,arguments={k:v for k,v in kwargs.items() if k!='access_token'},result=reply))
                return reply
            if branch!='no_op':
                password=next(r['password'] for r in world.apis.supervisor.show_account_passwords() if r['account_name']=='amazon')
                token=world.apis.amazon.login(username=world.task.supervisor.email,password=password)['access_token']
                from appworld.apps.amazon import models
                user=models.User.find_one(email=world.task.supervisor.email)
                before=[dict(product_id=r.product_id,quantity=r.quantity) for r in user.cart_entries]
                call('clear_cart',access_token=token)
                for name in ['Sony PlayStation 5','Etekcity Food Kitchen Scale','Xbox Series S Console']:
                    found=call('search_products',access_token=token,query=name,page_limit=20)
                    product=next(p for p in found if p['name']==name)
                    call('add_product_to_cart',access_token=token,product_id=product['product_id'],quantity=1)
                cards=call('show_payment_cards',access_token=token)
                card=next(c for c in cards if c['card_name']=='Discover')
                addresses=call('show_addresses',access_token=token)
                address=next(a for a in addresses if a['name'].lower()=='home')
                call('place_order',access_token=token,payment_card_id=card['payment_card_id'],address_id=address['address_id'])
                if branch=='positive':
                    for row in before:call('add_product_to_cart',access_token=token,**row)
                world.apis.supervisor.complete_task()
            world.execute('pass')
            result=world.evaluate().to_dict()
            reports[branch]=dict(case='AW06',task_id='4815c06_1',layer='original_fixed_world_private_api_replay',model_episodes=0,authored_variant_binding=False,api_calls=calls,evaluator=result)
            (output/(branch+'.json')).write_text(json.dumps(reports[branch],indent=2)+'\n')
    assert reports['positive']['evaluator']['success']
    assert not reports['no_op']['evaluator']['success']
    assert not reports['cart_not_restored']['evaluator']['success']
    return reports

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    run(p.parse_args().output)
