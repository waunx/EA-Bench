"""AW03 fixed original world author controls; never model predictions."""
import argparse,json,os
from pathlib import Path

def run(output):
 from appworld import AppWorld
 from appworld.apps.amazon import models
 output.mkdir(parents=True,exist_ok=True);reports={}
 private=json.loads((Path(os.environ['APPWORLD_ROOT'])/'data/tasks/efc3cea_1/ground_truth/private_data.json').read_text())
 for branch in ['no_op','positive','unwrapped']:
  with AppWorld(task_id='efc3cea_1',experiment_name='aw03-original-'+branch) as w:
   calls=[]
   def call(name,**args):
    r=getattr(w.apis.amazon,name)(**args);calls.append(dict(api='amazon.'+name,arguments={k:v for k,v in args.items() if k!='access_token'},result=r));return r
   if branch!='no_op':
    user=models.User.find_one(email=w.task.supervisor.email)
    password=next(r['password'] for r in w.apis.supervisor.show_account_passwords() if r['account_name']=='amazon')
    token=w.apis.amazon.login(username=user.email,password=password)['access_token']
    call('clear_cart',access_token=token)
    call('add_product_to_cart',access_token=token,product_id=private['giftable_product_id'],quantity=4)
    if branch=='positive':call('add_gift_wrapping_to_product',access_token=token,product_id=private['giftable_product_id'],quantity=4)
    card=max((c for c in user.payment_cards if not c.expired),key=lambda c:c.balance)
    home=next(a for a in user.addresses if a.name.lower()=='home')
    call('place_order',access_token=token,payment_card_id=card.id,address_id=home.id)
    w.apis.supervisor.complete_task()
   w.execute('pass');report=w.evaluate().to_dict();reports[branch]=report
   (output/(branch+'.json')).write_text(json.dumps(dict(task_id='efc3cea_1',scope='Original private author control; not solver or authored variant',native_calls=calls,evaluator=report),indent=2,default=str)+'\n')
 assert reports['positive']['success'] and not reports['no_op']['success'] and not reports['unwrapped']['success'],reports
 (output/'result.json').write_text(json.dumps(reports,indent=2,default=str)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output.resolve())
