"""WB14 mutually exclusive cross-application effects and mail-before-transfer."""
from copy import deepcopy
import json
from .authored import reviewed_worlds
from .author_english_wb14 import BOARDS
from .english_wb14 import load,solve,fact,dates
from .acceptance import CheckResult
from .session import BindingError,canonical

def same(a,b):return canonical(a)==canonical(b)
def mapped(target):return dict(target,board=BOARDS[target['board']]) if 'board' in target else target

def calendar(data,answers=None):
    rows=[]
    for raw in data['calendar.csv']+data.get('calendar_history.csv',[]):
        row=dict(raw);row['start']=int(row['start']);row['attendees']=json.loads(row['attendees'])
        row['end']=int(row['end']) if row['end'] else fact(data,'busy_end',answers) if answers is not None else None
        row['status']=row['status'] or (fact(data,'calendar_state',answers) if answers is not None else None)
        rows.append(row)
    return rows

def records(data,answers=None):
    rows=[]
    for raw in data['crm.csv']+data.get('crm_archive.csv',[]):
        row=dict(raw);flag=row['deleted'] or (fact(data,'lead_state',answers) if answers is not None else None)
        row['deleted']=flag=='1' if flag is not None else None;rows.append(row)
    return rows

def initial_state(data,answers):return dict(source_data=deepcopy(data),calendar=calendar(data,answers),records=records(data,answers),tasks=[],invitations=[],sent=[],effect_events=[])
class WB14Checker:
    def __init__(self,variant,answers,backend):
        self.data=load(variant);self.target=solve(self.data,answers)
        matches=[mapped(e) for a,e in reviewed_worlds('WB14',variant) if same(a,answers)]
        if len(matches)!=1 or not same(matches[0],self.target):raise BindingError('WB14 reviewed result mismatch')
        self.backend,self.initial=backend,backend.snapshot()
        if not same(self.initial,initial_state(self.data,answers)):raise BindingError('WB14 initial state mismatch')
    def final(self,report):
        state=self.backend.snapshot();t=self.target;true=t['branch']=='task_and_meeting'
        old={r['event']:r for r in self.initial['calendar']};rows=state.get('calendar',[])
        unique=all(isinstance(r,dict) and isinstance(r.get('event'),str) for r in rows) and len({r['event'] for r in rows})==len(rows)
        by_id={r['event']:r for r in rows} if unique else {};new=[r for k,r in by_id.items() if k not in old]
        tasks=state.get('tasks',[]);emails=state.get('sent',[])
        expected_tasks=[] if not true else [dict(owner=t['owner'],board=t['board'],list=t['list'],title=t['task'],due=t['due'])]
        expected_meetings=[] if not true else [dict(owner='self',day=dates(self.data)[1],start=t['start'],end=t['end'],status='confirmed',title=t['meeting'],attendees=[t['owner']])]
        task_ok=all(isinstance(r,dict) and isinstance(r.get('task'),str) for r in tasks) and same([{k:v for k,v in r.items() if k!='task'} for r in tasks],expected_tasks)
        meeting_ok=same([{k:v for k,v in r.items() if k!='event'} for r in new],expected_meetings)
        expected_emails=[] if true else [dict(to=t['owner'],subject=t['subject'],body=t['body'])]
        mail_ok=all(isinstance(r,dict) and isinstance(r.get('message_id'),str) for r in emails) and same([{k:v for k,v in r.items() if k!='message_id'} for r in emails],expected_emails)
        expected_records=[dict(r,owner=t['owner']) if r['id'] in t['crm_updates'] else r for r in self.initial['records']]
        crm_ok=same(sorted(state.get('records',[]),key=lambda r:r['id']),sorted(expected_records,key=lambda r:r['id']))
        invites=[dict(event=r['event'],to=p,day=r['day'],start=r['start'],end=r['end'],title=r['title']) for r in new for p in r.get('attendees',[])]
        events=state.get('effect_events',[])
        expected_events=[dict(op='task',record=r) for r in tasks]+[dict(op='meeting',record=r) for r in new]+[dict(op='email',record=r) for r in emails]
        expected_events += [dict(op='transfer',id=k,owner=t['owner']) for k in t['crm_updates']]
        effects=same(sorted(events,key=canonical),sorted(expected_events,key=canonical))
        mail_positions=[i for i,e in enumerate(events) if len(emails)==1 and e==dict(op='email',record=emails[0])]
        order=true or (len(mail_positions)==1 and all(i>mail_positions[0] for i,e in enumerate(events) if e.get('op')=='transfer'))
        checks=dict(correct_task_branch=task_ok,correct_meeting_branch=meeting_ok,correct_email_branch=mail_ok,
            exact_crm_transfer_scope=crm_ok,calendar_preserved=unique and all(same(by_id.get(k),r) for k,r in old.items()),
            invitations_match=same(state.get('invitations'),invites),actual_effects=effects,email_before_all_transfers=order,
            source_records_preserved=same(state.get('source_data'),self.initial['source_data']),state_fields_preserved=set(state)==set(self.initial),
            report=isinstance(report,dict) and set(report)=={'summary'} and isinstance(report['summary'],str) and bool(report['summary'].strip()))
        return CheckResult.evaluated('authored_state',checks,backend='authored_fixture')
