"""Run submitted SQL only on a disposable copy of the selected input DB."""
import sqlite3,shutil,tempfile,hashlib
from pathlib import Path
from .jb24_evidence import PACKET
def execute(script,private_root,variant):
 source=PACKET/'variants'/variant/'inputs/workload_requirements.db';before=hashlib.sha256(source.read_bytes()).hexdigest();results=[];error=None
 with tempfile.TemporaryDirectory(prefix='sql-',dir=private_root) as td:
  copied=Path(td)/'workload.db';shutil.copyfile(source,copied);c=sqlite3.connect(copied)
  def authorize(action,a,b,db,trigger):
   if action in (sqlite3.SQLITE_ATTACH,sqlite3.SQLITE_DETACH):return sqlite3.SQLITE_DENY
   if action==sqlite3.SQLITE_PRAGMA and (a or '').lower() not in ('table_info','table_xinfo','index_list','index_info','foreign_key_list'):return sqlite3.SQLITE_DENY
   if action==sqlite3.SQLITE_CREATE_VTABLE:return sqlite3.SQLITE_DENY
   if action==sqlite3.SQLITE_FUNCTION and (b or '').lower() in ('load_extension','readfile','writefile'):return sqlite3.SQLITE_DENY
   return sqlite3.SQLITE_OK
  c.set_authorizer(authorize);ticks=[0]
  def progress():ticks[0]+=1;return ticks[0]>20000
  c.set_progress_handler(progress,1000)
  try:
   pending=''
   for char in Path(script).read_text():
    pending+=char
    if char==';' and sqlite3.complete_statement(pending):
     cur=c.execute(pending)
     if cur.description:results.append(dict(columns=[x[0] for x in cur.description],rows=cur.fetchmany(1001)))
     pending=''
   if pending.strip():
    cur=c.execute(pending)
    if cur.description:results.append(dict(columns=[x[0] for x in cur.description],rows=cur.fetchmany(1001)))
   if not results:
    for (name,) in c.execute("select name from sqlite_master where type='view'").fetchall():
     cur=c.execute('SELECT * FROM "'+name.replace('"','""')+'"');results.append(dict(view=name,columns=[x[0] for x in cur.description],rows=cur.fetchmany(1001)))
  except Exception as exc:error=type(exc).__name__+': '+str(exc)
  finally:c.close()
 assert hashlib.sha256(source.read_bytes()).hexdigest()==before
 return dict(status='executed' if error is None and results else 'fail',error=error,result_sets=results,source_sha256=before,source_unchanged=True,scope='SQL runtime and result evidence; semantic correctness judged separately')
