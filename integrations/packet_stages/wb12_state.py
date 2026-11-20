"""WB12 real local deletions, preserved records and delete-before-email order."""
from copy import deepcopy
from .authored import reviewed_worlds
from .english_wb12 import load,solve,fact,raw_records
from .acceptance import CheckResult
from .session import BindingError,canonical

def same(a,b):return canonical(a)==canonical(b)
def records(data,answers=None):
    rows=[]
    for raw in raw_records(data):
        row=dict(raw);row['owner']=row['owner'] or (fact(data,'l2_owner',answers) if answers is not None else None)
        state=row['deleted'] or (fact(data,'l5_deleted',answers) if answers is not None else None)
        row['deleted']=state=='1' if state is not None else None;rows.append(row)
    return rows

def initial_state(data,answers):return dict(source_data=deepcopy(data),records=records(data,answers),sent=[],effect_events=[])
class WB12Checker:
    def __init__(self,variant,answers,backend):
        self.data=load(variant);self.target=solve(self.data,answers)
        matches=[e for a,e in reviewed_worlds('WB12',variant) if same(a,answers)]
        if len(matches)!=1 or not same(matches[0],self.target):raise BindingError('WB12 reviewed result mismatch')
        self.backend,self.initial=backend,backend.snapshot()
        if not same(self.initial,initial_state(self.data,answers)):raise BindingError('WB12 initial state mismatch')
    def final(self,report):
        state=self.backend.snapshot();rows=state.get('records',[])
        unique=all(isinstance(r,dict) and isinstance(r.get('id'),str) for r in rows) and len({r['id'] for r in rows})==len(rows)
        expected=[dict(r,deleted=True) if r['id'] in self.target['delete'] else r for r in self.initial['records']]
        reconciled=unique and same(sorted(rows,key=lambda r:r['id']),sorted(expected,key=lambda r:r['id']))
        emails=state.get('sent',[])
        mail_ok=len(emails)==1 and same(emails[0],dict(message_id=emails[0].get('message_id'),**{k:self.target[k] for k in ['to','subject','body']})) and isinstance(emails[0].get('message_id'),str)
        events=state.get('effect_events',[])
        expected_events=[dict(op='delete',id=k) for k in self.target['delete']]+[dict(op='send',message=m) for m in emails]
        effects=same(sorted(events,key=canonical),sorted(expected_events,key=canonical))
        ordered=effects and len(emails)==1 and events[-1]==dict(op='send',message=emails[0])
        checks=dict(unique_record_ids=unique,exact_deletion_scope_and_preservation=reconciled,
            exact_notification=mail_ok,actual_effects=effects,all_deletions_before_email=ordered,
            source_records_preserved=same(state.get('source_data'),self.initial['source_data']),state_fields_preserved=set(state)==set(self.initial),
            report=isinstance(report,dict) and set(report)=={'summary'} and isinstance(report['summary'],str) and bool(report['summary'].strip()))
        return CheckResult.evaluated('authored_state',checks,backend='authored_fixture')
