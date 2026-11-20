"""Run only in a fresh process whose cwd contains an isolated bound CSV world."""
import json
from pathlib import Path
import sys

def main():
    sys.path.insert(0,sys.argv[1])
    from src.evals.evaluation import is_correct
    from src.evals.actions import execute_actions_and_reset_state
    from src.tools.state import get_state
    request_path = Path(sys.argv[2])
    request = json.loads(request_path.read_text())
    before = get_state().crm_data.fillna('').to_dict(orient='records')
    executed, states = execute_actions_and_reset_state(request['predicted'])
    matched = is_correct(request['predicted'],request['reference'],'')
    result = dict(status='passed' if executed and matched else 'failed',execution_succeeded=executed,
                  native_state_match=matched,native_api_actions=len(request['predicted']),
                  original_algorithm_calls=1,original_task_fixed_world=False,
                  before_crm=before,after_crm=states['crm_data'].fillna('').to_dict(orient='records'),
                  validation_layer='bundled_workbench_bound_world_replay')
    (request_path.parent/'result.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':
    main()
