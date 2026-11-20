"""WB14 metric-selected task/meeting versus email/lead-transfer decisions."""
import csv,json
from datetime import date,timedelta
from .english_packet import inputs
class NeedFact(Exception):pass

def load(variant):
    data={}
    for p in inputs('WB14',variant).iterdir():
        if p.suffix=='.csv':
            with p.open(newline='') as f:data[p.name]=list(csv.DictReader(f))
        elif p.suffix=='.json':data[p.name]=json.loads(p.read_text())
        else:data[p.name]=p.read_text()
    return data

def observed(data):
    note=data.get('case_decision.md','')
    return dict(qa=True if 'is accepted.' in note else False if 'is rejected.' in note else None,
        busy_end=next(r['end'] for r in data['calendar.csv'] if r['event']=='CAL1') or None,
        calendar_state=next(r['status'] for r in data['calendar.csv'] if r['event']=='CAL3') or None,
        recipient=data['recipient_binding.json']['contact'],workspace=data['workspace_binding.json']['workspace'],
        lead_state=next(r['deleted'] for r in data['crm.csv'] if r['id']=='NL2') or None)

def fact(data,key,answers):
    value=observed(data)[key]
    if value is not None:return int(value) if key=='busy_end' else value
    records=data.get(key+'_records.json',[])
    if records:
        top=max(r['revision'] for r in records);values={r['value'] for r in records if r['revision']==top}
        if len(values)==1:return next(iter(values))
    if key not in answers:raise NeedFact(key)
    return answers[key]

def dates(data):
    today=date.fromisoformat(data['operation_context.json']['snapshot_date'])
    return today.isoformat(),(today+timedelta(days=1)).isoformat(),(today-timedelta(days=today.weekday())+timedelta(days=11)).isoformat()

def trigger(data,qa):
    today,_,_=dates(data);effective={}
    for r in data['visits.csv']+data.get('visits_history.csv',[]):
        if not today[:4]+'-10-01'<=r['day']<=today:continue
        if r['quality']!='accepted' and not (r['quality']=='QC2_pending' and qa):continue
        if r['bucket'] not in effective or int(r['revision'])>int(effective[r['bucket']]['revision']):effective[r['bucket']]=r
    return any(int(r['visits'])>10 for r in effective.values())

def solve(data,answers):
    possibilities={trigger(data,q) for q in [False,True]}
    yes=next(iter(possibilities)) if len(possibilities)==1 else trigger(data,fact(data,'qa',answers))
    target=fact(data,'recipient',answers)
    matches=[r for r in data['contacts.csv'] if r['contact']==target]
    if len(matches)!=1:raise NeedFact('Contact identity')
    owner=matches[0]['email']
    if not yes:
        aliases={r['alias']:r['employee'] for r in data['people_aliases.csv']}
        leads=sorted(r['id'] for r in data['crm.csv']+data.get('crm_archive.csv',[]) if aliases[r['owner']]=='NADIA'
                     and r['record_type']=='lead' and str(r['deleted'] or fact(data,'lead_state',answers))=='0')
        return dict(branch='email_then_transfer',owner=owner,sequence=['email']+['transfer:'+k for k in leads],crm_updates=leads,subject='New leads for you',body='total visits looks good, so there are new leads for you')
    workspace=fact(data,'workspace',answers)
    boards=[r for r in data['boards.csv'] if r['name']=='Front end' and r['archived']=='0' and r['list']=='Backlog' and r['workspace']==workspace]
    if len(boards)!=1:raise NeedFact('Active board identity')
    _,tomorrow,due=dates(data);context=data['operation_context.json']
    events=[r for r in data['calendar.csv']+data.get('calendar_history.csv',[]) if r['owner']=='self' and r['day']==tomorrow]
    for start in range(context['working_start'],context['working_end']-29):
        busy=False
        for r in events:
            if r['status']=='cancelled' or start+30<=int(r['start']):continue
            end=int(r['end']) if r['end'] else fact(data,'busy_end',answers)
            if start>=end:continue
            status=r['status'] or fact(data,'calendar_state',answers)
            if status in {'confirmed','tentative'}:busy=True;break
        if not busy:break
    else:raise NeedFact('No available half-hour')
    return dict(branch='task_and_meeting',owner=owner,board=boards[0]['id'],list='Backlog',task='Improve total visits',due=due,
        meeting='Discuss total visits',start=start,end=start+30,crm_updates=[],emails=[])
