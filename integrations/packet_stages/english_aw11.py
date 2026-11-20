"""AW11 scoped affirmative recommendation union and preserved follows."""
import csv,json
from .english_packet import inputs
class NeedFact(Exception):pass

def load(variant):
    data={}
    for p in inputs('AW11',variant).iterdir():
        if p.suffix=='.csv':
            with p.open(newline='') as f:data[p.name]=list(csv.DictReader(f))
        elif p.suffix=='.json':data[p.name]=json.loads(p.read_text())
        else:data[p.name]=p.read_text()
    return data

def observed(data):
    scope=next(r['in_scope'] for r in data['roster.csv'] if r['sender']=='P3')
    active=next(r['active'] for r in data['following.csv'] if r['artist']=='A2')
    identity=data.get('case_decision.md','')
    names=[code for name,code in [('Alex Park','X1'),('Alex Vale','X2')] if name in identity]
    return dict(alex=names[0] if len(names)==1 else None,
                p3_scope=scope=='1' if scope else None,a2_followed=active=='1' if active else None)

def fact(data,key,answers):
    value=observed(data)[key]
    if value is not None:return value
    records=[r for r in data.get('source_records.json',[]) if r['fact']==key]
    if records:
        top=max(r['revision'] for r in records);values={r['value'] for r in records if r['revision']==top}
        if len(values)==1:return next(iter(values))
    if key not in answers:raise NeedFact(key)
    return answers[key]

def current(data,answers):
    active={r['artist'] for r in data['following.csv'] if
            (fact(data,'a2_followed',answers) if r['artist']=='A2' else r['active']=='1')}
    for r in data.get('following_copy.csv',[]):
        if (r['artist'] in active)!=(r['active']=='1'):raise NeedFact('Follow snapshot disagreement')
    return active

def solve(data,answers):
    scopes={r['sender']:fact(data,'p3_scope',answers) if r['sender']=='P3' else r['in_scope']=='1' for r in data['roster.csv']}
    artists={r['name']:r['artist'] for r in data['artist_catalog.csv']+data.get('extra_artists.csv',[])}
    wanted=set()
    for r in data['recommendations.csv']+data.get('extra_recommendations.csv',[])+data.get('music_promotion.csv',[]):
        if not scopes[r['sender']] or not r['text'].startswith('Recommend:'):continue
        for name in r['text'].split(':',1)[1].rstrip('.').split(';'):
            name=name.strip();wanted.add(fact(data,'alex',answers) if name=='Alex' else artists[name])
    active=current(data,answers)
    return dict(add=sorted(wanted-active),final=sorted(wanted|active),unfollow=[])
