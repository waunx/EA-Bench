"""AW08 account operations; reads never expose computed balances or hidden facts."""
from copy import deepcopy
from .packet_interface import PacketInterface,SYSTEM,OUTPUT_FORMAT
from .english_packet import inputs
from .english_aw08 import load,requests,NeedFact
from .aw08_state import AW08Checker,initial_state

API_FORMATS={
    'list_meal_replies':{},'list_payments':{},'list_requests':{},
    'cancel_request':{'request':'request ID'},
    'create_request':{'person':'person ID','event_ref':'event ID','amount_cents':'positive integer',
                      'public':'boolean','note':'description string'},
}


class OpenAW08(PacketInterface):
    case='AW08'; validation_layer='authored_fixture'; api_formats=API_FORMATS; need_fact_error=NeedFact
    fact_labels=dict(pay17_event='Payment event attribution',a_food='Final food amount',req1_state='Request lifecycle',
                     pay17_amount='Settled payment amount',pay18_state='Payment settlement status',rounding='Residual-cent convention')

    def __init__(self,variant='full',answers=None,ask_handler=None):
        self.variant,self.folder=variant,inputs('AW08',variant);self.data=load(variant)
        self.answers,self.confirmed=deepcopy(answers or {}),{}
        self.state=initial_state(self.data,self.answers);self.checker=AW08Checker(variant,self.answers,self)
        self.files={p.name:p for p in self.folder.iterdir() if p.is_file()}
        self.events,self.calls,self.effects=[],[],{};self.done=False;self.result=None;self.ask_handler=ask_handler
        self.raw_requests={r['request']:r for r in requests(self.data)};self.revealed_states=set()

    def call(self,name,arguments):
        if name not in API_FORMATS:raise ValueError('Unknown API')
        if name=='cancel_request':return self.cancel(arguments)
        if name=='create_request':return self.create(arguments)
        if arguments:raise ValueError('This API takes no arguments')
        if name=='list_meal_replies':return {'replies':deepcopy(self.data['meal_replies.csv']+self.data.get('meal_reply_archive.csv',[]))}
        if name=='list_payments':return {'payments':deepcopy(self.data['payments.csv']+self.data.get('payment_journal.csv',[]))}
        rows=deepcopy(self.state['requests'])
        for row in rows:
            identity=row['request'];raw=self.raw_requests.get(identity)
            if raw and raw['state']=='' and identity not in self.revealed_states:row['state']=''
        return {'requests':rows}

    def cancel(self,arguments):
        if set(arguments)!={'request'} or not isinstance(arguments['request'],str):raise ValueError('Expected request ID')
        rows=[r for r in self.state['requests'] if r['request']==arguments['request']]
        if len(rows)!=1:raise ValueError('Unknown request')
        row=rows[0]
        if row['state']=='pending':
            row['state']='cancelled';self.state['request_events'].append(dict(op='cancel',request=row['request']))
        self.revealed_states.add(row['request']);self.calls.append('cancel_request')
        return dict(request=row['request'],state='cancelled')

    def create(self,arguments):
        if set(arguments)!={'person','event_ref','amount_cents','public','note'}:raise ValueError('Expected person, event_ref, amount_cents, public and note')
        if any(not isinstance(arguments[k],str) for k in ['person','event_ref','note']):raise ValueError('Expected string identifiers and note')
        if type(arguments['amount_cents']) is not int or arguments['amount_cents']<=0 or type(arguments['public']) is not bool:raise ValueError('Expected positive cents and public boolean')
        if arguments['person'] not in {r['person'] for r in self.data['meal_replies.csv']} or arguments['person']=='SELF':raise ValueError('Unknown recipient or request to own account')
        identity='REQ'+str(1000+len(self.state['requests']))
        record=dict(arguments,request=identity,state='pending')
        self.state['requests'].append(record);self.state['request_events'].append(dict(op='create',request=identity));self.calls.append('create_request')
        return deepcopy(record)
