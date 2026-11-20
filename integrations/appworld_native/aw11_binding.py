"""AW11 actual Spotify follow mutations with bound recommendation sources."""
import uuid
from integrations.packet_stages.open_aw11 import OpenAW11
class NativeAW11(OpenAW11):
 def __init__(self,variant='full',answers=None,ask_handler=None,experiment_name=None):
  super().__init__(variant,answers,ask_handler)
  from appworld import AppWorld
  from appworld.apps.spotify import models
  self.native=AppWorld(task_id='9a16324_1',experiment_name=experiment_name or 'aw11-'+uuid.uuid4().hex,load_ground_truth=False)
  self.models=models;self.native_calls=[];self.artist_map={};self.noop_actions=[]
  self.user=models.User.find_one(email=self.native.task.supervisor.email)
  password=next(r['password'] for r in self.native.apis.supervisor.show_account_passwords() if r['account_name']=='spotify')
  self.token=self.native.apis.spotify.login(username=self.user.email,password=password)['access_token']
  for row in self.data['artist_catalog.csv']+self.data.get('extra_artists.csv',[]):
   artist=models.Artist.create_save(name=row['name'],genre='Authored recommendation catalog');self.artist_map[row['artist']]=artist.id
  for identity in self.state['following']:models.UserArtistFollowing.create_save(user_id=self.user.id,artist_id=self.artist_map[identity])
  self.seed_messages();self.baseline=self.native_snapshot()
 def seed_messages(self):
  from appworld.apps.gmail import models as gm
  from appworld.apps.phone import models as pm
  self.gmail,self.phone=gm,pm;self.message_bindings=[];self.sender_map={}
  guser=gm.User.find_one(email=self.user.email);puser=pm.User.find_one(phone_number=self.native.task.supervisor.phone_number)
  for i,row in enumerate(self.data['roster.csv']):
   sender=row['sender'];g=gm.User.create_save(first_name=sender,last_name='Supplemental',email=sender.lower()+'@aw11.example.org',password='AW11Supplemental')
   p=pm.User.create_save(first_name=sender,last_name='Supplemental',phone_number='+155500011'+str(i).zfill(2),password='AW11Supplemental')
   self.sender_map[sender]=dict(gmail=g.id,phone=p.id,relationship=row['relationship'])
  for row in self.data['recommendations.csv']+self.data.get('extra_recommendations.csv',[])+self.data.get('music_promotion.csv',[]):
   sender=self.sender_map[row['sender']]
   if row['channel']=='email':
    record=gm.Email.create_save(sender_id=sender['gmail'],recipient_ids=[guser.id],subject='Music recommendations',body=row['text']);table='gmail.Email'
   else:
    record=pm.GlobalTextMessage.create_save(sender_id=sender['phone'],receiver_id=puser.id,message=row['text'])
    pm.UserTextMessage.create_save(global_text_message_id=record.id,user_id=puser.id);table='phone.GlobalTextMessage'
   self.message_bindings.append(dict(message=row['message'],native_table=table,native_id=record.id,text=row['text'],sender=row['sender']))
 def native_snapshot(self):
  models=[('following',self.models.UserArtistFollowing),('artists',self.models.Artist),('emails',self.gmail.Email),('sms',self.phone.GlobalTextMessage),('user_sms',self.phone.UserTextMessage)]
  return {key:{r.id:r.to_dict(keep_computed=False) for r in model.all()} for key,model in models}
 def write(self,name,args):
  before=set(self.state['following']);reply=super().write(name,args)
  if before==set(self.state['following']):self.noop_actions.append(dict(name=name,arguments=args));return reply
  kwargs=dict(access_token=self.token,artist_id=self.artist_map[args['artist']]);result=getattr(self.native.apis.spotify,name)(**kwargs)
  self.native_calls.append(dict(api='spotify.'+name,arguments={'artist_id':kwargs['artist_id']},result=result));return reply
 def native_checks(self):
  s,b=self.native_snapshot(),self.baseline;added=set(s['following'])-set(b['following']);deleted=set(b['following'])-set(s['following'])
  actual={(s['following'][i]['user_id'],s['following'][i]['artist_id']) for i in added}
  expected={(self.user.id,self.artist_map[i]) for i in self.checker.target['add']}
  return dict(exact_new_follows=actual==expected and len(added)==len(expected),no_deleted_follows=not deleted,old_follows_preserved=all(s['following'].get(k)==v for k,v in b['following'].items()),source_records_preserved=all(s[k]==b[k] for k in ['artists','emails','sms','user_sms']),no_unfollow_effects=not any(r['api']=='spotify.unfollow_artist' for r in self.native_calls),catalog_binding_exact=all(self.models.Artist.by_id(self.artist_map[r['artist']]).name==r['name'] for r in self.data['artist_catalog.csv']+self.data.get('extra_artists.csv',[])))
