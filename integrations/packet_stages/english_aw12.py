"""AW12 visible backup integrity and selected-set catalog matching."""
import csv,hashlib,json
from .english_packet import inputs
class NeedFact(Exception):pass

def load(variant):
    data={'digests':{}}
    for p in inputs('AW12',variant).iterdir():
        raw=p.read_bytes()
        if p.suffix=='.csv':
            with p.open(newline='') as f:data[p.name]=list(csv.DictReader(f))
        elif p.suffix=='.json':data[p.name]=json.loads(raw)
        else:data[p.name]=raw.decode()
        if p.name.startswith('export_'):data['digests'][p.name]=hashlib.sha256(raw).hexdigest()
    return data

def observed(data):
    identity=data.get('case_decision.md','');names=[name for name in ['export_A.json','export_B.json'] if name in identity]
    a=data['export_A.json']
    return dict(batch=names[0] if len(names)==1 else None,
        s2_duration=next(s['duration'] for s in a['songs'] if s['old']=='s2'),
        road_private=next(p['private'] for p in a['playlists'] if p['name']=='Road Trip'))

def fact(data,key,answers):
    value=observed(data)[key]
    if value is not None:return value
    records=[r for r in data.get('source_records.json',[]) if r['fact']==key]
    if records:
        top=max(r['revision'] for r in records);values={r['value'] for r in records if r['revision']==top}
        if len(values)==1:return next(iter(values))
    if key not in answers:raise NeedFact(key)
    return answers[key]

def integrity(data,name):
    rows=[r for r in data['manifest.csv'] if r['file']==name]
    if len(rows)!=1 or rows[0]['complete']!='1' or data['digests'][name]!=rows[0]['sha256']:
        raise ValueError('Backup delivery integrity check failed')
    return data['digests'][name]

def solve(data,answers):
    batch=fact(data,'batch',answers);integrity(data,batch);source=data[batch];mapping={}
    for song in source['songs']:
        duration=fact(data,'s2_duration',answers) if source['backup_set']=='A' and song['old']=='s2' else song['duration']
        matches=[r for r in data['track_catalog.csv']+data.get('recording_search.csv',[])
                 if r['isrc']==song['isrc'] and abs(int(r['duration'])-duration)<=2]
        if len(matches)!=1:raise NeedFact('Recording identity')
        mapping[song['old']]=matches[0]['track']
    albums=[]
    for upc in source['albums']:
        matches=[r for r in data['albums.csv']+data.get('album_search.csv',[]) if r['upc']==upc]
        if len(matches)!=1:raise NeedFact('Album identity')
        albums.append(matches[0]['album'])
    playlists=[]
    for playlist in source['playlists']:
        private=fact(data,'road_private',answers) if source['backup_set']=='A' and playlist['name']=='Road Trip' else playlist['private']
        extra=data.get('playlist_archive.json')
        if extra and extra['backup_set']==source['backup_set'] and extra['name']==playlist['name'] and extra['private']!=private:
            raise NeedFact('Playlist privacy')
        playlists.append(dict(name=playlist['name'],private=private,tracks=list(dict.fromkeys(mapping[t] for t in playlist['tracks']))))
    return dict(songs=sorted(set(mapping.values())),albums=list(dict.fromkeys(albums)),playlists=playlists)
