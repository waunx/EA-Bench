"""AW12 local account/library migration and visible integrity checks."""
from copy import deepcopy
from .packet_interface import PacketInterface,SYSTEM,OUTPUT_FORMAT
from .english_packet import inputs
from .english_aw12 import load,integrity,NeedFact
from .aw12_state import AW12Checker,initial_state
API_FORMATS=dict(list_accounts={},list_tracks={},list_albums={},verify_backup={'file':'backup filename'},create_account={},
    add_song={'account':'account ID','track':'track ID'},add_album={'account':'account ID','album':'album ID'},
    create_playlist={'account':'account ID','name':'playlist name','private':'boolean','tracks':['track ID']},
    update_playlist={'account':'account ID','playlist':'playlist ID','name':'playlist name','private':'boolean','tracks':['track ID']})

class OpenAW12(PacketInterface):
    case='AW12';validation_layer='authored_fixture';api_formats=API_FORMATS;need_fact_error=NeedFact
    fact_labels=dict(batch='Authorized backup',s2_duration='Source recording duration',road_private='Playlist privacy')
    def __init__(self,variant='full',answers=None,ask_handler=None):
        self.variant,self.folder=variant,inputs('AW12',variant);self.data=load(variant)
        self.answers,self.confirmed=deepcopy(answers or {}),{}
        self.state=initial_state(self.data);self.checker=AW12Checker(variant,self.answers,self)
        self.files={p.name:p for p in self.folder.iterdir() if p.is_file()}
        self.events,self.calls,self.effects=[],[],{}
        self.done=False;self.result=None;self.ask_handler=ask_handler
    def call(self,name,args):
        if name not in API_FORMATS:raise ValueError('Unknown API')
        if set(args)!=set(API_FORMATS[name]):raise ValueError('Arguments must match API format')
        if name=='list_accounts':return {'accounts':deepcopy(self.state['accounts'])}
        if name=='list_tracks':return {'tracks':deepcopy(self.data['track_catalog.csv']+self.data.get('recording_search.csv',[]))}
        if name=='list_albums':return {'albums':deepcopy(self.data['albums.csv']+self.data.get('album_search.csv',[]))}
        if name=='verify_backup':
            filename=args['file']
            if filename not in self.data['digests']:raise ValueError('Unknown backup')
            digest=integrity(self.data,filename)
            self.state['migration_events'].append(dict(op=name,file=filename,sha256=digest))
            return dict(file=filename,sha256=digest,delivery_verified=True)
        if name=='create_account':
            identity='AC'+str(1000+len(self.state['accounts']))
            self.state['accounts'][identity]=dict(owner='self',songs=[],albums=[],playlists=[])
            self.state['migration_events'].append(dict(op=name,account=identity));self.calls.append(name)
            return dict(account=identity,owner='self')
        return self.write(name,args)
    def write(self,name,args):
        if not isinstance(args['account'],str) or args['account'] not in self.state['accounts']:raise ValueError('Unknown account')
        account=self.state['accounts'][args['account']]
        if name in {'add_song','add_album'}:
            kind='track' if name=='add_song' else 'album';field='songs' if kind=='track' else 'albums'
            catalog=self.data['track_catalog.csv']+self.data.get('recording_search.csv',[]) if kind=='track' else self.data['albums.csv']+self.data.get('album_search.csv',[])
            if args[kind] not in {r[kind] for r in catalog}:raise ValueError('Unknown catalog ID')
            if args[kind] not in account[field]:
                account[field].append(args[kind]);account[field].sort()
                self.state['migration_events'].append(dict(op=name,**args))
            self.calls.append(name);return dict(account=args['account'],**{kind:args[kind]})
        return self.playlist(name,args,account)
    def playlist(self,name,args,account):
        catalog={r['track'] for r in self.data['track_catalog.csv']+self.data.get('recording_search.csv',[])}
        if not isinstance(args['name'],str) or not args['name'] or type(args['private']) is not bool:raise ValueError('Expected name and privacy flag')
        if not isinstance(args['tracks'],list) or any(not isinstance(t,str) or t not in catalog for t in args['tracks']):raise ValueError('Unknown playlist track')
        if name=='create_playlist':
            identity='PL'+str(1000+sum(len(a['playlists']) for a in self.state['accounts'].values()))
            record=dict(playlist=identity,name=args['name'],private=args['private'],tracks=deepcopy(args['tracks']))
            account['playlists'].append(record)
        else:
            matches=[p for p in account['playlists'] if p['playlist']==args['playlist']]
            if len(matches)!=1:raise ValueError('Unknown playlist')
            identity=args['playlist'];matches[0].update(name=args['name'],private=args['private'],tracks=deepcopy(args['tracks']))
        event=dict(op=name,**deepcopy(args));event['playlist']=identity
        self.state['migration_events'].append(event);self.calls.append(name)
        return dict(account=args['account'],playlist=identity)
