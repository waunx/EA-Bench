"""AW12 original migration evaluator controls; separate from supplemental seeds."""
import argparse,json,os,re
from pathlib import Path

def run(output):
 from appworld import AppWorld
 from appworld.apps.gmail import models as gm
 output.mkdir(parents=True,exist_ok=True);reports={}
 private=json.loads((Path(os.environ['APPWORLD_ROOT'])/'data/tasks/80acbaf_1/ground_truth/private_data.json').read_text())
 for branch in ['no_op','positive','missing_song']:
  with AppWorld(task_id='80acbaf_1',experiment_name='aw12-original-'+branch) as w:
   calls=[]
   def call(name,**args):
    result=getattr(w.apis.spotify,name)(**args);calls.append(dict(api='spotify.'+name,arguments={k:v for k,v in args.items() if k not in {'password','access_token','verification_code'}},result=result));return result
   if branch!='no_op':
    su=w.task.supervisor;call('signup',first_name=su.first_name,last_name=su.last_name,email=su.email,password='AW12Baseline')
    user=gm.User.find_one(email=su.email)
    email=max((e for e in gm.Email.all() if user.id in e.recipient_ids and 'Your account verification code is:' in e.body),key=lambda e:e.id)
    code=re.search(r'Your account verification code is: (\S+)',email.body).group(1)
    call('verify_account',email=su.email,verification_code=code)
    token=w.apis.spotify.login(username=su.email,password='AW12Baseline')['access_token']
    songs=private['song_library_song_ids']
    if branch=='missing_song':songs=songs[1:]
    for song in songs:call('add_song_to_library',access_token=token,song_id=song)
    for album in private['album_library_album_ids']:call('add_album_to_library',access_token=token,album_id=album)
    for title,songs in private['playlist_name_to_song_ids'].items():
     playlist=call('create_playlist',access_token=token,title=title,is_public=False)['playlist_id']
     for song in songs:call('add_song_to_playlist',access_token=token,playlist_id=playlist,song_id=song)
    w.apis.supervisor.complete_task()
   w.execute('pass');reports[branch]=w.evaluate().to_dict()
   (output/(branch+'.json')).write_text(json.dumps(dict(scope='Original private evaluator control, not solver',native_calls=calls,evaluator=reports[branch]),indent=2,default=str)+'\n')
 assert reports['positive']['success'] and not reports['no_op']['success'] and not reports['missing_song']['success']
 (output/'result.json').write_text(json.dumps(reports,indent=2,default=str)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output.resolve())
