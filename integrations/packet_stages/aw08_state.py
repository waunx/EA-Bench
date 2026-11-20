"""AW08 actual request ledger, metadata, balances and replacement timing."""
from copy import deepcopy
from .authored import reviewed_worlds
from .author_english_aw08 import REQUEST_IDS
from .english_aw08 import load,solve,actions,requests,fact
from .acceptance import CheckResult
from .session import BindingError,canonical


def same(a,b):return canonical(a)==canonical(b)


def mapped(result):
    return dict(result,keep_requests=sorted(REQUEST_IDS.get(k,k) for k in result['keep_requests']),
                cancel_requests=sorted(REQUEST_IDS.get(k,k) for k in result['cancel_requests']))


def initial_state(data,answers):
    rows=[]
    for r in requests(data):
        row=deepcopy(r);row['amount_cents']=int(row['amount_cents']);row['public']=row['public']=='true'
        row['state']=fact(data,row['state'],'req1_state',answers);rows.append(row)
    return dict(source_data=deepcopy(data),requests=rows,request_events=[])


class AW08Checker:
    def __init__(self,variant,answers,backend):
        self.data,self.answers=load(variant),deepcopy(answers)
        matches=[mapped(e) for a,e in reviewed_worlds('AW08',variant) if same(a,answers)]
        self.target=solve(self.data,answers)
        if len(matches)!=1 or not same(matches[0],actions(self.target)):
            raise BindingError('AW08 differs from reviewed world')
        self.backend,self.initial=backend,backend.snapshot()
        if not same(self.initial,initial_state(self.data,answers)):raise BindingError('Initial request state mismatch')

    def final(self,report):
        state=self.backend.snapshot(); rows=state.get('requests',[])
        shape=isinstance(rows,list) and all(isinstance(r,dict) and isinstance(r.get('request'),str) for r in rows)
        ids=[r['request'] for r in rows] if shape else []
        unique=shape and len(ids)==len(set(ids))
        by_id={r['request']:r for r in rows} if unique else {}
        originals={r['request']:r for r in self.initial['requests']}
        retained=True
        for identity,row in originals.items():
            expected=dict(row,state='cancelled') if identity in self.target['cancel_requests'] else row
            retained=retained and same(by_id.get(identity),expected)
        new=[r for r in rows if r['request'] not in originals] if unique else []
        active_new=[r for r in new if r.get('state')=='pending']
        new_ok=len(active_new)==len(self.target['new_requests']) and {r.get('person') for r in active_new}==set(self.target['new_requests'])
        new_ok=new_ok and all(same(r,dict(request=r['request'],person=r['person'],event_ref='LUNCH-0928',
            amount_cents=self.target['new_requests'][r['person']],state='pending',public=True,note='Lunch Meeting Order')) for r in active_new)
        new_ok=new_ok and all(set(r)=={'request','person','event_ref','amount_cents','state','public','note'}
            and r['state'] in {'pending','cancelled'} and r['person'] in self.target['new_requests']
            and r['event_ref']=='LUNCH-0928' and type(r['amount_cents']) is int and r['amount_cents']>0
            and r['public'] is True and r['note']=='Lunch Meeting Order' for r in new)
        pending=[r for r in rows if r.get('event_ref')=='LUNCH-0928' and r.get('state')=='pending'] if unique else []
        balances={k:v for k,v in self.target['owed'].items() if k!='SELF' and v>0}
        pending_ok=len(pending)==len(balances) and {r.get('person') for r in pending}==set(balances)
        pending_ok=pending_ok and all(type(r.get('amount_cents')) is int and r['amount_cents']==balances[r['person']]
            and r.get('public') is True and r.get('note')=='Lunch Meeting Order' for r in pending)
        checks=dict(unique_request_ids=bool(unique),initial_records_reconciled=bool(retained),
                    correct_new_requests=bool(new_ok),one_public_request_per_owed_person=bool(pending_ok),
                    cancel_before_replacement=self.timing(state,originals,new),
                    source_records_preserved=same(state.get('source_data'),self.initial['source_data']),
                    state_fields_preserved=set(state)==set(self.initial),
                    report=isinstance(report,dict) and set(report)=={'summary'} and isinstance(report['summary'],str) and bool(report['summary'].strip()))
        return CheckResult.evaluated('authored_state',checks,backend='authored_fixture')

    def timing(self,state,originals,new):
        replay=deepcopy(originals);new_by_id={r['request']:r for r in new}
        try:
            for event in state.get('request_events',[]):
                if set(event)!={'op','request'}:return False
                identity=event['request']
                if event['op']=='cancel':
                    if identity not in replay or replay[identity]['state']!='pending':return False
                    replay[identity]['state']='cancelled'
                elif event['op']=='create':
                    if identity in replay or identity not in new_by_id:return False
                    row=dict(new_by_id[identity],state='pending')
                    if any(r['state']=='pending' and r['person']==row['person'] and r['event_ref']==row['event_ref']
                           for r in replay.values()):return False
                    replay[identity]=row
                else:return False
        except (TypeError,KeyError):return False
        return same(sorted(replay.values(),key=lambda r:r['request']),
                    sorted(state.get('requests',[]),key=lambda r:r['request']))
