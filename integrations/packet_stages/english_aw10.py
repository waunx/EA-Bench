"""AW10 liked/library intersection and bounded draft replacement."""
import csv,json
from .english_packet import inputs

class NeedFact(Exception):pass

def load(variant):
    data={}
    for p in inputs('AW10',variant).iterdir():
        if p.suffix=='.csv':
            with p.open(newline='') as f:data[p.name]=list(csv.DictReader(f))
        elif p.suffix=='.json':data[p.name]=json.loads(p.read_text())
        else:data[p.name]=p.read_bytes().decode()
    return data

def observed(data):
    active=next(r['active'] for r in data['liked.csv'] if r['track']=='T6')
    return dict(merge=True if data.get('case_decision.md') else None,
        harbor_liked=active=='1' if active else None,
        t2_isrc=next(r['isrc'] for r in data['songs.csv'] if r['track']=='T2') or None)

def fact(data,key,answers):
    value=observed(data)[key]
    if value is not None:return value
    records=[r for r in data.get('source_records.json',[]) if r['fact']==key]
    if records:
        top=max(r['revision'] for r in records)
        values={r['value'] for r in records if r['revision']==top}
        if len(values)==1:return next(iter(values))
    if key not in answers:raise NeedFact(key)
    return answers[key]

def solve(data,answers):
    songs=data['songs.csv']+data.get('catalog_search.csv',[])
    if len({r['track'] for r in songs})!=len(songs):raise ValueError('Catalogue track identity collision')
    catalogue={r['track']:r for r in songs}
    library={r['track'] for r in data['library.csv']+data.get('guest_library.csv',[])+data.get('library_copy.csv',[])
             if r.get('account','self')=='self'}
    liked={r['track'] for r in data['liked.csv'] if
           (fact(data,'harbor_liked',answers) if r['track']=='T6' else r['active']=='1')}
    tracks=sorted(library&liked)
    try:merge=fact(data,'merge',answers)
    except NeedFact:
        if fact(data,'t2_isrc',answers) not in {catalogue[t]['isrc'] for t in tracks if t!='T2'}:merge=False
        else:raise NeedFact('merge')
    if merge:
        groups={}
        for track in tracks:
            row=catalogue[track];isrc=fact(data,'t2_isrc',answers) if track=='T2' else row['isrc']
            key=(int(row['year']),track)
            if isrc not in groups or key < groups[isrc]:groups[isrc]=key
        tracks=sorted(v[1] for v in groups.values())
    draft=data['mail_draft.eml'];start=draft.index('<SONGS>')+len('<SONGS>');end=draft.index('</SONGS>')
    message=draft[:start]+'\n'+'\n'.join('- '+catalogue[t]['title'] for t in tracks)+'\n'+draft[end:]
    return dict(tracks=tracks,message=message)
