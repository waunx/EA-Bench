"""AW10 original evaluator controls, strictly separate from authored worlds."""
import json,os,argparse
from pathlib import Path

def run(output):
 from appworld import AppWorld
 from appworld.apps.gmail import models
 output.mkdir(parents=True,exist_ok=True);reports={}
 private=json.loads((Path(os.environ['APPWORLD_ROOT'])/'data/tasks/1b988ac_1/ground_truth/private_data.json').read_text())
 for branch in ['no_op','positive','missing_song']:
  with AppWorld(task_id='1b988ac_1',experiment_name='aw10-original-'+branch) as w:
   calls=[]
   if branch!='no_op':
    user=models.User.find_one(email=w.task.supervisor.email)
    password=next(r['password'] for r in w.apis.supervisor.show_account_passwords() if r['account_name']=='gmail')
    token=w.apis.gmail.login(username=user.email,password=password)['access_token']
    draft=next(d for d in models.Draft.find_all(user_id=user.id) if d.response_to_email_id==private['contact_person_request_email_id'])
    songs=list(private['favorite_song_title_to_artist_names'].items())
    if branch=='missing_song':songs=songs[1:]
    body=private['first_line']+'\n'+'\n'.join('- '+title+' by '+', '.join(artists) for title,artists in songs)+'\n'+private['last_line']
    calls.append(w.apis.gmail.update_draft(access_token=token,draft_id=draft.id,body=body))
    calls.append(w.apis.gmail.send_email_from_draft(access_token=token,draft_id=draft.id))
    w.apis.supervisor.complete_task()
   w.execute('pass');report=w.evaluate().to_dict();reports[branch]=report
   (output/(branch+'.json')).write_text(json.dumps(dict(scope='Original private control; not evaluated solver',native_calls=calls,evaluator=report),indent=2,default=str)+'\n')
 assert reports['positive']['success'] and not reports['no_op']['success'] and not reports['missing_song']['success']
 (output/'result.json').write_text(json.dumps(reports,indent=2,default=str)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output.resolve())
