"""WB02 eligible staff, logical workload and lead tie-breaks."""
import csv,json
from .english_packet import inputs
class NeedFact(Exception):pass

def load(variant):
    data={}
    for p in inputs('WB02',variant).iterdir():
        if p.suffix=='.csv':
            with p.open(newline='') as f:data[p.name]=list(csv.DictReader(f))
        elif p.suffix=='.json':data[p.name]=json.loads(p.read_text())
        else:data[p.name]=p.read_text()
    return data

def observed(data):
    y=next(r for r in data['employees.csv'] if r['employee']=='Y')
    c=next(r for r in data['employees.csv'] if r['employee']=='C');note=data.get('case_decision.md','')
    same=True if 'the same actual task.' in note else False if 'two independent tasks.' in note else None
    return dict(eligible_y=int(y['eligible']) if y['eligible'] else None,same_task=same,c_last_lead=c['last_lead'] or None)

def fact(data,key,answers):
    raw=observed(data)[key]
    if raw is not None:return raw
    records=data.get('migration_adjudications.json' if key=='same_task' else key+'_records.json',[])
    field='same_task' if key=='same_task' else 'value'
    if records:
        top=max(r['revision'] for r in records);values={r[field] for r in records if r['revision']==top}
        if len(values)==1:return next(iter(values))
    if key not in answers:raise NeedFact(key)
    return answers[key]

def aliases(data):
    result={r['email']:r['employee'] for r in data['employees.csv']}
    for r in data['owner_aliases.csv']+data.get('owner_alias_copy.csv',[]):
        if r['alias'] in result and result[r['alias']]!=r['employee']:raise ValueError('Ambiguous owner alias')
        result[r['alias']]=r['employee']
    return result

def solve(data,answers):
    staff=[r for r in data['employees.csv'] if (fact(data,'eligible_y',answers) if r['employee']=='Y' else int(r['eligible']))==1]
    if not staff:raise ValueError('No eligible staff')
    owners=aliases(data);tasks={r['employee']:set() for r in staff}
    same=fact(data,'same_task',answers) if 'Y' in tasks else False
    for r in data['assigned_tasks.csv']+data.get('closed_tasks.csv',[])+data.get('unavailable_staff_tasks.csv',[]):
        owner=owners[r['owner']]
        if owner in tasks and r['status'] not in {'completed','cancelled'}:
            tasks[owner].add('T17' if same and r['task']=='T18' else r['task'])
    counts={k:len(v) for k,v in tasks.items()};minimum=min(counts.values())
    tied=[r for r in staff if counts[r['employee']]==minimum]
    chosen=tied[0] if len(tied)==1 else min(tied,key=lambda r:(r['last_lead'] or fact(data,'c_last_lead',answers),r['employee']))
    return dict(counts=counts,lead='Reese Martinez',assign_to=chosen['email'])
