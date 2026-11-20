"""WB01 visible contact/calendar data and local calendar invitations."""
from copy import deepcopy
from .packet_interface import PacketInterface,SYSTEM,OUTPUT_FORMAT
from .english_packet import inputs
from .english_wb01 import load,NeedFact
from .wb01_state import WB01Checker,initial_state,calendar
API_FORMATS=dict(list_customers={},list_contacts={},list_assignments={},list_calendar={},get_context={},
    create_event={'owner':'calendar owner','day':'YYYY-MM-DD','start':'minute of day','end':'minute of day','title':'event title','attendees':['email address']})
class OpenWB01(PacketInterface):
    case='WB01';validation_layer='authored_fixture';api_formats=API_FORMATS;need_fact_error=NeedFact
    fact_labels=dict(connected='Actual call connection',busy_end='Appointment ending time',handover='Assignment handover date')
    def __init__(self,variant='full',answers=None,ask_handler=None):
        self.variant,self.folder=variant,inputs('WB01',variant);self.data=load(variant)
        self.answers,self.confirmed=deepcopy(answers or {}),{}
        self.state=initial_state(self.data,self.answers);self.checker=WB01Checker(variant,self.answers,self)
        self.files={p.name:p for p in self.folder.iterdir() if p.is_file()}
        self.events,self.calls,self.effects=[],[],{}
        self.done=False;self.result=None;self.ask_handler=ask_handler
    def call(self,name,args):
        if name not in API_FORMATS:raise ValueError('Unknown API')
        if set(args)!=set(API_FORMATS[name]):raise ValueError('Arguments must match API format')
        if name=='get_context':return deepcopy(self.data['calendar_context.json'])
        if name=='list_customers':return {'customers':deepcopy(self.data['customer_directory.csv'])}
        if name=='list_contacts':return {'contacts':deepcopy(self.data['contact_events.csv']+self.data.get('campaign_events.csv',[]))}
        if name=='list_assignments':return {'assignments':deepcopy(self.data['owner_history.csv']+self.data.get('owner_archive.csv',[]))}
        if name=='list_calendar':
            public=calendar(self.data);old={r['event'] for r in public}
            return {'events':public+[deepcopy(r) for r in self.state['calendar'] if r['event'] not in old]}
        from datetime import date
        if any(not isinstance(args[k],str) for k in ['owner','day','title']):raise ValueError('Expected string fields')
        date.fromisoformat(args['day'])
        if any(type(args[k]) is not int for k in ['start','end']) or not 0<=args['start']<args['end']<=1440:raise ValueError('Invalid minute interval')
        if not isinstance(args['attendees'],list) or any(not isinstance(x,str) or '@' not in x for x in args['attendees']):raise ValueError('Invalid attendee addresses')
        identity='EV'+str(1000+len(self.state['calendar']));record=dict(event=identity,**deepcopy(args))
        self.state['calendar'].append(record)
        self.state['invitations'] += [dict(event=identity,to=person,day=args['day'],start=args['start'],end=args['end'],title=args['title']) for person in args['attendees']]
        self.state['calendar_events'].append(dict(op='create_event',record=deepcopy(record)));self.calls.append(name)
        return dict(event=identity,status='created')
