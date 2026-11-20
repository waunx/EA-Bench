"""Original AW14 private reference controls, separate from authored variants."""
import json,os,uuid
from pathlib import Path

def run(output):
    from appworld import AppWorld
    from appworld.apps.splitwise import models
    task='8d42650_1';output=Path(output);output.mkdir(parents=True,exist_ok=False)
    private=json.loads((Path(os.environ['APPWORLD_ROOT'])/'data/tasks'/task/'ground_truth/private_data.json').read_text())
    rows=[]
    for branch in ['no_op','positive','wrong_month']:
        with AppWorld(task_id=task,experiment_name='aw14-original-'+branch+'-'+uuid.uuid4().hex[:8]) as world:
            calls=[]
            if branch!='no_op':
                password=next(r['password'] for r in world.apis.supervisor.show_account_passwords() if r['account_name']=='splitwise')
                token=world.apis.splitwise.login(username=world.task.supervisor.email,password=password)['access_token']
                # Actual original bills are attachments; preserve the original download effect.
                from appworld.apps.gmail import models as gmail
                passwords={r['account_name']:r['password'] for r in world.apis.supervisor.show_account_passwords()}
                mail_token=world.apis.gmail.login(username=world.task.supervisor.email,password=passwords['gmail'])['access_token']
                file_token=world.apis.file_system.login(username=world.task.supervisor.email,password=passwords['file_system'])['access_token']
                mailbox=gmail.User.find_one(email=world.task.supervisor.email)
                for attachment in gmail.Attachment.all():
                    email=gmail.Email.by_id(attachment.email_id) if attachment.email_id else None
                    if email and mailbox.id in email.recipient_ids and 'electric' in (email.subject+' '+email.body).lower():
                        world.apis.gmail.download_attachment(access_token=mail_token,attachment_id=attachment.id,file_system_access_token=file_token,overwrite=True)
                        calls.append(dict(api='gmail.download_attachment',attachment_id=attachment.id))
                emails=[models.User.by_id(i).email for i in private['member_ids']]
                for index,(description,amount) in enumerate(private['expense_description_to_amount'].items()):
                    if branch=='wrong_month' and index==0:description='electricity bill for 04/22'
                    args=dict(description=description,paid_amount=amount,payer_email=world.task.supervisor.email,
                              debtor_emails=emails,group_id=private['group_id'])
                    answer=world.apis.splitwise.record_expense(access_token=token,**args)
                    calls.append(dict(arguments=args,result=answer))
                world.apis.supervisor.complete_task()
            world.execute('pass')
            verdict=world.evaluate().to_dict()
            rows.append(dict(branch=branch,task=task,calls=calls,evaluator=verdict))
            (output/'result.json').write_text(json.dumps(rows,indent=2)+'\n')
            assert verdict['success']==(branch=='positive'),(branch,verdict)
    (output/'result.json').write_text(json.dumps(rows,indent=2)+'\n')
    return rows

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();run(a.out)
