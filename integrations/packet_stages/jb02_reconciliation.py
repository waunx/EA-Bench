"""JB02 isolated submitted execution and source-grounded conditional reconciliation.

Exact table/column conventions are diagnostics, not a hidden output schema.
Unmapped conventions must be reconciled by the mandatory semantic judge.
"""
from pathlib import Path
import json, shutil, tempfile, math, sqlite3, hashlib
from .artifact_sandbox import execute
from .native import artifact_hashes
from .author_english_jb02 import PACKET, REFERENCE_ROOT, ROOT
from .jb01_reconciliation import cells, numerical_rows

def verify_references(variant):
 records=json.loads((PACKET/'variants'/variant/'inputs/reference_sources.json').read_text());paths={}
 for record in records:
  source=REFERENCE_ROOT/record['file'] if record['file'].endswith('.csv') else ROOT/'data/references/JB02'/record['file']
  if hashlib.sha256(source.read_bytes()).hexdigest()!=record['sha256']:raise RuntimeError('Public reference integrity failure: '+record['file'])
  paths[record['file']]=source
 return paths

def database_evidence(path,expected):
 import pandas as pd
 report=[];tables={};hard=[]
 with sqlite3.connect('file:'+str(path.resolve())+'?mode=ro',uri=True) as db:
  for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'"):
   escaped='"'+name.replace('"','""')+'"'
   frame=pd.read_sql_query('SELECT * FROM '+escaped,db)
   tables[name]=dict(columns=list(frame.columns),rows=len(frame),sample=frame.head(8).to_dict('records'),indexes=db.execute('PRAGMA index_list('+escaped+')').fetchall())
   fips=next((c for c in frame if c.lower() in ['fips','county_fips','geoid']),None)
   tables[name]['detected_fips_column']=fips
   tables[name]['fips_indexed']=bool(fips and any(fips in [row[2] for row in db.execute('PRAGMA index_info('+chr(34)+idx[1].replace(chr(34),chr(34)*2)+chr(34)+')')] for idx in tables[name]['indexes']))
   if fips is None:continue
   tables[name]['unique_fips']=int(frame[fips].nunique());tables[name]['duplicate_fips']=int(frame[fips].duplicated().sum())
   frame=frame.set_index(fips);frame.index=frame.index.astype(str).str.zfill(5)
   for expected_name,source in expected.items():
    common=[c for c in source.columns if c in frame.columns]
    if not common:continue
    mismatches=[];compared=0
    for f in frame.index.unique().intersection(source.index):
     if frame.index.duplicated().any():break
     for col in common:
      x,y=frame.loc[f,col],source.loc[f,col];compared+=1
      try:equal=math.isclose(float(x),float(y),rel_tol=1e-8,abs_tol=1e-8)
      except (TypeError,ValueError):equal=str(x)==str(y)
      if not equal and len(mismatches)<25:mismatches.append(dict(fips=f,column=col,submitted=str(x),source=str(y)))
    record=dict(table=name,source_table=expected_name,columns=common,compared=compared,mismatches=mismatches,duplicate_fips=bool(frame.index.duplicated().any()),conditional=True)
    report.append(record)
    if expected_name=='health_outcomes' and compared:hard.append(not mismatches and not record['duplicate_fips'])
 return dict(tables=tables,comparisons=report,source_health_values_consistent=all(hard) if hard else None)

CAPTURE = '''
import json as _audit_json
import pandas as _audit_pd
_audit_tables=[];_audit_seen=set()
def _audit_walk(name,value,depth=0):
 if id(value) in _audit_seen or depth>3 or len(_audit_tables)>=150:return
 _audit_seen.add(id(value))
 if isinstance(value,(_audit_pd.DataFrame,_audit_pd.Series)):
  if isinstance(value,_audit_pd.Series):value=value.to_frame()
  if len(value)<=10000 and len(value.columns)<=100:
   _audit_tables.append(dict(name=name,table=_audit_json.loads(value.to_json(orient='split',default_handler=str))))
 elif isinstance(value,dict):
  for key,item in list(value.items()):_audit_walk(name+'.'+str(key),item,depth+1)
for _audit_name,_audit_value in list(globals().items()):
 if not _audit_name.startswith('_'):_audit_walk(_audit_name,_audit_value)
with open('/workspace/_audit_tables.json','w') as _audit_f:_audit_json.dump(_audit_tables,_audit_f)
'''

def replay(artifacts,private,variant,references):
 import nbformat
 records=[];rebuilt={};tables=[];executed=[]
 for i,notebook in enumerate([artifacts/'reconciliation_models.ipynb']):
  attempts=[]
  for mode in ['notebook_directory','workspace_directory']:
   with tempfile.TemporaryDirectory(prefix='jb02-replay-') as temp:
    work=Path(temp);out=work/'output';out.mkdir()
    for source in artifacts.rglob('*'):
     if source.is_symlink():raise ValueError('Submitted symlink')
     if not source.is_file() or source.suffix.lower() in {'.xls','.pdf','.xlsx','.png'}:continue
     # Do not seed derived deliverables into the replay.
     target=out/source.relative_to(artifacts);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
     target=work/source.relative_to(artifacts);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
     if source.suffix.lower()=='.ipynb':
      support=nbformat.read(source,as_version=4)
      for c in support.cells:
       if c.cell_type=='code':c.outputs=[];c.execution_count=None
      for dest in [out/source.relative_to(artifacts),work/source.relative_to(artifacts)]:nbformat.write(support,dest)
    target=out/notebook.relative_to(artifacts);target.parent.mkdir(parents=True,exist_ok=True)
    nb=nbformat.read(notebook,as_version=4)
    for cell in nb.cells:
     if cell.cell_type=='code':cell.outputs=[];cell.execution_count=None
    kernel=nb.metadata.get('kernelspec',{}).get('name','python3')
    language=nb.metadata.get('language_info',{}).get('name',nb.metadata.get('kernelspec',{}).get('language','python' if kernel.startswith('python') else ''))
    if language.lower()=='python':nb.cells.append(nbformat.v4.new_code_cell(CAPTURE))
    nbformat.write(nb,target)
    cwd='/workspace/output/'+str(notebook.relative_to(artifacts).parent) if mode=='notebook_directory' else '/workspace'
    nbpath='/workspace/'+str(target.relative_to(work))
    script='import os,nbformat\nfrom nbclient import NotebookClient\nfrom jupyter_client.kernelspec import get_kernel_spec, NoSuchKernel\ntry:get_kernel_spec('+repr(kernel)+')\nexcept NoSuchKernel:\n print("JB02_REQUIRED_KERNEL_UNAVAILABLE");raise SystemExit(2)\nos.chdir('+repr(cwd)+')\nnb=nbformat.read('+repr(nbpath)+',as_version=4)\ntry:\n NotebookClient(nb,timeout=120,kernel_name='+repr(kernel)+').execute()\nexcept Exception as exc:\n nbformat.write(nb,"/workspace/_failed.ipynb");print(type(exc).__name__,getattr(exc,"ename",""),getattr(exc,"evalue",""));import traceback;traceback.print_exc();raise SystemExit(1)\nnbformat.write(nb,"/workspace/_executed.ipynb")\n'
    result=execute(PACKET/'variants'/variant,work,"python3 - <<'AUDIT_CODE'\n"+script+'AUDIT_CODE',references=references,timeout=180)
    if result['exit_code']==2 and 'JB02_REQUIRED_KERNEL_UNAVAILABLE' in result['stdout']:
     raise RuntimeError('Required notebook kernel is not provisioned: '+kernel)
    if result['exit_code']==0 and any(path.is_symlink() for path in work.rglob('*')):
     result=dict(result,exit_code=1,stdout=result['stdout']+'\nDisallowed symlink in execution outputs')
    if (work/'_failed.ipynb').exists():shutil.copyfile(work/'_failed.ipynb',private/('failed_'+mode+'.ipynb'))
    attempts.append(dict(mode=mode,**result))
    if result['exit_code']==0:
     name='replayed_notebook_'+str(i)+'.ipynb';shutil.copyfile(work/'_executed.ipynb',private/name);executed.append(name)
     if (work/'_audit_tables.json').exists():
      tables.extend(dict(item,source_notebook=str(notebook.relative_to(artifacts))) for item in json.loads((work/'_audit_tables.json').read_text()))
     for book in work.rglob('*.xlsx'):
      rebuilt[str(i)+'/'+str(book.relative_to(work))]=cells(book)
     break
  records.append(dict(notebook=str(notebook.relative_to(artifacts)),passed=attempts[-1]['exit_code']==0,attempts=attempts))
 return records,rebuilt,tables,executed

def compare_tables(submitted,captured,rebuilt):
 candidates=[]
 for item in captured:
  t=item['table'];candidates.append((item['name'],[t['columns']]+t['data']))
 for file,book in rebuilt.items():candidates.extend((file+'/'+sheet,rows) for sheet,rows in book.items())
 comparisons=[]
 for sheet,rows in submitted.items():
  left=numerical_rows(rows);possible=sum(len(v) for vs in left.values() for v in vs);matches=[]
  for name,candidate in candidates:
   if not rows or not candidate or rows[0]!=candidate[0]:continue
   right=numerical_rows(candidate);count=0;bad=[]
   for key,lv in left.items():
    rv=right.get(key)
    if rv is None or len(lv)!=1 or len(rv)!=1:continue
    count+=len(lv[0])
    if any(not math.isclose(x,y,rel_tol=1e-6,abs_tol=5e-7) for x,y in zip(lv[0],rv[0])):bad.append(dict(labels=key[0],submitted=lv[0],replayed=rv[0]))
   matches.append(dict(candidate=name,compared=count,eligible=possible,coverage=count/possible if possible else 0,mismatches=bad[:20]))
  strong=[m for m in matches if m['coverage']>=.99]
  comparisons.append(dict(sheet=sheet,matches=matches,consistent=any(not m['mismatches'] for m in strong) if strong else None))
 return comparisons

def build(artifacts,private,variant,world=None):
 import nbformat,fitz
 from .jb02_analysis import prepare,analyze,database
 artifacts=Path(artifacts);private=Path(private);private.mkdir(parents=True,exist_ok=True)
 before=artifact_hashes(artifacts);paths=verify_references(variant)
 with tempfile.TemporaryDirectory(prefix='jb02-evidence-') as temp:
  tmp=Path(temp);refs=tmp/'references';refs.mkdir()
  for name,path in paths.items():shutil.copyfile(path,refs/name)
  preflight=execute(PACKET/'variants'/variant,tmp/'preflight',"python3 - <<'PYCODE'\nimport nbclient,nbformat,openpyxl,fitz,statsmodels,scipy,pandas,shapely\nfrom nbclient import NotebookClient\nNotebookClient(nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell('1+1')]),timeout=30,kernel_name='python3').execute()\nPYCODE",timeout=60)
  (private/'environment_preflight.json').write_text(json.dumps(preflight,indent=2)+'\n')
  if preflight['exit_code']:raise RuntimeError('JB02 acceptance runtime preflight failed; infrastructure failure')
  expected=prepare(PACKET/'variants'/variant/'inputs',REFERENCE_ROOT)
  db=database_evidence(artifacts/'county_analysis.db',expected)
  records,rebuilt,tables,executed=replay(artifacts,private,variant,refs)
  submitted=cells(artifacts/'disparity_profile.xlsx');comparisons=compare_tables(submitted,tables,rebuilt)
  database(expected,tmp/'reference.db');reference=analyze(tmp/'reference.db',refs/'us_states.geojson')
  reference={k:json.loads(v.to_json(orient='split')) if hasattr(v,'to_json') else v for k,v in reference.items() if k in ['matrix','decomposition','fits','spatial','mediation']}
 outputs=[]
 for name in executed:
  nb=nbformat.read(private/name,as_version=4)
  for i,cell in enumerate(nb.cells):
   if cell.cell_type!='code' or cell.source==CAPTURE:continue
   for out in cell.get('outputs',[]):
    outputs.append(dict(cell=i,text=out.get('text',''),data={k:v for k,v in out.get('data',{}).items() if k in ['text/plain','text/html','application/json']}))
 with fitz.open(artifacts/'reconciliation_memo.pdf') as pdf:
  memo=dict(pages=len(pdf),text='\n'.join(p.get_text() for p in pdf),images=len({im[0] for p in pdf for im in p.get_images()}))
 infrastructure_error=any('ModuleNotFoundError' in a.get('stdout','') or 'ImportError' in a.get('stdout','') for r in records for a in r['attempts']) and not all(r['passed'] for r in records)
 report=dict(infrastructure_error=infrastructure_error,replay_passed=bool(records) and all(r['passed'] for r in records),replays=records,database=db,workbook_comparisons=comparisons,executed_notebooks=executed,artifact_hashes=before,source_artifacts_unchanged=artifact_hashes(artifacts)==before,scope='Isolated submitted notebook replay; source database audit and conditional labeled workbook reproduction. Unmapped schema/methods require mandatory semantic reconciliation, not automatic rejection or pass.')
 # Large county tables remain in private evidence on disk; the semantic judge gets
 # aggregate tables and the source comparison, plus samples and full row counts.
 compact=[]
 for item in tables:
  t=item['table'];compact.append(dict(item,table=dict(t,data=t['data'][:120],index=t['index'][:120]),total_rows=len(t['data']),truncated=len(t['data'])>120))
 evidence=dict(database=db,submitted_workbook=submitted,captured_tables=compact,executed_outputs=outputs,memo=memo,conditional_reference=reference)
 (private/'captured_tables.json').write_text(json.dumps(tables,default=str)+'\n')
 (private/'reconciliation.json').write_text(json.dumps(report,default=str,indent=2)+'\n')
 (private/'numerical_evidence.json').write_text(json.dumps(evidence,default=str)+'\n')
 verify_references(variant)
 return report,evidence
