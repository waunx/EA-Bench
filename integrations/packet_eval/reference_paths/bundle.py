"""Build a self-contained input reader with no oracle or expected-result values."""
import hashlib
from pathlib import Path
from .kernel import extract, SPECIAL
HERE=Path(__file__).resolve().parent

def bundle(case):
 code=extract(case)+'\n'+(HERE/'reducers.py').read_text()+'\n'+(HERE/'questions.py').read_text()
 code+='\nimport os,sys\nINPUTS=Path("/workspace/inputs")\naccessed=set()\n'
 code+='''def access_audit(event,args):
 if event in ['open','sqlite3.connect'] and args and isinstance(args[0],(str,bytes,os.PathLike)):
  value=os.fsdecode(args[0])
  if value.startswith('file:'):value=value[5:].split('?',1)[0]
  path=os.path.abspath(value)
  if path.startswith('/workspace/inputs/'):
   accessed.add(path.removeprefix('/workspace/'))
  elif path.startswith('/workspace/') and path!='/workspace/prompt.md':
   raise RuntimeError('Reference reader attempted non-input access: '+path)
sys.addaudithook(access_audit)
'''
 code+=f"data=load('selected')\n" if case in SPECIAL else "data=collect(INPUTS)\n"
 code+=f"unknown=unknown_keys({case!r},globals(),data)\n"
 call="actions(solve(data,{}))" if case=='AW08' else "solve(data,{})" if case in SPECIAL-{'JB03','JB11'} else "project(data,{})"
 code+=f"if unknown:\n payload=dict(kind='state',data=reduce_data({case!r},data),unknown=unknown)\nelse:\n payload=dict(kind='result',result={call},unknown=[])\n"
 code+="payload['accessed_files']=sorted(accessed)\nprint(json.dumps(payload,ensure_ascii=False,separators=(',',':'),default=json_default))\n"
 assert 'private/oracle' not in code and 'EXPECTED' not in code
 return code

def command(case):
 code=bundle(case)
 delimiter='EA_REFERENCE_'+hashlib.sha256(code.encode()).hexdigest()[:16]
 return "python3 - <<'"+delimiter+"'\n"+code+'\n'+delimiter
