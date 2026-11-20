"""Validate submitted simulated SQLite state, never mutate inputs."""
from pathlib import Path
import csv,json,sqlite3,hashlib
from .jb29_evidence import snapshot,PACKET

def check_state(output,variant):
 source=PACKET/'variants'/variant/'inputs/dispatch_cad.db';before=hashlib.sha256(source.read_bytes()).hexdigest();old=snapshot(source);checks={};details={}
 try:
  new=snapshot(output);con=sqlite3.connect('file:'+str(Path(output).resolve())+'?mode=ro&immutable=1',uri=True);checks['sqlite_integrity']=con.execute('pragma integrity_check').fetchone()[0]=='ok'
  con.row_factory=sqlite3.Row;extras={}
  for row in con.execute("select name from sqlite_master where type='table'"):
   name=row[0]
   if name not in old and not name.startswith('sqlite_'):
    quoted='"'+name.replace('"','""')+'"';extras[name]=[dict(r) for r in con.execute('select * from '+quoted+' limit 1001')]
  details['additional_link_or_audit_tables']=extras;con.close()
 except Exception as e:return dict(status='fail',checks=dict(readable_sqlite=False),error=str(e))
 calls=list(csv.DictReader((source.parent/'incoming_calls_queue.csv').open()));expected={r['call_id'] for r in old['call_records']+calls};actual={r.get('call_id') for r in new['call_records']}
 checks['all_fifteen_inserted_once']=actual==expected and len(new['call_records'])==len(expected)
 fields=['call_id','call_received_time','caller_phone','caller_name','incident_type','incident_category','location_address','location_lat','location_lng','caller_description']
 found={r.get('call_id'):r for r in new['call_records']};bad=[]
 for q in calls:
  row=found.get(q['call_id'],{})
  for k in fields:
   if k in ['location_lat','location_lng']:
    try:match=abs(float(row.get(k))-float(q[k]))<1e-7
    except Exception:match=False
   else:match=str(row.get(k,''))==str(q.get(k,''))
   if not match:bad.append([q['call_id'],k])
 checks['new_call_source_fields_preserved']=not bad;details['changed_new_call_fields']=bad
 changes=[];missing=[]
 mutable={'call_records':{'status','updated_at'},'unit_assignments':{'clear_time','status','notes'},'dispatch_log':{'clear_time','disposition','notes'}}
 forbidden=[]
 for table,key in [('call_records','record_id'),('unit_assignments','assignment_id'),('dispatch_log','log_id')]:
  index={r.get(key):r for r in new[table]}
  for r in old[table]:
   if r[key] not in index:missing.append([table,r[key]]);continue
   for col,val in r.items():
    if index[r[key]].get(col)!=val:
     item=dict(table=table,key=r[key],column=col,before=val,after=index[r[key]].get(col));changes.append(item)
     if col not in mutable[table] or (col=='clear_time' and val is not None) or (col=='status' and val in ['COMPLETED','CLEARED']):forbidden.append(item)
 checks['existing_history_preserved']=not missing and not forbidden
 details.update(missing_original_records=missing,existing_state_changes=changes,forbidden_history_changes=forbidden)
 checks['no_orphan_assignment_or_log']=all(r.get('call_id') in actual and r.get('unit_id') for t in ['unit_assignments','dispatch_log'] for r in new[t])
 assignments=new['unit_assignments'];active={}
 for a in assignments:
  if not a.get('clear_time') and a.get('status') not in ['CLEARED','CANCELLED','PENDING','REQUESTED','AWAITING','STAGED']:active.setdefault(str(a.get('unit_id')),set()).add(str(a.get('call_id')))
 details['multiple_active_call_links']={u:sorted(ids) for u,ids in active.items() if len(ids)>1}
 details['link_review']='Multiple call links may represent a documented shared physical response. Judge relation identity and simultaneous commitments; do not impose one-unit-one-report when linked reports describe one event.'
 canonical=json.loads((PACKET/'MANIFEST.json').read_text())[variant]['inputs/dispatch_cad.db']
 checks['source_matches_manifest']=before==canonical
 checks['source_db_unchanged']=hashlib.sha256(source.read_bytes()).hexdigest()==before
 return dict(status='pass' if all(checks.values()) else 'fail',checks=checks,details=details,submitted_state=new,source_sha256=before,output_sha256=hashlib.sha256(Path(output).read_bytes()).hexdigest(),scope='Actual SQLite records/integrity, original history, source immutability and link diagnostics; dispatch feasibility judged semantically.')
