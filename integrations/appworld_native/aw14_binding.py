"""AW14 expense effects in a real Splitwise world with explicit authored IDs."""
import json
import os
from pathlib import Path
import shutil
from integrations.packet_stages.open_aw14 import OpenAW14

def template():
    root=Path(os.environ['APPWORLD_ROOT']).resolve()
    repo=Path(__file__).resolve().parents[2]
    if root==repo or repo in root.parents:raise ValueError('Use isolated native runtime root')
    destination=root/'data/tasks/eaaw014_1'
    if not destination.exists():
        shutil.copytree(root/'data/tasks/8d42650_1',destination)
        p=destination/'specs.json';d=json.loads(p.read_text())
        d['datetime']='2025-04-15T12:00:00';p.write_text(json.dumps(d,indent=2)+'\n')
    return 'eaaw014_1'

class NativeAW14(OpenAW14):
    def __init__(self,variant='full',answers=None,experiment_name='aw14-native'):
        super().__init__(variant,answers)
        from appworld import AppWorld
        from appworld.apps.splitwise import models
        self.native=AppWorld(task_id=template(),experiment_name=experiment_name,load_ground_truth=False)
        self.models=models;self.native_calls=[];self.expense_map={}
        self.user=models.User.find_one(email=self.native.task.supervisor.email)
        password=next(x['password'] for x in self.native.apis.supervisor.show_account_passwords() if x['account_name']=='splitwise')
        self.token=self.native.apis.splitwise.login(username=self.user.email,password=password)['access_token']
        self.members={'SELF':self.user}
        for row in self.data['roommates.csv']:
            who=row['person']
            if who=='SELF':continue
            self.members[who]=models.User.create_save(first_name='Authored',last_name=who,
                email='aw14-'+who.lower()+'@example.com',password='private-native-seed',verified=True)
        self.group=models.Group.create_save(user_id=self.user.id,name='Authored G10',description='AW14 bound expense group')
        for member in self.members.values():
            models.GroupMember.create_save(group_id=self.group.id,user_id=member.id)
        for row in self.state['expenses']:
            expense=models.Expense.create_save(user_id=self.user.id,group_id=self.group.id,
                payer_id=self.members[row['payer']].id,description=row['note'],
                amount=row['amount_cents']/100,deleted=row['deleted'])
            self.expense_map[row['expense']]=expense.id
            for who,amount in row['shares'].items():
                models.ExpenseShare.create_save(expense_id=expense.id,group_id=self.group.id,
                    debtor_id=self.members[who].id,share_amount=amount/100)
        self.baseline=self.native_snapshot()

    def native_snapshot(self):
        return {name:{str(row.id):row.to_dict(keep_computed=False) for row in getattr(self.models,name).all()}
                for name in ['Expense','ExpenseShare','Group','GroupMember']}

    def api(self,name,**kwargs):
        result=getattr(self.native.apis.splitwise,name)(access_token=self.token,**kwargs)
        self.native_calls.append(dict(api=name,arguments=kwargs,result=result))
        return result

    def write(self,name,args):
        if name!='delete_expense':
            self.validate_fields(args)
            if args['group']!=self.data['account_context.json']['group']:
                raise ValueError('No native group binding for requested group')
            if args['payer'] not in self.members or any(k not in self.members for k in args['shares']):
                raise ValueError('No native identity binding')
            values=dict(description=args['note'],paid_amount=args['amount_cents']/100,
                        payer_email=self.members[args['payer']].email,
                        debtor_emails=[self.members[k].email for k in args['shares']],
                        debt_amounts=[n/100 for n in args['shares'].values()])
        if name=='create_expense':
            result=self.api('record_expense',group_id=self.group.id,**values)
            native_id=result['expense_id']
        else:
            native_id=self.expense_map[args['expense']]
            if name=='update_expense':self.api(name,expense_id=native_id,**values)
            else:self.api(name,expense_id=native_id)
        result=super().write(name,args)
        self.expense_map[result['expense']]=native_id
        return result

    def native_checks(self):
        snapshot=self.native_snapshot()
        checks={}
        expected={r['expense']:r for r in self.state['expenses']}
        for identity,row in expected.items():
            native=self.models.Expense.by_id(self.expense_map[identity])
            reverse={v.id:k for k,v in self.members.items()}
            shares={reverse.get(s.debtor_id,'unbound:'+str(s.debtor_id)):
                    round(s.share_amount*100) for s in native.expense_shares}
            checks['effect_'+identity]=(len(native.expense_shares)==len(row['shares']) and native.description==row['note'] and
                round(native.amount*100)==row['amount_cents'] and native.deleted==row['deleted'] and
                native.payer_id==self.members[row['payer']].id and native.group_id==self.group.id and
                shares==row['shares'])
        bound=set(self.expense_map.values())
        for identity,row in self.baseline['Expense'].items():
            if int(identity) not in bound:
                checks['unrelated_expense_'+identity]=snapshot['Expense'].get(identity)==row
        update_ids={self.expense_map[k] for k in self.checker.updates}
        checks['unmodified_shares_preserved']=all(
            row['expense_id'] in update_ids or snapshot['ExpenseShare'].get(identity)==row
            for identity,row in self.baseline['ExpenseShare'].items())
        new_expense_ids={int(k) for k in snapshot['Expense'] if k not in self.baseline['Expense']}
        checks['new_shares_in_mutable_scope']=all(
            identity in self.baseline['ExpenseShare'] or row['expense_id'] in update_ids|new_expense_ids
            for identity,row in snapshot['ExpenseShare'].items())
        checks['group_and_members_preserved']=(snapshot['Group']==self.baseline['Group'] and
                                             snapshot['GroupMember']==self.baseline['GroupMember'])
        checks['no_unmapped_new_expenses']=all(
            k in self.baseline['Expense'] or int(k) in bound for k in snapshot['Expense'])
        # Independently compare actual native expenses to required monthly entries.
        native_rows=[r for r in self.models.Expense.all() if r.group_id==self.group.id and not r.deleted]
        for month,required in self.checker.expected.items():
            matches=[r for r in native_rows if r.description==required['note']]
            good=len(matches)==1
            if good:
                row=matches[0]
                actual={s.debtor_id:round(s.share_amount*100) for s in row.expense_shares}
                wanted={self.members[k].id:v for k,v in required['shares'].items()}
                good=(len(row.expense_shares)==len(wanted) and round(row.amount*100)==required['amount_cents'] and
                      row.payer_id==self.members[required['payer']].id and actual==wanted)
            checks['required_month_'+month]=good
        additions=sum(a['op']=='create' for a in self.checker.target['actions'])
        initial_active=sum(not r['deleted'] for r in self.checker.initial['expenses'])
        checks['exact_group_expense_count']=len(native_rows)==initial_active+additions
        for identity,required in self.checker.updates.items():
            row=self.models.Expense.by_id(self.expense_map[identity])
            wanted={self.members[k].id:v for k,v in required['shares'].items()}
            actual={s.debtor_id:round(s.share_amount*100) for s in row.expense_shares}
            checks['required_update_'+identity]=(not row.deleted and row.description==required['note']
                and round(row.amount*100)==required['amount_cents'] and actual==wanted
                and len(row.expense_shares)==len(wanted) and row.group_id==self.group.id
                and row.payer_id==self.members[required['payer']].id)
        for identity in self.checker.target['protected']:
            nid=str(self.expense_map[identity])
            checks['protected_'+identity]=snapshot['Expense'].get(nid)==self.baseline['Expense'].get(nid)
        return checks
