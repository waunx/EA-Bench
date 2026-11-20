"""WB02 new Lead ownership and preserved pre-existing CRM state."""
from copy import deepcopy
from .authored import reviewed_worlds
from .english_wb02 import load,solve
from .acceptance import CheckResult
from .session import BindingError,canonical

def same(a,b):return canonical(a)==canonical(b)
def initial_state(data):return dict(source_data=deepcopy(data),records=deepcopy(data['crm_records.json']),crm_events=[])
class WB02Checker:
    def __init__(self,variant,answers,backend):
        self.data=load(variant);self.target=solve(self.data,answers)
        matches=[e for a,e in reviewed_worlds('WB02',variant) if same(a,answers)]
        if len(matches)!=1 or not same(matches[0],self.target):raise BindingError('WB02 reviewed result mismatch')
        self.backend,self.initial=backend,backend.snapshot()
        if not same(self.initial,initial_state(self.data)):raise BindingError('WB02 initial CRM mismatch')
    def final(self,report):
        state=self.backend.snapshot();rows=state.get('records',[]);old={r['record']:r for r in self.initial['records']}
        unique=all(isinstance(r,dict) and isinstance(r.get('record'),str) for r in rows) and len({r['record'] for r in rows})==len(rows)
        by_id={r['record']:r for r in rows} if unique else {};new=[r for k,r in by_id.items() if k not in old]
        correct=len(new)==1 and same(new[0],dict(record=new[0]['record'],name=self.target['lead'],status='Lead',owner=self.target['assign_to']))
        checks=dict(unique_crm_ids=unique,one_correct_new_lead=correct,
            existing_records_preserved=all(same(by_id.get(k),v) for k,v in old.items()),
            crm_effect_ledger=self.ledger(state,old),
            source_records_preserved=same(state.get('source_data'),self.initial['source_data']),
            state_fields_preserved=set(state)==set(self.initial),
            report=isinstance(report,dict) and set(report)=={'summary'} and isinstance(report['summary'],str) and bool(report['summary'].strip()))
        return CheckResult.evaluated('authored_state',checks,backend='authored_fixture')
    def ledger(self,state,old):
        replay=deepcopy(old)
        try:
            for event in state.get('crm_events',[]):
                if set(event)!={'op','record'}:return False
                row=event['record'];identity=row['record']
                if identity in old:return False
                if event['op']=='create_record':
                    if identity in replay:return False
                elif event['op']=='update_record':
                    if identity not in replay:return False
                else:return False
                replay[identity]=deepcopy(row)
            return same(sorted(replay.values(),key=lambda r:r['record']),sorted(state.get('records',[]),key=lambda r:r['record']))
        except (KeyError,TypeError):return False
