"""WB02 visible workload records and local CRM effects."""
from copy import deepcopy
from .packet_interface import PacketInterface,SYSTEM,OUTPUT_FORMAT
from .english_packet import inputs
from .english_wb02 import load,aliases,NeedFact
from .wb02_state import WB02Checker,initial_state
FIELDS=dict(name='person name',status='CRM status',owner='employee ID or email')
API_FORMATS=dict(list_employees={},list_tasks={},list_aliases={},list_records={},create_record=FIELDS,update_record=dict(record='record ID',**FIELDS))
class OpenWB02(PacketInterface):
    case='WB02';validation_layer='authored_fixture';api_formats=API_FORMATS;need_fact_error=NeedFact
    fact_labels=dict(eligible_y='Current staff eligibility',same_task='Task identity',c_last_lead='Last lead assignment date')
    def __init__(self,variant='full',answers=None,ask_handler=None):
        self.variant,self.folder=variant,inputs('WB02',variant);self.data=load(variant)
        self.answers,self.confirmed=deepcopy(answers or {}),{}
        self.state=initial_state(self.data);self.checker=WB02Checker(variant,self.answers,self)
        self.files={p.name:p for p in self.folder.iterdir() if p.is_file()}
        self.events,self.calls,self.effects=[],[],{}
        self.done=False;self.result=None;self.ask_handler=ask_handler
    def call(self,name,args):
        if name not in API_FORMATS:raise ValueError('Unknown API')
        if set(args)!=set(API_FORMATS[name]):raise ValueError('Arguments must match API format')
        if name=='list_employees':return {'employees':deepcopy(self.data['employees.csv'])}
        if name=='list_tasks':return {'tasks':deepcopy(self.data['assigned_tasks.csv']+self.data.get('closed_tasks.csv',[])+self.data.get('unavailable_staff_tasks.csv',[]))}
        if name=='list_aliases':return {'aliases':deepcopy(self.data['owner_aliases.csv']+self.data.get('owner_alias_copy.csv',[]))}
        if name=='list_records':return {'records':deepcopy(self.state['records'])}
        if any(not isinstance(v,str) or not v.strip() for v in args.values()):raise ValueError('Expected nonempty string fields')
        if args['status'] not in {'Lead','Customer'}:raise ValueError('Unknown CRM status')
        employees={r['employee']:r['email'] for r in self.data['employees.csv']}
        employee=args['owner'] if args['owner'] in employees else aliases(self.data).get(args['owner'])
        if employee not in employees:raise ValueError('Unknown staff identity')
        records=self.state['records'];before=deepcopy(records)
        if name=='create_record':
            identity='CRM'+str(1000+len(records));row=dict(record=identity,name=args['name'],status=args['status'],owner=employees[employee]);records.append(row)
        else:
            matches=[r for r in records if r['record']==args['record']]
            if len(matches)!=1:raise ValueError('Unknown CRM record')
            row=matches[0];row.update(name=args['name'],status=args['status'],owner=employees[employee])
        if before!=records:self.state['crm_events'].append(dict(op=name,record=deepcopy(row)))
        self.calls.append(name);return dict(record=row['record'],status='saved')
