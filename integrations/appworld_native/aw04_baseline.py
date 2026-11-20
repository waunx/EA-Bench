"""AW04 fixed original world author controls; never model predictions."""
import argparse,json,os
from pathlib import Path

def run(output):
 from appworld import AppWorld
 from appworld.apps.amazon import models
 output.mkdir(parents=True,exist_ok=True);reports={}
 private=json.loads((Path(os.environ['APPWORLD_ROOT'])/'data/tasks/30e8586_1/ground_truth/private_data.json').read_text())
 for branch in ['no_op','positive','missing_recipient']:
  with AppWorld(task_id='30e8586_1',experiment_name='aw04-original-'+branch) as w:
   calls=[]
   def call(api_name,**args):
    r=getattr(w.apis.amazon,api_name)(**args);calls.append(dict(api='amazon.'+api_name,arguments={k:v for k,v in args.items() if k!='access_token'},result=r));return r
   if branch!='no_op':
    user=models.User.find_one(email=w.task.supervisor.email)
    password=next(r['password'] for r in w.apis.supervisor.show_account_passwords() if r['account_name']=='amazon')
    token=w.apis.amazon.login(username=user.email,password=password)['access_token']
    card=max((c for c in user.payment_cards if not c.expired),key=lambda c:c.balance)
    products=call('search_products',access_token=token,product_type='popcorn maker',page_limit=20,sort_by='-rating')
    product=next(p for p in products if p['rating']==private['max_rating_purchasable'] and p['inventory_quantity']>=4)
    if private['prime_beneficial']:call('subscribe_prime',access_token=token,payment_card_id=card.id,duration='monthly')
    homes=private['friends_home_address_texts']
    if branch=='missing_recipient':homes=homes[:-1]
    for i,home in enumerate(homes):
     street,city,state,country,zipcode=home.split('\n')
     address=call('add_address',access_token=token,name='Original friend '+str(i),street_address=street,city=city,state=state,country=country,zip_code=int(zipcode))
     call('clear_cart',access_token=token)
     call('add_product_to_cart',access_token=token,product_id=product['product_id'],quantity=1)
     call('add_gift_wrapping_to_product',access_token=token,product_id=product['product_id'],quantity=1)
     call('place_order',access_token=token,payment_card_id=card.id,address_id=address['address_id'])
    w.apis.supervisor.complete_task()
   w.execute('pass');report=w.evaluate().to_dict();reports[branch]=report
   (output/(branch+'.json')).write_text(json.dumps(dict(task_id='30e8586_1',scope='Original private author control; not solver or authored variant',native_calls=calls,evaluator=report),indent=2,default=str)+'\n')
 assert reports['positive']['success'] and not reports['no_op']['success'] and not reports['missing_recipient']['success'],reports
 (output/'result.json').write_text(json.dumps(reports,indent=2,default=str)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output.resolve())
