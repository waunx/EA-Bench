"""Validate source-only reference paths separately from model cost traces."""
import argparse,json,itertools,hashlib,sys
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from copy import deepcopy
from .kernel import SOURCE,ROOT,environment,read_data,decide,SPECIAL
from .reducers import reduce_data,restore_data,json_default,json_hook
from .questions import unknown_keys
from .bundle import bundle,command
from integrations.packet_eval.command_replay import execute_traced
from integrations.packet_eval.scoring import equal
from integrations.packet_audit.common import write,sha


def author_worlds(case,variant,oracle,report):
 record=report['variants'][variant];unknown=oracle['variants'][variant]['missing']+oracle['variants'][variant]['conflict']
 if 'worlds' in record:
  expected={frozenset(w['alternatives']):w.get('result',w.get('actions')) for w in record['worlds']}
 elif 'reviewed_worlds' in record:
  expected={frozenset(k for k,v in w['answers'].items() if v==oracle['atoms'][k]['alternative']):w['expected'] for w in record['reviewed_worlds']}
 else:
  code=ROOT/'experiments/ea-bench-45-variants-20260929'
  env={'__file__':str(SOURCE/case/'check.py')}
  exec((code/'reviewed_head.txt').read_text()+(code/(case+'_logic.py')).read_text(),env)
  expected={frozenset(k for k,b in zip(unknown,bits) if b):env['EXPECTED'][''.join('1' if k in {k for k,b in zip(unknown,bits) if b} else '0' for k in oracle['atoms'])] for bits in itertools.product([0,1],repeat=len(unknown))}
 return [(dict((k,oracle['atoms'][k]['alternative' if k in alternatives else 'default']) for k in unknown),value) for alternatives,value in expected.items()]


def normal(value):return json.loads(json.dumps(value,ensure_ascii=False,default=json_default))

def validate_case(case,variants,output,trace=False):
 directory=SOURCE/case
 oracle=json.loads((directory/'private/oracle.json').read_text())
 report=json.loads((directory/'private/check_result.json').read_text())
 manifest=json.loads((directory/'MANIFEST.json').read_text())
 target=output/case;target.mkdir(parents=True,exist_ok=True)
 (target/'reference.py').write_text(bundle(case))
 rows=[]
 for variant in variants:
  packet=directory/'variants'/variant
  for name,digest in manifest[variant].items():
   assert sha(packet/name)==digest,(case,variant,name,'source changed')
  inputs=directory/'variants'/variant/'inputs'
  env=environment(case,inputs);data=read_data(case,env)
  unknown=unknown_keys(case,env,data)
  declared=oracle['variants'][variant]['missing']+oracle['variants'][variant]['conflict']
  assert set(unknown)==set(declared),(case,variant,unknown,declared)
  worlds=author_worlds(case,variant,oracle,report)
  checked=0
  state=reduce_data(case,data) if unknown else None
  text=json.dumps(state,ensure_ascii=False,separators=(',',':'),default=json_default)
  if unknown:assert len(text.encode())<22500,(case,variant,len(text.encode()))
  for answers,expected in worlds:
   restored=restore_data(case,json.loads(text,object_hook=json_hook)) if unknown else data
   actual=normal(decide(case,env,restored,answers))
   assert equal(actual,normal(expected)),(case,variant,answers,actual,expected)
   checked+=1
  if trace:
   path=target/variant
   reply,count=execute_traced(directory/'variants'/variant,path/'workspace',command(case),path/'execution')
   assert reply['exit_code']==0,(case,variant,reply)
   assert not reply['truncated'],(case,variant,'output truncated')
   assert count['command_count']==1,(case,variant,count)
   payload=json.loads(reply['stdout'],object_hook=json_hook)
   assert set(payload['unknown'])==set(unknown)
   assert payload['accessed_files'],(case,variant,'reference did not read input data')
   for answers,expected in worlds:
    actual=normal(decide(case,env,restore_data(case,payload['data']),answers)) if payload['kind']=='state' else normal(payload['result'])
    assert equal(actual,normal(expected)),(case,variant,'wire reference mismatch',answers)
  rows.append(dict(id=case+'--'+variant,case=case,variant=variant,
      input_hashes=manifest[variant],reference_sha256=sha(target/'reference.py'),
      read_compute_commands=1,ask_calls=int(bool(unknown)),submit_calls=1,
      tool_lower_bound=2+int(bool(unknown)),worlds_checked=checked,
      reference_output_bytes=len(reply['stdout'].encode()) if trace else len(text.encode()),
      read_files=payload['accessed_files'] if trace else None,
      status='reference_path_verified' if trace else 'memory_checks_passed',
      criterion='evidence_grounded_file_decision',
      lower_bound_argument='At least one command must acquire task-relevant file evidence; unknown facts require at least one user call; a successful attempt requires submit. The reference attains these counts. Internal agent reasoning is not a command.'))
 write(target/'validation.json',dict(case=case,variants=rows,model_calls=0))
 contracts=dict(json.loads(line) for line in (ROOT/'integrations/packet_eval/contracts.jsonl').read_text().splitlines())
 original=json.loads((directory/'SOURCE.json').read_text())['original_text']
 lines=['# '+case+' reference action-cost validation','',contracts[case],'',
  'Reference completion requires file evidence. A command may batch reading and computation; model-internal reasoning is not counted as a tool call. Requested facts and user calls are recorded separately.',
  'The reference reads public inputs. Private expected values are used only by the outer checker.',
  '', '| Variant | Read/compute | User calls | Submit | Total | Counterfactual worlds |','|---|---:|---:|---:|---:|---:|']
 for row in rows:lines.append('|'+row['variant']+'|1|'+str(row['ask_calls'])+'|1|'+str(row['tool_lower_bound'])+'|'+str(row['worlds_checked'])+'|')
 lines+=['','## Original task text','',original]
 (target/'REVIEW.md').write_text('\n'.join(lines)+'\n')

 print(case,len(rows),'variants',sum(r['worlds_checked'] for r in rows),'worlds checked',flush=True)
 return rows

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--output',type=Path,required=True)
 parser.add_argument('--trace',action='store_true')
 parser.add_argument('--case')
 parser.add_argument('--workers',type=int,default=4)
 args=parser.parse_args()
 tasks=json.loads((SOURCE/'PROGRESS.json').read_text())['tasks']
 if args.case:tasks=[t for t in tasks if t['case']==args.case]
 args.output.mkdir(parents=True,exist_ok=True)
 rows=[];errors=[]
 with ThreadPoolExecutor(max_workers=args.workers) as pool:
  futures={pool.submit(validate_case,t['case'],t['generated'],args.output,args.trace):t['case'] for t in tasks}
  for future in as_completed(futures):
   try:rows.extend(future.result())
   except Exception as error:
    import traceback
    traceback.print_exc()
    errors.append(dict(case=futures[future],error=str(error)))
 report=dict(model_calls=0,traced=args.trace,passed=len(rows),rows=rows,errors=errors,
  implementation_sha256={p.name:sha(p) for p in Path(__file__).parent.glob('*.py')},
  scope='Evidence-based file decision reference; one source-reading command, optional clarification, then submission. In-agent pure arithmetic is uncharged, as model reasoning is uncharged.')
 write(args.output/'validation.json',report)
 if errors:raise SystemExit(1)
 print('Verified',len(rows),'reference paths; model calls 0',flush=True)

if __name__=='__main__':main()
