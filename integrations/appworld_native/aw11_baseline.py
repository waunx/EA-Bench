"""AW11 official original evaluator controls, independent from authored seed."""
import argparse,json,os
from pathlib import Path

def run(output):
 from appworld import AppWorld
 from appworld.apps.spotify import models
 output.mkdir(parents=True,exist_ok=True);reports={}
 private=json.loads((Path(os.environ['APPWORLD_ROOT'])/'data/tasks/9a16324_1/ground_truth/private_data.json').read_text())
 for branch in ['no_op','positive','missing_artist']:
  with AppWorld(task_id='9a16324_1',experiment_name='aw11-original-'+branch) as w:
   calls=[]
   if branch!='no_op':
    user=models.User.find_one(email=w.task.supervisor.email)
    password=next(r['password'] for r in w.apis.supervisor.show_account_passwords() if r['account_name']=='spotify')
    token=w.apis.spotify.login(username=user.email,password=password)['access_token']
    artists=sorted(set(private['coworkers_artist_ids']+private['friends_artist_ids'])-{r.artist_id for r in models.UserArtistFollowing.find_all(user_id=user.id)})
    if branch=='missing_artist':artists=artists[1:]
    for identity in artists:
     result=w.apis.spotify.follow_artist(access_token=token,artist_id=identity);calls.append(dict(api='spotify.follow_artist',artist_id=identity,result=result))
    w.apis.supervisor.complete_task()
   w.execute('pass');reports[branch]=w.evaluate().to_dict()
   (output/(branch+'.json')).write_text(json.dumps(dict(scope='Original private evaluator control, not solver',native_calls=calls,evaluator=reports[branch]),indent=2,default=str)+'\n')
 assert reports['positive']['success'] and not reports['no_op']['success'] and not reports['missing_artist']['success']
 (output/'result.json').write_text(json.dumps(reports,indent=2,default=str)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output.resolve())
