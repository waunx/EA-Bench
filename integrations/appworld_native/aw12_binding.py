"""AW12 actual Spotify signup/library migration with explicit catalog projections."""
import uuid,hashlib,json
from integrations.packet_stages.open_aw12 import OpenAW12
class NativeAW12(OpenAW12):
 def __init__(self,variant='full',answers=None,ask_handler=None,experiment_name=None):
  super().__init__(variant,answers,ask_handler)
  from appworld import AppWorld
  from appworld.apps.spotify import models as m
  from appworld.apps.file_system import models as fs
  from appworld.common.datetime import DateTime
  self.native=AppWorld(task_id='80acbaf_1',experiment_name=experiment_name or 'aw12-'+uuid.uuid4().hex,load_ground_truth=False)
  self.models,self.fs=m,fs;self.native_calls=[];self.song_map={};self.album_map={};self.account_map={};self.playlist_map={};self.tokens={};self.verified=[];self.noops=[];self.native_integrity_timing=True
  for row in self.data['track_catalog.csv']+self.data.get('recording_search.csv',[]):
   song=m.Song.create_save(title='AW12 '+row['track'],duration=int(row['duration']),artist_ids=[],release_date=DateTime.parse('2020-01-01'),genre='Supplemental catalog')
   self.song_map[row['track']]=song.id
  for row in self.data['albums.csv']+self.data.get('album_search.csv',[]):
   album=m.Album.create_save(title='AW12 '+row['album'],artist_ids=[],release_date=DateTime.parse('2020-01-01'),genre='Supplemental catalog');self.album_map[row['album']]=album.id
  for identity,account in self.state['accounts'].items():
   user=m.User.create_save(first_name=identity,last_name='Existing Other Account',email=identity.lower()+'@aw12.example.org',password='AW12Supplemental',verified=True)
   self.account_map[identity]=user.id
   self.tokens[identity]=self.native.apis.spotify.login(username=user.email,password='AW12Supplemental')['access_token']
   for track in account['songs']:m.UserLibrarySong.create_save(user_id=user.id,song_id=self.song_map[track])
   for album in account['albums']:m.UserLibraryAlbum.create_save(user_id=user.id,album_id=self.album_map[album])
   for p in account['playlists']:
    playlist=m.Playlist.create_save(user_id=user.id,title=p['name'],is_public=not p['private']);self.playlist_map[p['playlist']]=playlist.id
    for track in p['tracks']:m.PlaylistSong.create_save(playlist_id=playlist.id,song_id=self.song_map[track])
  fu=fs.User.find_one(email=self.native.task.supervisor.email);self.file_map={}
  for name in self.data['digests']:
   file=fs.File.create_save(user_id=fu.id,path=fu.home_directory_path.rstrip('/')+'/backups/aw12_'+name,content=(self.folder/name).read_bytes().decode())
   self.file_map[name]=file.id
  self.sidecars={}
  password=next(r['password'] for r in self.native.apis.supervisor.show_account_passwords() if r['account_name']=='file_system')
  self.fs_token=self.native.apis.file_system.login(username=fu.email,password=password)['access_token'];self.home=fu.home_directory_path
  self.baseline=self.native_snapshot()
 def native_snapshot(self):
  m=self.models
  tables=[('users',m.User),('songs',m.Song),('albums',m.Album),('library_songs',m.UserLibrarySong),('library_albums',m.UserLibraryAlbum),('playlists',m.Playlist),('playlist_songs',m.PlaylistSong),('files',self.fs.File)]
  return {key:{r.id:r.to_dict(keep_computed=False) for r in model.all()} for key,model in tables}
 def api(self,name,**args):
  reply=getattr(self.native.apis.spotify,name)(**args)
  self.native_calls.append(dict(api='spotify.'+name,arguments={k:v for k,v in args.items() if k not in {'access_token','password','verification_code'}},result=reply));return reply
 def call(self,name,args):
  if name=='verify_backup':
   reply=super().call(name,args);digest=hashlib.sha256(self.fs.File.by_id(self.file_map[args['file']]).content.encode()).hexdigest()
   if digest!=reply['sha256']:raise ValueError('Native backup bytes disagree')
   self.verified.append(args['file']);return reply
  if name=='create_account':
   reply=super().call(name,args);identity=reply['account'];su=self.native.task.supervisor
   self.api('signup',first_name=su.first_name,last_name=su.last_name,email=su.email,password='AW12MigratedAccount')
   user=self.models.User.find_one(email=su.email)
   from appworld.apps.gmail import models as gm
   import re
   gu=gm.User.find_one(email=su.email)
   notification=max((mail for mail in gm.Email.all() if gu.id in mail.recipient_ids and 'Your account verification code is:' in mail.body),key=lambda mail:mail.id)
   code=re.search(r'Your account verification code is: (\S+)',notification.body).group(1)
   self.api('verify_account',email=su.email,verification_code=code)
   self.tokens[identity]=self.native.apis.spotify.login(username=su.email,password='AW12MigratedAccount')['access_token'];self.account_map[identity]=user.id
   return reply
  return super().call(name,args)
 def write(self,name,args):
  before=len(self.state['migration_events']);reply=super().write(name,args)
  if len(self.state['migration_events'])==before:self.noops.append(dict(name=name,args=args));return reply
  self.native_integrity_timing=self.native_integrity_timing and self.checker.batch in self.verified
  token=self.tokens[args['account']]
  if name=='add_song':self.api('add_song_to_library',access_token=token,song_id=self.song_map[args['track']])
  elif name=='add_album':self.api('add_album_to_library',access_token=token,album_id=self.album_map[args['album']])
  else:
   if name=='create_playlist':
    result=self.api('create_playlist',access_token=token,title=args['name'],is_public=not args['private']);native_id=result['playlist_id'];self.playlist_map[reply['playlist']]=native_id
   else:
    native_id=self.playlist_map[args['playlist']];self.api('update_playlist',access_token=token,playlist_id=native_id,title=args['name'],is_public=not args['private'])
    for row in self.models.PlaylistSong.find_all(playlist_id=native_id):self.api('remove_song_from_playlist',access_token=token,playlist_id=native_id,song_id=row.song_id)
   for track in args['tracks']:self.api('add_song_to_playlist',access_token=token,playlist_id=native_id,song_id=self.song_map[track])
   path=self.home.rstrip('/')+'/backups/aw12_playlist_'+str(native_id)+'_order.json'
   payload=dict(playlist_id=native_id,name=args['name'],private=args['private'],ordered_song_ids=[self.song_map[t] for t in args['tracks']],verified_backup_sha256={n:self.data['digests'][n] for n in self.verified},scope='Ordered migration record; native Spotify display order is catalog order')
   content=json.dumps(payload,sort_keys=True)
   reply_file=self.native.apis.file_system.create_file(access_token=self.fs_token,file_path=path,content=content,overwrite=True)
   self.native_calls.append(dict(api='file_system.create_file',arguments=dict(file_path=path,content=content,overwrite=True),result=reply_file))
   self.sidecars[native_id]=path
  return reply
 def native_checks(self):
  s,b=self.native_snapshot(),self.baseline;new=set(s['users'])-set(b['users']);user_id=next(iter(new)) if len(new)==1 else None;t=self.checker.target
  songs=sorted(r['song_id'] for r in s['library_songs'].values() if r['user_id']==user_id)
  albums=sorted(r['album_id'] for r in s['library_albums'].values() if r['user_id']==user_id)
  playlists=[]
  for p in s['playlists'].values():
   if p['user_id']!=user_id:continue
   tracks=[r['song_id'] for _,r in sorted(s['playlist_songs'].items()) if r['playlist_id']==p['id']]
   playlists.append(dict(name=p['title'],private=not p['is_public'],tracks=tracks))
  api_playlists=[]
  if user_id:
   identity=next(k for k,v in self.account_map.items() if v==user_id)
   for p in s['playlists'].values():
    if p['user_id']==user_id:
     row=self.api('show_playlist',access_token=self.tokens[identity],playlist_id=p['id']);api_playlists.append(dict(name=row['title'],private=not row['is_public'],tracks=[song['id'] for song in row['songs']]))
  expected=[dict(p,tracks=[self.song_map[i] for i in p['tracks']]) for p in t['playlists']]
  sidecars=[];sidecar_provenance=True
  for native_id,path in self.sidecars.items():
   result=self.native.apis.file_system.show_file(access_token=self.fs_token,file_path=path)
   self.native_calls.append(dict(api='file_system.show_file',arguments=dict(file_path=path),result=result))
   payload=json.loads(result['content']);sidecar_provenance=sidecar_provenance and payload['playlist_id']==native_id and payload['verified_backup_sha256'].get(self.checker.batch)==self.data['digests'][self.checker.batch] and all(self.data['digests'].get(n)==h for n,h in payload['verified_backup_sha256'].items());sidecars.append(dict(name=payload['name'],private=payload['private'],tracks=payload['ordered_song_ids']))
  def membership(rows):return sorted([dict(r,tracks=sorted(r['tracks'])) for r in rows],key=lambda r:r['name'])
  return dict(sidecar_source_provenance=sidecar_provenance,only_expected_sidecar_files={r['path'] for i,r in s['files'].items() if i not in b['files']}==set(self.sidecars.values()),native_api_membership_privacy_exact=membership(api_playlists)==membership(expected),durable_order_record_exact=sorted(sidecars,key=lambda p:p['name'])==sorted(expected,key=lambda p:p['name']),native_integrity_timing=self.native_integrity_timing and self.checker.batch in self.verified,native_durations_exact=all(self.models.Song.by_id(self.song_map[r['track']]).duration==int(r['duration']) for r in self.data['track_catalog.csv']+self.data.get('recording_search.csv',[])),one_new_user=len(new)==1,new_user_identity=bool(user_id) and s['users'][user_id]['email']==self.native.task.supervisor.email,new_user_verified=bool(user_id) and s['users'][user_id]['verified'],exact_song_library=songs==sorted(self.song_map[i] for i in t['songs']),exact_album_library=albums==sorted(self.album_map[i] for i in t['albums']),supplemental_insertion_order_and_privacy=sorted(playlists,key=lambda p:p['name'])==sorted(expected,key=lambda p:p['name']),old_records_preserved=all(all(s[k].get(i)==r for i,r in b[k].items()) for k in s),no_unexpected_library_owners=all(r['user_id']==user_id for k in ['library_songs','library_albums','playlists'] for i,r in s[k].items() if i not in b[k]),backup_native_bytes_exact=all(hashlib.sha256(self.fs.File.by_id(self.file_map[n]).content.encode()).hexdigest()==h for n,h in self.data['digests'].items()),source_catalog_unchanged=s['songs']==b['songs'] and s['albums']==b['albums'])
