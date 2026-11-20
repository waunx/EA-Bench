"""AW10 actual Gmail effects on explicitly authored supplemental seed."""
import uuid
from integrations.packet_stages.open_aw10 import OpenAW10
class NativeAW10(OpenAW10):
 def __init__(self,variant='full',answers=None,ask_handler=None,experiment_name=None):
  super().__init__(variant,answers,ask_handler)
  from appworld import AppWorld
  from appworld.apps.gmail import models
  self.native=AppWorld(task_id='1b988ac_1',experiment_name=experiment_name or 'aw10-'+uuid.uuid4().hex,load_ground_truth=False)
  self.models=models;self.native_calls=[]
  self.user=models.User.find_one(email=self.native.task.supervisor.email)
  password=next(r['password'] for r in self.native.apis.supervisor.show_account_passwords() if r['account_name']=='gmail')
  self.token=self.native.apis.gmail.login(username=self.user.email,password=password)['access_token']
  self.recipient=models.User.find_one(email='katie@example.org')
  if not self.recipient:
   template=models.User.all()[0].to_dict(keep_computed=False);template.pop('id');template.update(email='katie@example.org',first_name='Katie',last_name='Recipient',password='AW10Supplemental')
   self.recipient=models.User.create_save(**template)
  subject,body=self.parts(self.data['mail_draft.eml'])
  rt=self.native.apis.gmail.login(username=self.recipient.email,password='AW10Supplemental')['access_token']
  request=self.native.apis.gmail.send_email(access_token=rt,email_addresses=[self.user.email],subject=subject,body='Please send me your song recommendations.')
  self.request_id=request['sent_email_id']
  self.thread=models.UserEmailThread.find_one(user_id=self.user.id,email_ids__has=self.request_id)
  self.global_thread_id=self.thread.global_email_thread_id
  self.draft_id=self.native.apis.gmail.create_draft(access_token=self.token,recipient_email_addresses=[self.recipient.email],body=body,belongs_to_email_thread_id=self.thread.id,response_to_email_id=self.request_id)['draft_id']
  self.seed_music()
  self.baseline=self.native_snapshot()
 @staticmethod
 def parts(message):
  headers,body=message.split('\n\n',1)
  return next(s[9:] for s in headers.splitlines() if s.startswith('Subject: ')),body
 def native_snapshot(self):
  return {key:{r.id:r.to_dict(keep_computed=False) for r in model.all()} for key,model in [('emails',self.models.Email),('drafts',self.models.Draft),('threads',self.models.UserEmailThread),('global_threads',self.models.GlobalEmailThread),('songs',self.spotify.Song),('likes',self.spotify.SongLike),('library',self.spotify.UserLibrarySong)]}
 def write(self,name,args):
  result=super().write(name,args)
  kwargs=dict(access_token=self.token,draft_id=self.draft_id)
  if name=='update_draft':
   subject,body=self.parts(args['message']);api='update_draft';kwargs.update(body=body,email_addresses=[next(line[4:] for line in args['message'].split('\n\n',1)[0].splitlines() if line.startswith('To: '))])
  else:api='send_email_from_draft'
  reply=getattr(self.native.apis.gmail,api)(**kwargs)
  self.native_calls.append(dict(api='gmail.'+api,arguments={k:v for k,v in kwargs.items() if k!='access_token'},result=reply))
  return result
 def native_checks(self):
  s,b=self.native_snapshot(),self.baseline;new=set(s['emails'])-set(b['emails']);mail=s['emails'][next(iter(new))] if len(new)==1 else None
  subject,body=self.parts(self.checker.target['message'])
  checks=dict(one_email=len(new)==1,email_body_exact=bool(mail) and mail['body']==body,email_subject_exact=bool(mail) and mail['subject']=='Re: '+subject,recipient_exact=bool(mail) and mail['recipient_ids']==[self.recipient.id],sender_exact=bool(mail) and mail['sender_id']==self.user.id,draft_consumed=self.draft_id not in s['drafts'],old_emails_preserved=all(s['emails'].get(k)==v for k,v in b['emails'].items()),other_drafts_preserved=s['drafts']=={k:v for k,v in b['drafts'].items() if k!=self.draft_id})

  checks['reply_to_request']=bool(mail) and mail['response_to_email_id']==self.request_id
  checks['same_thread_ids']=set(s['threads'])==set(b['threads']) and set(s['global_threads'])==set(b['global_threads'])
  sent_id=next(iter(new)) if len(new)==1 else None
  checks['global_thread_messages_exact']=self.models.GlobalEmailThread.by_id(self.global_thread_id).email_ids==[self.request_id,sent_id]
  affected={i for i,r in b['threads'].items() if r['global_email_thread_id']==self.global_thread_id}
  checks['participant_threads_exact']=all(s['threads'][i]['email_ids']==[self.request_id,sent_id] for i in affected)
  checks['other_threads_preserved']=all(s['threads'].get(i)==r for i,r in b['threads'].items() if i not in affected) and all(s['global_threads'].get(i)==r for i,r in b['global_threads'].items() if i!=self.global_thread_id)
  checks['catalog_projection_exact']=all(self.spotify.Song.by_id(r['native_song_id']).title==r['title'] and self.spotify.Song.by_id(r['native_song_id']).release_date.year==r['release_year'] for r in self.source_bindings)
  checks['music_preserved']=all(s[k]==b[k] for k in ['songs','likes','library'])
  return checks
 def seed_music(self):
  from appworld.apps.spotify import models as m
  from appworld.common.datetime import DateTime
  from integrations.packet_stages.english_aw10 import fact
  self.spotify=m;self.song_map={};self.isrc_projection={};self.source_bindings=[]
  user=m.User.find_one(email=self.user.email)
  guest=next(u for u in m.User.all() if u.id!=user.id)
  for row in self.data['songs.csv']+self.data.get('catalog_search.csv',[]):
   song=m.Song.create_save(title=row['title'],artist_ids=[],duration=180,release_date=DateTime.parse(row['year']+'-01-01'),genre='Supplemental')
   self.song_map[row['track']]=song.id
   self.source_bindings.append(dict(authored_track=row['track'],native_song_id=song.id,title=row['title'],release_year=int(row['year'])))
   self.isrc_projection[song.id]=fact(self.data,'t2_isrc',self.answers) if row['track']=='T2' else row['isrc']
  seen=set()
  for row in self.data['library.csv']+self.data.get('guest_library.csv',[])+self.data.get('library_copy.csv',[]):
   pair=(user.id if row.get('account','self')=='self' else guest.id,self.song_map[row['track']])
   if pair not in seen:m.UserLibrarySong.create_save(user_id=pair[0],song_id=pair[1]);seen.add(pair)
  for row in self.data['liked.csv']:
   active=fact(self.data,'harbor_liked',self.answers) if row['track']=='T6' else row['active']=='1'
   if active:m.SongLike.create_save(user_id=user.id,song_id=self.song_map[row['track']])
