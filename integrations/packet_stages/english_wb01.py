"""WB01 recent contact, earliest free half-hour and effective responsibility."""
import csv,json
from datetime import date,timedelta
from .english_packet import inputs
class NeedFact(Exception):pass

def load(variant):
    data={}
    for p in inputs('WB01',variant).iterdir():
        if p.suffix=='.csv':
            with p.open(newline='') as f:data[p.name]=list(csv.DictReader(f))
        elif p.suffix=='.json':data[p.name]=json.loads(p.read_text())
        else:data[p.name]=p.read_text()
    return data

def observed(data):
    note=data.get('case_decision.md','')
    connected=False if 'did not connect.' in note else True if 'connected.' in note else None
    end=next(r['end'] for r in data['calendar.csv'] if r['owner']=='self' and r['start']=='615')
    boundary=next(r['from'] for r in data['owner_history.csv'] if r['email']=='akira.sato@atlas.com')
    return dict(connected=connected,busy_end=int(end) if end else None,handover=boundary or None)

def fact(data,key,answers):
    value=observed(data)[key]
    if value is not None:return value
    records=[r for r in data.get('source_records.json',[]) if r['fact']==key]
    if records:
        top=max(r['revision'] for r in records);values={r['value'] for r in records if r['revision']==top}
        if len(values)==1:return next(iter(values))
    if key not in answers:raise NeedFact(key)
    return answers[key]

def dates(data):
    today=date.fromisoformat(data['calendar_context.json']['snapshot_date'])
    return today.isoformat(),(today-timedelta(days=14)).isoformat(),(today+timedelta(days=1)).isoformat()

def solve(data,answers):
    today,since,tomorrow=dates(data)
    customers=[r['customer'] for r in data['customer_directory.csv'] if r['name']=='Cameron Anderson' and r['company']=='Acme']
    if len(customers)!=1:raise NeedFact('Customer identity')
    customer=customers[0]
    events=[r for r in data['contact_events.csv']+data.get('campaign_events.csv',[])
            if r['customer']==customer and r['kind']=='conversation' and since<=r['date']<=today]
    if any(r['result']=='connected' for r in events):return dict(events=[])
    if any(r['event']=='CALL7' for r in events) and fact(data,'connected',answers):return dict(events=[])
    owners=[]
    for row in data['owner_history.csv']+data.get('owner_archive.csv',[]):
        start=row['from'] or fact(data,'handover',answers);end=row['to'] or fact(data,'handover',answers)
        if row['customer']==customer and start<=tomorrow<end:owners.append(row['email'])
    if len(owners)!=1:raise NeedFact('Active responsibility interval')
    busy=[]
    for row in data['calendar.csv']+data.get('calendar_copy.csv',[]):
        if row['owner']=='self' and row['day']==tomorrow:
            end=int(row['end']) if row['end'] else fact(data,'busy_end',answers)
            busy.append((int(row['start']),end))
    context=data['calendar_context.json']
    candidates=[x for x in range(context['working_start'],context['working_end']-29) if all(x+30<=a or x>=b for a,b in busy)]
    if not candidates:raise NeedFact('No available half-hour')
    start=candidates[0]
    return dict(events=[dict(to=owners[0],start=start,end=start+30,title='Update on Cameron Anderson')])
