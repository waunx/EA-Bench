"""AW10 authored music reads and email edit/send operations."""
from copy import deepcopy
from .packet_interface import PacketInterface,SYSTEM,OUTPUT_FORMAT
from .english_packet import inputs
from .english_aw10 import load,NeedFact
from .aw10_state import initial_state,AW10Checker

API_FORMATS=dict(list_songs={},list_likes={},list_library={},list_drafts={},
    update_draft={'draft_id':'draft ID','message':'complete email text'},send_draft={'draft_id':'draft ID'})

class OpenAW10(PacketInterface):
    case='AW10';validation_layer='authored_fixture';api_formats=API_FORMATS;need_fact_error=NeedFact
    fact_labels=dict(merge='Edition merging preference',harbor_liked='Current like status',t2_isrc='Recording identity')

    def __init__(self,variant='full',answers=None,ask_handler=None):
        self.variant,self.folder=variant,inputs('AW10',variant);self.data=load(variant)
        self.answers,self.confirmed=deepcopy(answers or {}),{}
        self.state=initial_state(self.data);self.checker=AW10Checker(variant,self.answers,self)
        self.files={p.name:p for p in self.folder.iterdir() if p.is_file()}
        self.events,self.calls,self.effects=[],[],{};self.done=False;self.result=None;self.ask_handler=ask_handler

    def call(self,name,arguments):
        if name not in API_FORMATS:raise ValueError('Unknown API')
        if name in {'update_draft','send_draft'}:return self.write(name,arguments)
        if arguments:raise ValueError('This API takes no arguments')
        if name=='list_songs':return {'songs':deepcopy(self.data['songs.csv']+self.data.get('catalog_search.csv',[]))}
        if name=='list_likes':return {'likes':deepcopy(self.data['liked.csv'])}
        if name=='list_library':return {'library':deepcopy(self.data['library.csv']+self.data.get('guest_library.csv',[])+self.data.get('library_copy.csv',[]))}
        return {'drafts':[dict(draft_id=k,message=v) for k,v in self.state['drafts'].items()]}

    def write(self,name,args):
        if set(args)!=set(API_FORMATS[name]) or any(not isinstance(v,str) for v in args.values()):
            raise ValueError('Expected string arguments matching API format')
        identity=args['draft_id']
        if identity not in self.state['drafts']:raise ValueError('Unknown draft')
        if name=='update_draft':
            self.state['drafts'][identity]=args['message']
            self.state['mail_events'].append(dict(op='update',**args))
        else:
            self.state['sent'].append(dict(draft_id=identity,message=self.state['drafts'].pop(identity)))
            self.state['mail_events'].append(dict(op='send',draft_id=identity))
        self.calls.append(name)
        return dict(draft_id=identity,status='updated' if name=='update_draft' else 'sent')
