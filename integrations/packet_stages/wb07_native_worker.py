"""WB07 fresh native runtime; accepts each permitted-assignee reference separately."""
import hashlib,json,sys
from pathlib import Path
native=Path(sys.argv[1]);sys.path.insert(0,str(native))
from src.evals.evaluation import is_correct
from src.evals.actions import execute_actions_and_reset_state
from src.tools.state import get_state,reset_state
request=json.loads(Path('request.json').read_text());rows=[];reset_state()
initial=get_state().project_tasks.fillna('').to_dict('records')
for p in request['predictions']:
    success,states=execute_actions_and_reset_state(p['actions'])
    checks=[is_correct(p['actions'],r,p.get('error','')) for r in request['expected']]
    rows.append(dict(label=p['label'],actions=p['actions'],execution_success=success,native_evaluator_passed=any(checks),permitted_reference_results=checks,final_state={k:v.fillna('').to_dict('records') for k,v in states.items()}))
result=dict(initial_tasks=initial,predictions=rows,original_evaluator_runs=len(rows)*len(request['expected']),bundled_source_sha256={str(p.relative_to(native)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (native/'src').rglob('*.py')},upstream_byte_identity_certified=False)
Path('result.json').write_text(json.dumps(result,indent=2)+'\n')
