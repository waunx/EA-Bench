"""Private AW01 original-world API replay; never an agent evaluation or variant binding."""
import argparse
import json
import os
from pathlib import Path


def run(output: Path):
    from appworld import AppWorld
    task_id = 'f99d726_1'
    output.mkdir(parents=True, exist_ok=True)
    reports = {}
    for branch in ('no_op', 'positive', 'wrong_color'):
        with AppWorld(task_id=task_id, experiment_name=f'aw01-native-{branch}') as world:
            transcript = []
            def call(name, **kwargs):
                app, method = name.split('.')
                result = getattr(getattr(world.apis, app), method)(**kwargs)
                transcript.append({'api': name, 'arguments': {k:v for k,v in kwargs.items() if k not in ('access_token','password')}, 'result': result})
                return result
            if branch != 'no_op':
                # Private author replay uses official oracle target; this is not model performance.
                private = json.loads((Path(os.environ['APPWORLD_ROOT'])/'data/tasks'/task_id/'ground_truth/private_data.json').read_text())
                password = next(x['password'] for x in world.apis.supervisor.show_account_passwords() if x['account_name']=='amazon')
                token = world.apis.amazon.login(username=world.task.supervisor.email,password=password)['access_token']
                color = private['best_available_color'] if branch == 'positive' else 'black'
                products = call('amazon.search_products',access_token=token,query=private['product_name'],color=color,relative_size=private['desired_relative_size'],page_limit=20)
                product = next(p for p in products if p['name']==private['product_name'] and p['inventory_quantity']>0)
                deliverers = call('amazon.show_return_deliverers')
                call('amazon.initiate_return',access_token=token,order_id=private['order_id'],product_id=private['product_id'],deliverer_id=deliverers[0]['deliverer_id'],quantity=1)
                cards = world.apis.amazon.show_payment_cards(access_token=token)
                addresses = world.apis.amazon.show_addresses(access_token=token)
                call('amazon.add_product_to_cart',access_token=token,product_id=product['product_id'],quantity=1,clear_cart_first=True)
                call('amazon.place_order',access_token=token,payment_card_id=next(c['payment_card_id'] for c in cards if (c['expiry_year'], c['expiry_month']) >= (2023, 5)),address_id=addresses[0]['address_id'])
                call('supervisor.complete_task')
            # Persist direct API mutations before the official evaluator reads on-disk output.
            world.execute('pass')
            report = world.evaluate().to_dict()
            reports[branch] = report
            (output/f'{branch}.json').write_text(json.dumps({'evaluation_layer':'official_original_task_private_api_replay','task_id':task_id,'authored_variant_binding':False,'api_calls':transcript,'evaluator':report},indent=2)+'\n')
    assert reports['positive']['success'], reports['positive']
    assert not reports['no_op']['success']
    assert not reports['wrong_color']['success']
    print(json.dumps({key:{'success':value['success'],'passes':len(value['passes']),'tests':value['num_tests']} for key,value in reports.items()},indent=2))

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    run(args.output)
