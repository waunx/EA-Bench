"""Safe submitted-notebook replay and private numerical reconciliation evidence."""
from pathlib import Path
import json,shutil,tempfile,math,collections,hashlib
from .artifact_sandbox import execute
from .native import artifact_hashes
from .author_english_jb01 import PACKET,REFERENCE_ROOT
REQUIRED={'Clean_Data','Descriptive_Stats','Correlation_Matrix','Model_Comparison','Sensitivity'}

def cells(path):
 import openpyxl
 book=openpyxl.load_workbook(path,read_only=True,data_only=True)
 result={name:[[v if isinstance(v,(str,int,float,bool)) or v is None else str(v) for v in row] for row in book[name].iter_rows(values_only=True)] for name in book.sheetnames}
 book.close();return result

def numerical_rows(rows):
 result=collections.defaultdict(list)
 for row in rows:
  nums=[(i,float(v)) for i,v in enumerate(row) if isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)]
  if not nums:continue
  labels=tuple((i,str(v).strip().casefold()) for i,v in enumerate(row) if v is not None and not isinstance(v,(int,float,bool)))
  if labels:result[(labels,tuple(i for i,v in nums))].append([v for i,v in nums])
 return result

def compare_books(submitted,rebuilt):
 comparisons=[]
 for a,aa in submitted.items():
  for b,bb in rebuilt.items():
   compared=0;possible=0;mismatches=[];covered=[]
   for sheet in REQUIRED & aa.keys() & bb.keys():
    left=numerical_rows(aa[sheet]);right=numerical_rows(bb[sheet]);count=0
    possible+=sum(len(values) for rows in left.values() for values in rows)
    for key,lv in left.items():
     rv=right.get(key)
     if not rv or len(rv)!=1 or len(lv)!=1:continue
     for x,y in zip(sorted(lv),sorted(rv)):
      count+=len(x)
      if any(not math.isclose(v,w,rel_tol=1e-6,abs_tol=5e-7) for v,w in zip(x,y)):
       mismatches.append(dict(sheet=sheet,labels=key[0],submitted=x,replayed=y))
    if count:covered.append(sheet)
    compared+=count
   comparisons.append(dict(submitted=a,replayed=b,compared_numbers=compared,eligible_numbers=possible,coverage=compared/possible if possible else 0,sheets=sorted(covered),mismatches=mismatches))
 return comparisons

CAPTURE = '''
import json as _audit_json
import pandas as _audit_pd
_audit_tables=[];_audit_seen=set()
def _audit_walk(name,value,depth=0):
 if id(value) in _audit_seen or depth>3 or len(_audit_tables)>=150:return
 _audit_seen.add(id(value))
 if isinstance(value,(_audit_pd.DataFrame,_audit_pd.Series)):
  if isinstance(value,_audit_pd.Series):value=value.to_frame()
  if len(value)<=1000 and len(value.columns)<=100:
   _audit_tables.append(dict(name=name,table=_audit_json.loads(value.to_json(orient='split',default_handler=str))))
 elif isinstance(value,dict):
  for key,item in list(value.items()):_audit_walk(name+'.'+str(key),item,depth+1)
for _audit_name,_audit_value in list(globals().items()):
 if not _audit_name.startswith('_'):_audit_walk(_audit_name,_audit_value)
with open('/workspace/_audit_tables.json','w') as _audit_f:_audit_json.dump(_audit_tables,_audit_f)
'''

def replay(artifacts,private,variant):
 import nbformat
 records=[];rebuilt={};tables=[];executed=[]
 for i,notebook in enumerate(sorted(artifacts.rglob('*.ipynb'))):
  attempts=[]
  for mode in ['notebook_directory','workspace_directory']:
   with tempfile.TemporaryDirectory(prefix='jb01-replay-') as temp:
    work=Path(temp);out=work/'output';out.mkdir()
    for source in artifacts.rglob('*'):
     if source.is_symlink():raise ValueError('Submitted symlink')
     if not source.is_file() or source.suffix.lower() in {'.xls','.pdf'}:continue
     if source.suffix.lower()=='.xlsx' and REQUIRED.issubset(cells(source)):continue
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
    script='import os,nbformat\nfrom nbclient import NotebookClient\nfrom jupyter_client.kernelspec import get_kernel_spec, NoSuchKernel\ntry:get_kernel_spec('+repr(kernel)+')\nexcept NoSuchKernel:\n print("JB01_REQUIRED_KERNEL_UNAVAILABLE");raise SystemExit(2)\nos.chdir('+repr(cwd)+')\nnb=nbformat.read('+repr(nbpath)+',as_version=4)\ntry:\n NotebookClient(nb,timeout=120,kernel_name='+repr(kernel)+').execute()\nexcept Exception as exc:\n print(type(exc).__name__,getattr(exc,"ename",""),getattr(exc,"evalue",""));raise SystemExit(1)\nnbformat.write(nb,"/workspace/_executed.ipynb")\n'
    result=execute(PACKET/'variants'/variant,work,"python3 - <<'AUDIT_CODE'\n"+script+'AUDIT_CODE',references=REFERENCE_ROOT,timeout=180)
    if result['exit_code']==2 and 'JB01_REQUIRED_KERNEL_UNAVAILABLE' in result['stdout']:
     raise RuntimeError('Required notebook kernel is not provisioned: '+kernel)
    if result['exit_code']==0 and any(path.is_symlink() for path in work.rglob('*')):
     result=dict(result,exit_code=1,stdout=result['stdout']+'\nDisallowed symlink in execution outputs')
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

def build(artifacts,private,variant,world):
 from .jb01_analysis import prepare,analyze
 artifacts=Path(artifacts);private=Path(private);private.mkdir(parents=True,exist_ok=True)
 before=artifact_hashes(artifacts)
 reference_hashes=verify_references(variant)
 environment_preflight(variant,private)
 records,rebuilt,tables,executed=replay(artifacts,private,variant)
 submitted={str(p.relative_to(artifacts)):cells(p) for p in artifacts.rglob('*.xlsx')}
 comparisons=compare_books(submitted,rebuilt)
 clean,quality=prepare(PACKET/'variants'/variant/'inputs',REFERENCE_ROOT,world or {})
 analysis=analyze(clean)
 reference={key:json.loads(value.to_json(orient='split')) for key,value in analysis.items() if hasattr(value,'to_json')}
 reference.update(clustering=analysis['clustering'],stability=analysis['stability'],quality=quality)
 strong=[c for c in comparisons if c['coverage']>=.99 and set(c['sheets'])==REQUIRED]
 numeric_consistent=any(not c['mismatches'] for c in strong) if strong else None
 report=dict(labeled_numeric_reproduction=numeric_consistent,replay_passed=bool(records) and any(r['passed'] for r in records),replays=records,numerical_comparisons=comparisons,executed_notebooks=executed,artifact_hashes=before,source_artifacts_unchanged=artifact_hashes(artifacts)==before,scope='Fresh isolated notebook execution; labeled numerical comparisons are conditional on matching layouts. Semantic rubric must reconcile all submitted numbers, all captured tables and source references, permitting defensible alternate methods.')
 (private/'reconciliation.json').write_text(json.dumps(report,indent=2)+'\n')
 verify_references(variant)
 outputs=[]
 import nbformat
 for name in executed:
  notebook=nbformat.read(private/name,as_version=4)
  for index,cell in enumerate(notebook.cells):
   if cell.cell_type=='code' and cell.source==CAPTURE:continue
   for output in cell.get('outputs',[]):
    item=dict(notebook=name,cell=index,output_type=output.output_type)
    if 'text' in output:item['text']=output.text
    if 'data' in output:item['data']={k:v for k,v in output.data.items() if k in ['text/plain','text/html','application/json']}
    outputs.append(item)
 evidence=dict(reference_hashes=reference_hashes,executed_notebook_outputs=outputs,submitted_workbooks=submitted,replayed_workbooks=rebuilt,captured_notebook_tables=tables,conditional_reference=reference)
 (private/'numerical_evidence.json').write_text(json.dumps(evidence,default=str)+'\n')
 return report,evidence

def verify_references(variant):
 records=json.loads((PACKET/'variants'/variant/'inputs/reference_sources.json').read_text());hashes={}
 for record in records:
  source=REFERENCE_ROOT/record['file'];digest=hashlib.sha256(source.read_bytes()).hexdigest()
  if digest!=record['sha256']:raise RuntimeError('Public reference integrity failure: '+record['file'])
  hashes[record['file']]=digest
 return hashes

def environment_preflight(variant,private):
 with tempfile.TemporaryDirectory(prefix='jb01-preflight-') as temp:
  command="python3 - <<'PREFLIGHT'\nimport nbclient,nbformat,openpyxl,fitz,statsmodels,scipy,pandas,json\nfrom nbclient import NotebookClient\nnb=nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell('1+1')])\nNotebookClient(nb,timeout=30,kernel_name='python3').execute()\nprint(json.dumps({m.__name__:getattr(m,'__version__','available') for m in [nbclient,nbformat,openpyxl,fitz,statsmodels,scipy,pandas]}))\nPREFLIGHT"
  result=execute(PACKET/'variants'/variant,Path(temp),command,timeout=60)
 (private/'environment_preflight.json').write_text(json.dumps(result,indent=2)+'\n')
 if result['exit_code']!=0:raise RuntimeError('Acceptance runtime preflight failed; infrastructure, not submitted artifact failure')
