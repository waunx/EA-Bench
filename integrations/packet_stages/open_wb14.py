"""WB14 authored task, calendar, email and CRM operations."""
from copy import deepcopy
from datetime import date
from .packet_interface import PacketInterface,SYSTEM,OUTPUT_FORMAT
from .english_packet import inputs
from .english_wb14 import load,NeedFact
from .wb14_state import WB14Checker,initial_state,calendar
API_FORMATS=dict(get_context={},list_visits={},list_contacts={},list_boards={},list_calendar={},list_crm={},list_aliases={},
    create_task={'board':'board ID','owner':'contact ID or email','title':'task title','list':'list name','due':'YYYY-MM-DD'},
    create_event={'owner':'calendar owner','day':'YYYY-MM-DD','start':'minute of day','end':'minute of day','title':'event title','attendees':['email address']},
    send_email={'to':'email address','subject':'subject string','body':'body string'},
    transfer_record={'id':'CRM record ID','owner':'contact ID or email'})
class OpenWB14(PacketInterface):
    case='WB14';validation_layer='authored_fixture';api_formats=API_FORMATS;need_fact_error=NeedFact
    fact_labels=dict(qa='Backfill acceptance',busy_end='Appointment end',calendar_state='Appointment status',recipient='Target contact',workspace='Target workspace',lead_state='Current CRM deletion flag')
    def __init__(self,variant='full',answers=None,ask_handler=None):
        self.variant,self.folder=variant,inputs('WB14',variant);self.data=load(variant)
        self.answers,self.confirmed=deepcopy(answers or {}),{}
        self.state=initial_state(self.data,self.answers);self.checker=WB14Checker(variant,self.answers,self)
        self.files={p.name:p for p in self.folder.iterdir() if p.is_file()}
        self.events,self.calls,self.effects=[],[],{}
        self.done=False;self.result=None;self.ask_handler=ask_handler
    def call(self,name,args):
        if name not in API_FORMATS:raise ValueError('Unknown API')
        if set(args)!=set(API_FORMATS[name]):raise ValueError('Arguments must match API format')
        if name=='get_context':return deepcopy(self.data['operation_context.json'])
        if name=='list_visits':return {'visits':deepcopy(self.data['visits.csv']+self.data.get('visits_history.csv',[]))}
        if name=='list_contacts':return {'contacts':deepcopy(self.data['contacts.csv'])}
        if name=='list_boards':return {'boards':deepcopy(self.data['boards.csv'])}
        if name=='list_aliases':return {'aliases':deepcopy(self.data['people_aliases.csv'])}
        if name=='list_calendar':
            public=calendar(self.data);old={r['event'] for r in public}
            return {'events':public+[deepcopy(r) for r in self.state['calendar'] if r['event'] not in old]}
        if name=='list_crm':
            rows=deepcopy(self.state['records']);raw={r['id']:r for r in self.data['crm.csv']+self.data.get('crm_archive.csv',[])}
            for r in rows:
                if raw[r['id']]['deleted']=='':r['deleted']=None
            return {'records':rows}
        if name=='create_event':return self.create_event(args)
        if any(not isinstance(v,str) or not v for v in args.values()):raise ValueError('Expected nonempty string fields')
        if name=='create_task':
            date.fromisoformat(args['due']);boards=[r for r in self.data['boards.csv'] if r['id']==args['board']]
            if len(boards)!=1 or boards[0]['archived']!='0':raise ValueError('Unknown or archived board')
            if args['list'].casefold()!=boards[0]['list'].casefold():raise ValueError('Unknown board list')
            record=dict(task='TASK'+str(1000+len(self.state['tasks'])),**args)
            record['owner']=self.owner(args['owner']);record['list']=boards[0]['list']
            self.state['tasks'].append(record);self.state['effect_events'].append(dict(op='task',record=deepcopy(record)))
            self.calls.append(name);return {'task':record['task']}
        if name=='send_email':
            if '@' not in args['to']:raise ValueError('Expected email address')
            record=dict(message_id='MSG'+str(1000+len(self.state['sent'])),**deepcopy(args))
            self.state['sent'].append(record);self.state['effect_events'].append(dict(op='email',record=deepcopy(record)))
            self.calls.append(name);return {'message_id':record['message_id']}
        owner=self.owner(args['owner']);matches=[r for r in self.state['records'] if r['id']==args['id']]
        if len(matches)!=1:raise ValueError('Unknown record')
        row=matches[0]
        if row['owner']!=owner:
            row['owner']=owner;self.state['effect_events'].append(dict(op='transfer',id=row['id'],owner=owner))
        self.calls.append(name);return dict(id=row['id'],owner=owner)
    def owner(self,value):
        aliases={r['contact']:r['email'] for r in self.data['contacts.csv']}
        aliases.update({r['alias']:r['current_email'] for r in self.data['people_aliases.csv']})
        if value in aliases:return aliases[value]
        if value in aliases.values():return value
        raise ValueError('Unknown person')
    def create_event(self,args):
        if any(not isinstance(args[k],str) or not args[k] for k in ['owner','day','title']):raise ValueError('Expected string fields')
        date.fromisoformat(args['day'])
        if any(type(args[k]) is not int for k in ['start','end']) or not 0<=args['start']<args['end']<=1440:raise ValueError('Invalid minute interval')
        if not isinstance(args['attendees'],list) or any(not isinstance(p,str) or '@' not in p for p in args['attendees']):raise ValueError('Invalid attendees')
        record=dict(event='CAL'+str(1000+len(self.state['calendar'])),status='confirmed',**deepcopy(args))
        self.state['calendar'].append(record)
        self.state['invitations'] += [dict(event=record['event'],to=p,day=record['day'],start=record['start'],end=record['end'],title=record['title']) for p in record['attendees']]
        self.state['effect_events'].append(dict(op='meeting',record=deepcopy(record)));self.calls.append('create_event')
        return {'event':record['event']}
