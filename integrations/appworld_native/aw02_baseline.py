"""AW02 official original private API controls, separate from supplemental worlds."""
import argparse,json,os
from pathlib import Path

def run(output):
    from appworld import AppWorld
    output.mkdir(parents=True,exist_ok=True);root=Path(os.environ['APPWORLD_ROOT']);reports={}
    private=json.loads((root/'data/tasks/f3a6713_1/ground_truth/private_data.json').read_text())
    for branch in ['no_op','positive','missing_item']:
        with AppWorld(task_id='f3a6713_1',experiment_name='aw02-original-'+branch) as world:
            calls=[]
            def call(name,**args):
                app,method=name.split('.');r=getattr(getattr(world.apis,app),method)(**args)
                calls.append(dict(api=name,arguments={k:v for k,v in args.items() if k not in ['access_token','password']},result=r));return r
            if branch!='no_op':
                from appworld.apps.amazon import models
                user=models.User.find_one(email=world.task.supervisor.email)
                password=next(r['password'] for r in world.apis.supervisor.show_account_passwords() if r['account_name']=='amazon')
                token=world.apis.amazon.login(username=world.task.supervisor.email,password=password)['access_token']
                call('amazon.clear_cart',access_token=token)
                requirements=list(private['to_order_product_type_to_quantity'].items())
                if branch=='missing_item':requirements=requirements[1:]
                for kind,quantity in requirements:
                    products=call('amazon.search_products',access_token=token,product_type=kind,page_limit=20,sort_by='-rating')
                    product=next(r for r in products if r['rating']==private['to_order_product_type_to_max_rating'][kind] and r['inventory_quantity']>=quantity)
                    call('amazon.add_product_to_cart',access_token=token,product_id=product['product_id'],quantity=quantity)
                cards=[]
                for card in user.payment_cards:
                    try:
                        if not card.expired:cards.append((card.balance,card.id))
                    except Exception:continue
                call('amazon.place_order',access_token=token,payment_card_id=max(cards)[1],address_id=user.addresses[0].id)
                call('supervisor.complete_task')
            world.execute('pass');report=world.evaluate().to_dict();reports[branch]=report
            (output/(branch+'.json')).write_text(json.dumps(dict(task_id='f3a6713_1',scope='official original private control, not solver nor supplemental binding',native_calls=calls,evaluator=report),indent=2,default=str)+'\n')
    assert reports['positive']['success'],reports['positive']
    assert not reports['no_op']['success'] and not reports['missing_item']['success']
    (output/'result.json').write_text(json.dumps(reports,indent=2,default=str)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output.resolve())
