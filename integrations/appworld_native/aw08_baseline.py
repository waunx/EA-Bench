"""AW08 original fixed-world author reference, not a solver episode."""
import json,os,uuid
from pathlib import Path

def run(output):
    from appworld import AppWorld
    from appworld.apps.venmo import models
    task='a676f2a_1';output=Path(output);output.mkdir(parents=True,exist_ok=False)
    data=json.loads((Path(os.environ['APPWORLD_ROOT'])/'data/tasks'/task/'ground_truth/private_data.json').read_text())
    targets=data['coworker_venmo_user_id_to_total_cost'];rows=[]
    for branch in ['no_op','positive','private_request']:
        with AppWorld(task_id=task,experiment_name='aw08-original-'+branch+'-'+uuid.uuid4().hex[:8]) as world:
            calls=[]
            if branch!='no_op':
                password=next(r['password'] for r in world.apis.supervisor.show_account_passwords() if r['account_name']=='venmo')
                token=world.apis.venmo.login(username=world.task.supervisor.email,password=password)['access_token']
                for identity,amount in targets.items():
                    person=models.User.by_id(int(identity.split(':')[-1]))
                    args=dict(user_email=person.email,amount=amount,description='Lunch Meeting Order',private=branch=='private_request')
                    answer=world.apis.venmo.create_payment_request(access_token=token,**args)
                    calls.append(dict(arguments=args,result=answer))
                world.apis.supervisor.complete_task()
            world.execute('pass');verdict=world.evaluate().to_dict()
            rows.append(dict(branch=branch,task=task,calls=calls,evaluator=verdict))
            (output/'result.json').write_text(json.dumps(rows,indent=2)+'\n')
            assert verdict['success']==(branch=='positive'),(branch,verdict)
    return rows

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();run(a.out)
