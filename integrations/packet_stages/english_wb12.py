"""WB12 valid low observations, deletion scope and exact original notification."""
import csv,json
from decimal import Decimal
from .english_packet import inputs
class NeedFact(Exception):pass
LOW_BODY='engaged users looks good, so we no longer need you finding new leads'
HIGH_BODY='We need you to improve engaged users - TBD.'

def load(variant):
    data={}
    for p in inputs('WB12',variant).iterdir():
        if p.suffix=='.csv':
            with p.open(newline='') as f:data[p.name]=list(csv.DictReader(f))
        elif p.suffix=='.json':data[p.name]=json.loads(p.read_text())
        else:data[p.name]=p.read_text()
    return data

def observed(data):
    note=data.get('case_decision.md','')
    quality=False if 'missing-data placeholder.' in note else True if 'genuine zero observation.' in note else None
    return dict(measurement=quality,l2_owner=next(r['owner'] for r in data['crm.csv'] if r['id']=='L2') or None,
        l5_deleted=next(r['deleted'] for r in data['crm.csv'] if r['id']=='L5') or None)

def fact(data,key,answers):
    value=observed(data)[key]
    if value is not None:return value
    records=[r for r in data.get('source_records.json',[]) if r['fact']==key]
    if records:
        top=max(r['revision'] for r in records);values={r['value'] for r in records if r['revision']==top}
        if len(values)==1:return next(iter(values))
    if key not in answers:raise NeedFact(key)
    return answers[key]

def raw_records(data):return data['crm.csv']+data.get('other_owner_leads.csv',[])+data.get('crm_history.csv',[])

def triggered(data,answers):
    today=data['operation_context.json']['snapshot_date'];since=today[:4]+'-11-06'
    low=[r for r in data['engaged_users.csv']+data.get('gap_fill_samples.csv',[]) if since<=r['day']<=today and Decimal(r['value'])<1]
    if any(r['quality']=='accepted' for r in low):return True
    return bool(any(r['sample']=='Z7' for r in low) and fact(data,'measurement',answers))

def solve(data,answers):
    people=[r for r in data['people.json'] if r['name']=='Raj Patel']
    if len(people)!=1:raise NeedFact('Notification identity')
    person=people[0];yes=triggered(data,answers);deleted=[]
    if yes:
        aliases={r['email']:r['employee'] for r in data['owner_aliases.csv']}
        for row in raw_records(data):
            if row['record_type']!='lead' or row['deleted']=='1':continue
            owner=row['owner'] or fact(data,'l2_owner',answers)
            if aliases[owner]!=person['employee']:continue
            state=row['deleted'] or fact(data,'l5_deleted',answers)
            if state=='0':deleted.append(row['id'])
    deleted.sort()
    return dict(delete=deleted,sequence=['delete:'+k for k in deleted]+['email'],to=person['email'],subject='Reprioritising',body=LOW_BODY if yes else HIGH_BODY)
