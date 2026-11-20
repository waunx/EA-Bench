"""WB07 conditional creation, permitted ties and unchanged existing work."""
from copy import deepcopy
from .authored import reviewed_worlds
from .english_wb07 import load,solve,fact,latest_tasks
from .acceptance import CheckResult
from .session import BindingError,canonical

def same(a,b):return canonical(a)==canonical(b)
def task_records(data,answers=None):
    people={r['owner']:r['email'] for r in data['people.csv']};boards={r['alias']:r['canonical'] for r in data['board_aliases.csv']};rows=[]
    for raw in latest_tasks(data).values():
        row=dict(raw);owner=row['owner'] or (fact(data,'t3_owner',answers) if answers is not None else None)
        row.update(owner=people[owner] if owner else None,board=boards[row['board']],revision=int(row['revision']),due=row['due'] or None)
        rows.append(row)
    return rows

def initial_state(data,answers):return dict(source_data=deepcopy(data),tasks=task_records(data,answers),task_events=[])

def accepted_new(rows,target):
    if not target['create']:return rows==[]
    if len(rows)!=1:return False
    row=rows[0];spec=target['create'][0]
    expected=dict(task=row['task'],revision=1,board='FRONT_END',owner=row['owner'],status='backlog',title=spec['title'],due=spec['due'])
    return row['owner'] in target['permitted_assignees'] and same(row,expected)

class WB07Checker:
    def __init__(self,variant,answers,backend):
        self.data=load(variant);self.target=solve(self.data,answers)
        matches=[e for a,e in reviewed_worlds('WB07',variant) if same(a,answers)]
        if len(matches)!=1 or not same(matches[0],self.target):raise BindingError('WB07 reviewed result mismatch')
        self.backend,self.initial=backend,backend.snapshot()
        if not same(self.initial,initial_state(self.data,answers)):raise BindingError('WB07 initial task mismatch')
    def final(self,report):
        state=self.backend.snapshot();rows=state.get('tasks',[]);old={r['task']:r for r in self.initial['tasks']}
        unique=all(isinstance(r,dict) and isinstance(r.get('task'),str) for r in rows) and len({r['task'] for r in rows})==len(rows)
        by_id={r['task']:r for r in rows} if unique else {};new=[r for k,r in by_id.items() if k not in old]
        checks=dict(unique_task_ids=unique,correct_conditional_task=accepted_new(new,self.target),
            existing_tasks_preserved=all(same(by_id.get(k),v) for k,v in old.items()),task_effect_ledger=self.ledger(state,old),
            source_records_preserved=same(state.get('source_data'),self.initial['source_data']),state_fields_preserved=set(state)==set(self.initial),
            report=isinstance(report,dict) and set(report)=={'summary'} and isinstance(report['summary'],str) and bool(report['summary'].strip()))
        return CheckResult.evaluated('authored_state',checks,backend='authored_fixture')
    def ledger(self,state,old):
        replay=deepcopy(old)
        try:
            for event in state.get('task_events',[]):
                if set(event)!={'op','record'}:return False
                row=event['record'];identity=row['task']
                if identity in old:return False
                if event['op']=='create_task':
                    if identity in replay:return False
                elif event['op']=='update_task':
                    if identity not in replay:return False
                else:return False
                replay[identity]=deepcopy(row)
            return same(sorted(replay.values(),key=lambda r:r['task']),sorted(state.get('tasks',[]),key=lambda r:r['task']))
        except (KeyError,TypeError):return False
