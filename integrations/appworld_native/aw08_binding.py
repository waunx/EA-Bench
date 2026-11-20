"""AW08 real Venmo request effects; event attribution remains supplemental."""
import json,os,shutil
from pathlib import Path
from integrations.packet_stages.open_aw08 import OpenAW08

def template():
    root=Path(os.environ['APPWORLD_ROOT']).resolve()
    repo=Path(__file__).resolve().parents[2]
    if root==repo or repo in root.parents:raise ValueError('Use isolated native root')
    destination=root/'data/tasks/eaaw008_1'
    if not destination.exists():
        shutil.copytree(root/'data/tasks/a676f2a_1',destination)
        p=destination/'specs.json';d=json.loads(p.read_text())
        d['datetime']='2026-09-29T12:00:00';p.write_text(json.dumps(d)+'\n')
    return 'eaaw008_1'

class NativeAW08(OpenAW08):
    def __init__(self,variant='full',answers=None,experiment_name='aw08-native'):
        super().__init__(variant,answers)
        from appworld import AppWorld
        from appworld.apps.venmo import models
        self.models=models
        self.native=AppWorld(task_id=template(),experiment_name=experiment_name,load_ground_truth=False)
        self.user=models.User.find_one(email=self.native.task.supervisor.email)
        password=next(r['password'] for r in self.native.apis.supervisor.show_account_passwords() if r['account_name']=='venmo')
        self.token=self.native.apis.venmo.login(username=self.user.email,password=password)['access_token']
        self.members={'SELF':self.user};self.request_map={};self.native_calls=[]
        for who in sorted({r['person'] for r in self.data['meal_replies.csv']}):
            if who=='SELF':continue
            self.members[who]=models.User.create_save(first_name='Authored',last_name=who,
                email='aw08-'+who.lower()+'@example.com',password='native-private-seed',verified=True)
        from appworld.common.datetime import DateTime
        for row in self.state['requests']:
            if row['state']=='cancelled':
                self.request_map[row['request']]=None
                continue
            fields=dict(sender_id=self.user.id,receiver_id=self.members[row['person']].id,
                        amount=row['amount_cents']/100,description=row['note'],private=not row['public'])
            if row['state']!='pending':fields['approved_at']=DateTime.now()
            r=models.PaymentRequest.create_save(**fields)
            self.request_map[row['request']]=r.id
        from integrations.packet_stages.english_aw08 import fact
        self.payment_map={}
        for row in self.data['payments.csv']+self.data.get('payment_journal.csv',[]):
            status=fact(self.data,row['status'],'pay18_state',self.answers)
            if status!='settled':continue
            amount=int(fact(self.data,row['amount_cents'],'pay17_amount',self.answers))
            event=fact(self.data,row['event_ref'],'pay17_event',self.answers)
            sender=self.members[row['person']]
            tx=models.Transaction.create_save(sender_id=sender.id,receiver_id=self.user.id,
                amount=amount/100,description=event+': '+row['memo'],private=True)
            self.payment_map[row['payment']]=tx.id
        self.baseline=self.native_snapshot()

    def native_snapshot(self):
        result={name:{str(r.id):r.to_dict(keep_computed=False) for r in getattr(self.models,name).all()}
                for name in ['PaymentRequest','Transaction']}
        result['balances']={str(r.id):r.venmo_balance for r in self.models.User.all()}
        return result

    def api(self,name,**args):
        result=getattr(self.native.apis.venmo,name)(access_token=self.token,**args)
        self.native_calls.append(dict(api=name,arguments=args,result=result))
        return result

    def create(self,args):
        # Validate through authored API, then realize exactly that request natively.
        result=super().create(args)
        native=self.api('create_payment_request',user_email=self.members[args['person']].email,
                        amount=args['amount_cents']/100,description=args['note'],private=not args['public'])
        self.request_map[result['request']]=native['payment_request_id']
        return result

    def cancel(self,args):
        row=next(r for r in self.state['requests'] if r['request']==args['request'])
        if row['state']=='pending':
            self.api('delete_payment_request',payment_request_id=self.request_map[args['request']])
        return super().cancel(args)

    def native_checks(self):
        state=self.native_snapshot();target=self.checker.target;checks={}
        cancelled={str(self.request_map[k]) for k in target['cancel_requests'] if self.request_map[k] is not None}
        for identity,row in self.baseline['PaymentRequest'].items():
            checks['old_request_'+identity]=(identity not in state['PaymentRequest'] if identity in cancelled
                                             else state['PaymentRequest'].get(identity)==row)
        bound={i for i in self.request_map.values() if i is not None}
        active=[r for r in self.models.PaymentRequest.all() if r.id in bound and r.pending
                and r.description=='Lunch Meeting Order']
        wanted={k:v for k,v in target['owed'].items() if k!='SELF' and v>0}
        checks['one_request_per_person']=len(active)==len(wanted)
        for person,amount in wanted.items():
            found=[r for r in active if r.receiver_id==self.members[person].id]
            checks['owed_'+person]=(len(found)==1 and round(found[0].amount*100)==amount
                                    and not found[0].private and found[0].sender_id==self.user.id)
        checks['exact_request_count']=len(state['PaymentRequest'])==len(self.baseline['PaymentRequest'])-len(cancelled)+len(target['new_requests'])
        checks['payments_unchanged']=state['Transaction']==self.baseline['Transaction']
        checks['balances_unchanged']=state['balances']==self.baseline['balances']
        return checks
