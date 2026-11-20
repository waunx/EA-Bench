"""WB07 accepted metric revisions, strict threshold and completed-work maxima."""
import csv,json
from datetime import date,timedelta
from .english_packet import inputs
class NeedFact(Exception):pass

def load(variant):
    data={}
    for p in inputs('WB07',variant).iterdir():
        if p.suffix=='.csv':
            with p.open(newline='') as f:data[p.name]=list(csv.DictReader(f))
        elif p.suffix=='.json':data[p.name]=json.loads(p.read_text())
        else:data[p.name]=p.read_text()
    return data

def observed(data):
    note=data.get('case_decision.md','');count=next(r['sessions'] for r in data['metric_partitions.csv'] if r['partition']=='P2' and r['revision']=='1')
    return dict(qa=True if 'is accepted.' in note else False if 'is rejected.' in note else None,
        t3_owner=next(r['owner'] for r in data['completed_tasks.csv'] if r['task']=='T3') or None,
        p2_sessions=int(count) if count else None)

def fact(data,key,answers):
    value=observed(data)[key]
    if value is not None:return value
    records=[r for r in data.get('source_records.json',[]) if r['fact']==key]
    if records:
        top=max(r['revision'] for r in records);values={r['value'] for r in records if r['revision']==top}
        if len(values)==1:return next(iter(values))
    if key not in answers:raise NeedFact(key)
    return answers[key]

def deadline(data):
    today=date.fromisoformat(data['analytics_context.json']['snapshot_date'])
    return (today-timedelta(days=today.weekday())+timedelta(days=11)).isoformat()

def trigger(data,qa,sessions):
    today=data['analytics_context.json']['snapshot_date'];since=today[:4]+'-11-27';effective={}
    for r in data['metric_partitions.csv']+data.get('metric_history.csv',[]):
        if not since<=r['day']<=today:continue
        if r['quality']!='accepted' and not (r['quality']=='BF7_pending' and qa):continue
        if r['partition'] not in effective or int(r['revision'])>int(effective[r['partition']]['revision']):effective[r['partition']]=r
    unknown=False
    for r in effective.values():
        n=sessions if r['partition']=='P2' and r['revision']=='1' else int(r['sessions'])
        if n is None:unknown=True;continue
        if n<=0:raise ValueError('Session count must be positive')
        if int(r['total_ms'])>19000*n:return True
    return None if unknown else False

def latest_tasks(data):
    latest={}
    for r in data['completed_tasks.csv']+data.get('task_archive.csv',[])+data.get('task_worklog.csv',[]):
        if r['task'] not in latest or int(r['revision'])>int(latest[r['task']]['revision']):latest[r['task']]=r
    return latest

def solve(data,answers):
    known={}
    for key in ['qa','p2_sessions']:
        try:known[key]=fact(data,key,answers)
        except NeedFact:known[key]=None
    q,n=known['qa'],known['p2_sessions']
    possibilities={trigger(data,value,n) for value in ([q] if q is not None else [False,True])}
    if possibilities=={False}:return dict(create=[],permitted_assignees=[])
    if possibilities!={True}:
        if q is None:q=fact(data,'qa',answers)
        yes=trigger(data,q,n)
        if yes is None:yes=trigger(data,q,fact(data,'p2_sessions',answers))
        if not yes:return dict(create=[],permitted_assignees=[])
    aliases={r['alias']:r['canonical'] for r in data['board_aliases.csv']};counts={}
    for r in latest_tasks(data).values():
        if aliases[r['board']]!='FRONT_END' or r['status'] not in {'done','completed'}:continue
        owner=r['owner'] or fact(data,'t3_owner',answers);counts[owner]=counts.get(owner,0)+1
    if not counts:raise NeedFact('No completed front-end assignee')
    emails={r['owner']:r['email'] for r in data['people.csv']}
    winners=sorted(emails[k] for k,v in counts.items() if v==max(counts.values()))
    return dict(create=[dict(owner=winners[0],title='Improve average session duration',board='Front end',list='Backlog',due=deadline(data))],permitted_assignees=winners)
