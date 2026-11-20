"""AW14 exact expense state, member balances, preservation and real effects."""
from copy import deepcopy
from .authored import reviewed_worlds
from .english_aw14 import load,solve,expenses,entry
from .acceptance import CheckResult
from .session import BindingError,canonical

def same(a,b):return canonical(a)==canonical(b)
def mapped(result):return dict(result,protected=['E01','E90'])
def initial_state(data):return dict(source_data=deepcopy(data),expenses=expenses(data),expense_events=[])
class AW14Checker:
    def __init__(self,variant,answers,backend):
        self.data=load(variant);self.target=solve(self.data,answers)
        matches=[mapped(e) for a,e in reviewed_worlds('AW14',variant) if same(a,answers)]
        if len(matches)!=1 or not same(matches[0],self.target):raise BindingError('AW14 reviewed result mismatch')
        self.backend,self.initial=backend,backend.snapshot()
        if not same(self.initial,initial_state(self.data)):raise BindingError('AW14 initial state mismatch')
        self.expected={m:entry(self.data,m,sum(s.values())) for m,s in self.target['shares'].items()}
        self.updates={a['expense']:self.expected[a['month']] for a in self.target['actions'] if a['op']=='update'}
    def final(self,report):
        state=self.backend.snapshot();rows=state.get('expenses',[])
        shape=isinstance(rows,list) and all(isinstance(r,dict) and isinstance(r.get('expense'),str) for r in rows)
        unique=shape and len({r['expense'] for r in rows})==len(rows)
        by_id={r['expense']:r for r in rows} if unique else {}
        old={r['expense']:r for r in self.initial['expenses']}
        preserved=all(same(by_id.get(k),dict(expense=k,**self.updates[k]) if k in self.updates else v) for k,v in old.items())
        group=self.data['account_context.json']['group'];year=self.data['account_context.json']['snapshot_date'][:4]
        current=[r for r in rows if not r.get('deleted') and r.get('group')==group and r.get('category')=='electricity' and str(r.get('usage_month','')).startswith(year+'-')] if unique else []
        exact=len(current)==len(self.expected) and {r.get('usage_month') for r in current}==set(self.expected)
        exact=exact and all(same({k:v for k,v in r.items() if k!='expense'},self.expected[r['usage_month']]) for r in current)
        scoped=unique and all(r.get('group')==group and r.get('category')=='electricity' and r.get('usage_month') in self.expected
            for r in rows if r['expense'] not in old)
        shares_ok=all(isinstance(r.get('shares'),dict) and all(type(v) is int and v>=0 for v in r['shares'].values())
            and type(r.get('amount_cents')) is int and sum(r['shares'].values())==r['amount_cents'] for r in current)
        total_ok=shares_ok and sum(r['amount_cents'] for r in current)==self.target['total_cents']
        checks=dict(unique_expense_ids=bool(unique),initial_records_reconciled=preserved,exact_monthly_entries=exact,
            new_records_within_scope=scoped,shares_conserve_cents=shares_ok,correct_total_including_self=total_ok,
            effect_ledger=self.ledger(state,old),source_records_preserved=same(state.get('source_data'),self.initial['source_data']),
            state_fields_preserved=set(state)==set(self.initial),
            report=isinstance(report,dict) and set(report)=={'summary'} and isinstance(report['summary'],str) and bool(report['summary'].strip()))
        return CheckResult.evaluated('authored_state',checks,backend='authored_fixture')
    def ledger(self,state,old):
        replay=deepcopy(old)
        try:
            for event in state.get('expense_events',[]):
                if set(event)!={'op','expense','record'}:return False
                identity=event['expense'];record=event['record'];op=event['op']
                if record['expense']!=identity:return False
                if identity in old and (identity not in self.updates or op!='update_expense'):return False
                if op=='create_expense':
                    if identity in replay or record['deleted'] is not False:return False
                elif op=='update_expense':
                    if identity not in replay or replay[identity]['deleted'] or record['deleted'] is not False:return False
                elif op=='delete_expense':
                    if identity not in replay or replay[identity]['deleted'] or not same(record,dict(replay[identity],deleted=True)):return False
                else:return False
                replay[identity]=deepcopy(record)
            return same(sorted(replay.values(),key=lambda r:r['expense']),sorted(state.get('expenses',[]),key=lambda r:r['expense']))
        except (KeyError,TypeError):return False
