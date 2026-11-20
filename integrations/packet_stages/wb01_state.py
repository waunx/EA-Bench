"""WB01 calendar event plus invitation state, including conditional no-op."""
from copy import deepcopy
import json
from .authored import reviewed_worlds
from .english_wb01 import load,solve,fact,dates
from .acceptance import CheckResult
from .session import BindingError,canonical

def same(a,b):return canonical(a)==canonical(b)
def calendar(data,answers=None):
    rows=[]
    for raw in data['calendar.csv']+data.get('calendar_copy.csv',[]):
        row=dict(raw);row['start']=int(row['start'])
        row['end']=int(row['end']) if row['end'] else fact(data,'busy_end',answers) if answers is not None else None
        row['attendees']=json.loads(row['attendees']);rows.append(row)
    return rows

def initial_state(data,answers):return dict(source_data=deepcopy(data),calendar=calendar(data,answers),invitations=[],calendar_events=[])
class WB01Checker:
    def __init__(self,variant,answers,backend):
        self.data=load(variant);self.target=solve(self.data,answers)
        matches=[e for a,e in reviewed_worlds('WB01',variant) if same(a,answers)]
        if len(matches)!=1 or not same(matches[0],self.target):raise BindingError('WB01 reviewed result mismatch')
        self.backend,self.initial=backend,backend.snapshot()
        if not same(self.initial,initial_state(self.data,answers)):raise BindingError('WB01 initial state mismatch')
    def final(self,report):
        state=self.backend.snapshot();rows=state.get('calendar',[]);old={r['event']:r for r in self.initial['calendar']}
        unique=all(isinstance(r,dict) and isinstance(r.get('event'),str) for r in rows) and len({r['event'] for r in rows})==len(rows)
        by_id={r['event']:r for r in rows} if unique else {};new=[r for k,r in by_id.items() if k not in old]
        expected=[dict(owner='self',day=dates(self.data)[2],start=r['start'],end=r['end'],title=r['title'],attendees=[r['to']]) for r in self.target['events']]
        actual=[{k:v for k,v in r.items() if k!='event'} for r in new]
        invites=[dict(event=r['event'],to=person,day=r['day'],start=r['start'],end=r['end'],title=r['title']) for r in new for person in r.get('attendees',[])]
        checks=dict(unique_calendar_ids=unique,correct_new_meeting=same(actual,expected),
            initial_calendar_preserved=all(same(by_id.get(k),v) for k,v in old.items()),
            invitation_matches_meeting=same(state.get('invitations'),invites),
            creation_effects=same(state.get('calendar_events'),[dict(op='create_event',record=r) for r in new]),
            source_records_preserved=same(state.get('source_data'),self.initial['source_data']),
            state_fields_preserved=set(state)==set(self.initial),
            report=isinstance(report,dict) and set(report)=={'summary'} and isinstance(report['summary'],str) and bool(report['summary'].strip()))
        return CheckResult.evaluated('authored_state',checks,backend='authored_fixture')
