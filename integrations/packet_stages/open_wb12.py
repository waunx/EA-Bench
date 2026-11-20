"""WB12 authored CRM deletion and email effects; no real external writes."""
from copy import deepcopy
from .packet_interface import PacketInterface,SYSTEM,OUTPUT_FORMAT
from .english_packet import inputs
from .english_wb12 import load,NeedFact,raw_records
from .wb12_state import WB12Checker,initial_state
API_FORMATS=dict(get_context={},list_samples={},list_records={},list_aliases={},list_people={},
    delete_record={'id':'CRM record ID'},send_email={'to':'email address','subject':'subject string','body':'body string'})
class OpenWB12(PacketInterface):
    case='WB12';validation_layer='authored_fixture';api_formats=API_FORMATS;need_fact_error=NeedFact
    fact_labels=dict(measurement='Sample quality classification',l2_owner='Current record owner',l5_deleted='Current deletion state')
    def __init__(self,variant='full',answers=None,ask_handler=None):
        self.variant,self.folder=variant,inputs('WB12',variant);self.data=load(variant)
        self.answers,self.confirmed=deepcopy(answers or {}),{}
        self.state=initial_state(self.data,self.answers);self.checker=WB12Checker(variant,self.answers,self)
        self.files={p.name:p for p in self.folder.iterdir() if p.is_file()}
        self.events,self.calls,self.effects=[],[],{};self.public_deleted=set()
        self.done=False;self.result=None;self.ask_handler=ask_handler
    def call(self,name,args):
        if name not in API_FORMATS:raise ValueError('Unknown API')
        if set(args)!=set(API_FORMATS[name]):raise ValueError('Arguments must match API format')
        if name=='get_context':return deepcopy(self.data['operation_context.json'])
        if name=='list_samples':return {'samples':deepcopy(self.data['engaged_users.csv']+self.data.get('gap_fill_samples.csv',[]))}
        if name=='list_aliases':return {'aliases':deepcopy(self.data['owner_aliases.csv'])}
        if name=='list_people':return {'people':deepcopy(self.data['people.json'])}
        if name=='list_records':
            raw={r['id']:r for r in raw_records(self.data)};rows=deepcopy(self.state['records'])
            for row in rows:
                if raw[row['id']]['owner']=='':row['owner']=None
                if raw[row['id']]['deleted']=='' and row['id'] not in self.public_deleted:row['deleted']=None
            return {'records':rows}
        if name=='delete_record':
            if not isinstance(args['id'],str):raise ValueError('Expected record ID')
            matches=[r for r in self.state['records'] if r['id']==args['id']]
            if len(matches)!=1:raise ValueError('Unknown record')
            row=matches[0]
            if not row['deleted']:
                row['deleted']=True;self.state['effect_events'].append(dict(op='delete',id=row['id']))
            self.public_deleted.add(row['id']);self.calls.append(name)
            return dict(id=row['id'],deleted=True)
        if any(not isinstance(v,str) or not v for v in args.values()) or '@' not in args['to']:raise ValueError('Expected email address, subject and body')
        message=dict(message_id='MSG'+str(1000+len(self.state['sent'])),**deepcopy(args))
        self.state['sent'].append(message);self.state['effect_events'].append(dict(op='send',message=deepcopy(message)));self.calls.append(name)
        return dict(message_id=message['message_id'],status='sent')
