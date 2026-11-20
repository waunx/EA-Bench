"""AW11 artist-follow environment with private-state-independent reads."""
from copy import deepcopy
from .packet_interface import PacketInterface,SYSTEM,OUTPUT_FORMAT
from .english_packet import inputs
from .english_aw11 import load,NeedFact
from .aw11_state import AW11Checker,initial_state
API_FORMATS=dict(list_artists={},list_recommendations={},list_roster={},list_following={},
                 follow_artist={'artist':'artist ID'},unfollow_artist={'artist':'artist ID'})

class OpenAW11(PacketInterface):
    case='AW11';validation_layer='authored_fixture';api_formats=API_FORMATS;need_fact_error=NeedFact
    fact_labels=dict(alex='Recommended artist identity',p3_scope='Current relationship scope',a2_followed='Current follow status')
    def __init__(self,variant='full',answers=None,ask_handler=None):
        self.variant,self.folder=variant,inputs('AW11',variant);self.data=load(variant)
        self.answers,self.confirmed=deepcopy(answers or {}),{}
        self.state=initial_state(self.data,self.answers);self.checker=AW11Checker(variant,self.answers,self)
        self.files={p.name:p for p in self.folder.iterdir() if p.is_file()}
        self.events,self.calls,self.effects=[],[],{};self.done=False;self.result=None;self.ask_handler=ask_handler
        self.public_states={}
    def call(self,name,args):
        if name not in API_FORMATS:raise ValueError('Unknown API')
        if name in {'follow_artist','unfollow_artist'}:return self.write(name,args)
        if args:raise ValueError('This API takes no arguments')
        if name=='list_artists':return {'artists':deepcopy(self.data['artist_catalog.csv']+self.data.get('extra_artists.csv',[]))}
        if name=='list_recommendations':return {'messages':deepcopy(self.data['recommendations.csv']+self.data.get('extra_recommendations.csv',[])+self.data.get('music_promotion.csv',[]))}
        if name=='list_roster':return {'roster':deepcopy(self.data['roster.csv'])}
        rows=deepcopy(self.data['following.csv']);known={r['artist'] for r in rows}
        for r in rows:
            if r['artist'] in self.public_states:r['active']=self.public_states[r['artist']]
        rows += [dict(artist=k,active=v) for k,v in self.public_states.items() if k not in known]
        return {'following':rows,'additional_records':deepcopy(self.data.get('following_copy.csv',[]))}
    def write(self,name,args):
        if set(args)!={'artist'} or not isinstance(args['artist'],str):raise ValueError('Expected artist ID')
        artist=args['artist'];catalog=self.data['artist_catalog.csv']+self.data.get('extra_artists.csv',[])
        if artist not in {r['artist'] for r in catalog}:raise ValueError('Unknown artist')
        current=set(self.state['following']);op='follow' if name=='follow_artist' else 'unfollow'
        if (op=='follow')!=(artist in current):
            if op=='follow':current.add(artist)
            else:current.remove(artist)
            self.state['follow_events'].append(dict(op=op,artist=artist))
        self.state['following']=sorted(current);self.public_states[artist]='1' if op=='follow' else '0'
        self.calls.append(name)
        return dict(artist=artist,active=op=='follow')
