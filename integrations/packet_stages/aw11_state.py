"""AW11 actual follow additions, preservation and chronological effects."""
from copy import deepcopy
from .authored import reviewed_worlds
from .english_aw11 import load,solve,current
from .acceptance import CheckResult
from .session import BindingError,canonical

def same(a,b):return canonical(a)==canonical(b)
def initial_state(data,answers):
    return dict(source_data=deepcopy(data),following=sorted(current(data,answers)),follow_events=[])

class AW11Checker:
    def __init__(self,variant,answers,backend):
        self.data=load(variant);self.target=solve(self.data,answers)
        matches=[e for a,e in reviewed_worlds('AW11',variant) if same(a,answers)]
        if len(matches)!=1 or not same(matches[0],self.target):raise BindingError('AW11 reviewed result mismatch')
        self.backend,self.initial=backend,backend.snapshot()
        if not same(self.initial,initial_state(self.data,answers)):raise BindingError('AW11 initial state mismatch')

    def final(self,report):
        state=self.backend.snapshot();events=state.get('follow_events',[])
        desired=[dict(op='follow',artist=k) for k in self.target['add']]
        following=state.get('following',[])
        checks=dict(correct_following=same(following,self.target['final']),
            exact_additions=same(sorted(events,key=canonical),sorted(desired,key=canonical)),
            existing_follows_preserved=isinstance(following,list) and set(self.initial['following']).issubset(following),
            no_unfollow=all(isinstance(e,dict) and e.get('op')!='unfollow' for e in events),
            source_records_preserved=same(state.get('source_data'),self.initial['source_data']),
            state_fields_preserved=set(state)==set(self.initial),
            report=isinstance(report,dict) and set(report)=={'summary'} and isinstance(report['summary'],str) and bool(report['summary'].strip()))
        return CheckResult.evaluated('authored_state',checks,backend='authored_fixture')
