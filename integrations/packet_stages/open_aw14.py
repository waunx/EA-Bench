"""AW14 authored expense API with visible-only reads and explicit writes."""
from copy import deepcopy
from .packet_interface import PacketInterface,SYSTEM,OUTPUT_FORMAT
from .english_packet import inputs
from .english_aw14 import load,NeedFact
from .aw14_state import AW14Checker,initial_state
FIELDS=dict(group='group ID',category='expense category',usage_month='YYYY-MM',amount_cents='nonnegative integer',payer='person ID',note='expense note',shares={'person ID':'nonnegative integer'})
API_FORMATS=dict(list_bills={},list_credits={},list_expenses={},list_members={},get_context={},
    create_expense=FIELDS,update_expense=dict(expense='expense ID',**FIELDS),delete_expense={'expense':'expense ID'})
class OpenAW14(PacketInterface):
    case='AW14';validation_layer='authored_fixture';api_formats=API_FORMATS;need_fact_error=NeedFact
    fact_labels=dict(active='Current credit status',march='Gross bill amount',credit='Credit adjustment amount')
    def __init__(self,variant='full',answers=None,ask_handler=None):
        self.variant,self.folder=variant,inputs('AW14',variant);self.data=load(variant)
        self.answers,self.confirmed=deepcopy(answers or {}),{}
        self.state=initial_state(self.data);self.checker=AW14Checker(variant,self.answers,self)
        self.files={p.name:p for p in self.folder.iterdir() if p.is_file()}
        self.events,self.calls,self.effects=[],[],{}
        self.done=False;self.result=None;self.ask_handler=ask_handler
    def call(self,name,args):
        if name not in API_FORMATS:raise ValueError('Unknown API')
        if set(args)!=set(API_FORMATS[name]):raise ValueError('Arguments must match API format')
        if name=='list_bills':return {'bills':deepcopy(self.data['bills.csv']+self.data.get('statement_archive.csv',[]))}
        if name=='list_credits':return {'credits':deepcopy(self.data['credit_notice.csv']),'archive':deepcopy(self.data.get('credit_archive.json'))}
        if name=='list_expenses':return {'expenses':deepcopy(self.state['expenses'])}
        if name=='list_members':return {'members':deepcopy(self.data['roommates.csv'])}
        if name=='get_context':return deepcopy(self.data['account_context.json'])
        return self.write(name,args)
    def write(self,name,args):
        rows=self.state['expenses'];before=deepcopy(rows)
        if name!='create_expense':
            matches=[r for r in rows if r['expense']==args['expense']]
            if len(matches)!=1:raise ValueError('Unknown expense')
            row=matches[0];identity=row['expense']
        else:identity='E'+str(1000+len(rows))
        if name=='delete_expense':row['deleted']=True
        else:
            self.validate_fields(args)
            record={k:deepcopy(args[k]) for k in FIELDS};record.update(expense=identity,deleted=False)
            if name=='create_expense':rows.append(record)
            else:
                if row['deleted']:raise ValueError('Expense is deleted')
                row.clear();row.update(record)
        if before!=rows:
            self.state['expense_events'].append(dict(op=name,expense=identity,record=deepcopy(next(r for r in rows if r['expense']==identity))))
        self.calls.append(name);return dict(expense=identity,status='deleted' if name=='delete_expense' else 'saved')
    def validate_fields(self,args):
        from datetime import datetime
        if any(not isinstance(args[k],str) for k in ['group','category','usage_month','payer','note']):raise ValueError('Expected string fields')
        if len(args['usage_month'])!=7:raise ValueError('Expected YYYY-MM usage month')
        datetime.strptime(args['usage_month'],'%Y-%m')
        if type(args['amount_cents']) is not int or args['amount_cents']<0:raise ValueError('Expected nonnegative integer cents')
        shares=args['shares']
        if not isinstance(shares,dict) or not shares or any(not isinstance(k,str) or type(v) is not int or v<0 for k,v in shares.items()):raise ValueError('Expected integer shares by person')
        if sum(shares.values())!=args['amount_cents']:raise ValueError('Shares must sum to total amount')
