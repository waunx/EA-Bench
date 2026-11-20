"""Selected dispatch sources and numeric controls; hidden worlds ignored."""
from pathlib import Path
from collections import Counter,defaultdict
from functools import lru_cache
import csv,json,math,sqlite3,hashlib
from .artifact_adapter_jb29 import PACKET,REF

def distance(a,b,c,d):
 a,b,c,d=map(math.radians,[float(a),float(b),float(c),float(d)])
 return 12742*math.asin(math.sqrt(math.sin((c-a)/2)**2+math.cos(a)*math.cos(c)*math.sin((d-b)/2)**2))
def snapshot(path):
 c=sqlite3.connect('file:'+str(Path(path).resolve())+'?mode=ro&immutable=1',uri=True);c.row_factory=sqlite3.Row
 try:return {t:[dict(r) for r in c.execute('select * from '+t)] for t in ['call_records','unit_assignments','dispatch_log']}
 finally:c.close()

@lru_cache(maxsize=1)
def historical():
 title=Counter();category=Counter();twp=Counter();hour=Counter();month=Counter();tc=Counter();geo=defaultdict(lambda:[0,0.,0.]);invalid=Counter();n=0;lo=hi=None
 with REF.open() as f:
  for r in csv.DictReader(f):
   n+=1;t=r.get('title','');title[t]+=1;cat=t.split(':')[0].strip();category[cat]+=1;town=r.get('twp') or '(missing)';twp[town]+=1;tc[(town,cat)]+=1;stamp=r.get('timeStamp','')
   if len(stamp)>=13:hour[stamp[11:13]]+=1;month[stamp[:7]]+=1;lo=min(lo,stamp) if lo else stamp;hi=max(hi,stamp) if hi else stamp
   else:invalid['timestamp']+=1
   try:
    lat=float(r['lat']);lng=float(r['lng'])
    if not (39<=lat<=42 and -77<=lng<=-74):invalid['coordinates_outside_broad_PA_region']+=1;continue
    g=geo[town];g[0]+=1;g[1]+=lat;g[2]+=lng
   except Exception:invalid['coordinates_unparseable']+=1
 return dict(rows=n,date_min=lo,date_max=hi,categories=dict(category),top_types=title.most_common(15),townships=dict(twp),hours=dict(sorted(hour.items())),months=dict(sorted(month.items())),township_categories=[dict(township=t,category=c,count=v) for (t,c),v in tc.most_common()],centroids={t:dict(valid_coordinate_rows=g[0],mean_lat=g[1]/g[0],mean_lng=g[2]/g[0]) for t,g in geo.items()},data_quality=dict(invalid),sha256=hashlib.sha256(REF.read_bytes()).hexdigest(),scope='All supplied full Kaggle rows; counts retain coordinate outliers. Centroids exclude coordinates outside broad PA region39-42lat/-77--74lng. Counts/centroids are descriptive, not risk-normalized causal clusters or DC demand forecasts.')

def build(variant,world=None,clarification_records=None):
 p=PACKET/'variants'/variant/'inputs';calls=list(csv.DictReader((p/'incoming_calls_queue.csv').open()));units=list(csv.DictReader((p/'unit_status.csv').open()));cad=snapshot(p/'dispatch_cad.db');stations=json.loads((p/'dc_fire_stations.geojson').read_text())
 e1=next(r for r in units if r['unit_id']=='E1');facts=dict(e1_status=e1['current_status'] or None,e1_position=e1['current_location_lat']+','+e1['current_location_lng'] if e1['current_location_lat'] and e1['current_location_lng'] else None)
 for record in clarification_records or []:
  for item in record.get('provided',[]):
   if item['fact_id'] in facts:facts[item['fact_id']]=item['value']
 e1['current_status']=facts['e1_status']
 e1['current_location_lat'],e1['current_location_lng']=facts['e1_position'].split(',') if facts['e1_position'] else (None,None)
 busy=defaultdict(list)
 for a in cad['unit_assignments']:
  if not a['clear_time'] and a['status'] not in ['CLEARED','CANCELLED']:busy[a['unit_id']].append(a)
 by_b=defaultdict(lambda:dict(total=0,raw_available=0,effective_available=0,unknown=0,units=[]));conflicts=[];matrix={}
 for u in units:
  g=by_b[u['battalion']];g['total']+=1;g['units'].append(u['unit_id']);g['raw_available']+=u['current_status']=='AVAILABLE';g['unknown']+=u['current_status'] is None
  u['effective_available']=None if u['current_status'] is None else u['current_status']=='AVAILABLE' and u['unit_id'] not in busy
  g['effective_available']+=u['effective_available'] is True
  if u['current_status']=='AVAILABLE' and u['unit_id'] in busy:conflicts.append(dict(unit=u['unit_id'],csv_status=u['current_status'],cad_assignments=busy[u['unit_id']]))
 role_types={'ALS':lambda u:u['unit_type']=='Medic Unit' and u['specialty']=='ALS','BLS':lambda u:u['unit_type']=='Ambulance','Engine':lambda u:u['unit_type']=='Engine','Truck':lambda u:u['unit_type']=='Truck','Rescue':lambda u:u['unit_type']=='Rescue Squad','Command':lambda u:u['unit_type']=='Battalion Chief','HazMat':lambda u:u['specialty']=='HazMat','SwiftWater':lambda u:u['specialty']=='Swift Water Rescue'}
 roles={1:['ALS','Engine'],2:['Engine','Truck','Command'],3:['ALS','Rescue'],4:['HazMat','Engine','ALS'],5:['ALS'],6:['BLS'],7:['Engine'],8:['ALS'],9:['Engine'],10:['ALS'],11:['Engine'],12:['BLS','ALS'],13:['SwiftWater','Rescue'],14:['ALS'],15:['Engine']}
 for call in calls:
  n=int(call['call_id'][-3:]);candidate={}
  for role in roles[n]:
   options=[]
   for u in units:
    if not role_types[role](u):continue
    lat,lng=u['current_location_lat'],u['current_location_lng'];dist=distance(lat,lng,call['location_lat'],call['location_lng']) if lat and lng else None
    options.append(dict(unit=u['unit_id'],distance_km=dist,available=u['effective_available']))
   candidate[role]=dict(capable=[o['unit'] for o in options],closest_available=sorted([o for o in options if o['available'] and o['distance_km'] is not None],key=lambda o:o['distance_km'])[:5],unknown=[o for o in options if o['available'] is None or o['distance_km'] is None])
  matrix[call['call_id']]=candidate
 for b,g in by_b.items():
  g['effective_available_pct']=100*g['effective_available']/g['total'];g['upper_available_pct']=100*(g['effective_available']+g['unknown'])/g['total']
 related=[]
 existing=cad['call_records']
 for call in calls:
  for other in existing+calls:
   if call['call_id']==other['call_id'] or (other in calls and other['call_id']<call['call_id']):continue
   d=distance(call['location_lat'],call['location_lng'],other['location_lat'],other['location_lng'])
   same=call['location_address'].lower()==other['location_address'].lower()
   if d<.3 or same:related.append(dict(new=call['call_id'],other=other['call_id'],km=d,exact_address=same,other_address=other['location_address'],other_status=other['status'],note='Proximity alone is not duplicate identity; compare event/address/caller and current status.'))
 specialty={r:dict(capable=[u['unit_id'] for u in units if f(u)],available=[u['unit_id'] for u in units if f(u) and u['effective_available']]) for r,f in role_types.items()}
 return dict(facts=facts,calls=calls,units=units,stations=stations,cad=cad,cad_sha256=hashlib.sha256((p/'dispatch_cad.db').read_bytes()).hexdigest(),busy_assignments=dict(busy),status_discrepancies=conflicts,battalions=dict(by_b),candidate_controls=matrix,specialty=specialty,nearby_review_pairs=related,historical=historical(),supplements={f.name:json.loads(f.read_text()) for f in p.glob('*.json')},limits='Station locations are not proof of current E1 position. No E1 CAD assignment is not proof of availability. No shift roster/end times supplied: no invented end-of-shift facts. Distances are haversine straight-line km, not road ETA. Candidate rankings are independent per call; globally deconflict simultaneous assignments. No selected hidden-world defaults.')
