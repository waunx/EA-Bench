"""Fresh-process worker. Imports native source only after CSV binding exists."""
import hashlib,json,sys
from pathlib import Path
native=Path(sys.argv[1]);sys.path.insert(0,str(native))
from src.evals.evaluation import is_correct
from src.evals.actions import execute_actions_and_reset_state
from src.tools.state import get_state,reset_state
request=json.loads(Path('request.json').read_text());results=[]
reset_state()
initial=get_state().calendar_events.fillna('').to_dict('records')
for prediction in request['predictions']:
    success,states=execute_actions_and_reset_state(prediction['actions'])
    results.append(dict(label=prediction['label'],execution_success=success,native_evaluator_passed=is_correct(prediction['actions'],request['expected'],prediction.get('error','')),actions=prediction['actions'],final_state={k:v.fillna('').to_dict('records') for k,v in states.items()}))
source_hashes={str(p.relative_to(native)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (native/'src').rglob('*.py')}
result=dict(initial_calendar=initial,predictions=results,bundled_source_sha256=source_hashes,original_evaluator_runs=len(results),validation_layer='Bundled WorkBench native API replay on authored bound CSV world; supplemental reference actions',upstream_byte_identity_certified=False)
Path('result.json').write_text(json.dumps(result,indent=2,default=str)+'\n')
