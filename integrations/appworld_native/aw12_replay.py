"""Host-side AW12 native subprocess invocation; no AppWorld import in host."""
from ea_bench.paths import APPWORLD_ROOT, APPWORLD_PYTHON
from pathlib import Path
import json,os,subprocess,uuid
ROOT=Path(__file__).resolve().parents[2]
PYTHON=Path(APPWORLD_PYTHON)
def replay(variant,answers,actions,output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    request=dict(variant=variant,answers=answers,actions=actions,experiment_name='aw12-bound-'+uuid.uuid4().hex[:12])
    (output/'request.json').write_text(json.dumps(request,indent=2)+'\n')
    env=dict(os.environ,APPWORLD_ROOT=APPWORLD_ROOT,PYTHONPATH=str(ROOT),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    try:
        p=subprocess.run([str(PYTHON),str(Path(__file__).with_name('aw12_worker.py')),'--request',str(output/'request.json'),'--output',str(output/'result.json')],cwd=APPWORLD_ROOT,env=env,text=True,capture_output=True,timeout=180)
    except subprocess.TimeoutExpired as exc:
        for name,value in [('stdout',exc.stdout),('stderr',exc.stderr)]:
            (output/(name+'.log')).write_text(value.decode(errors='replace') if isinstance(value,bytes) else value or '')
        (output/'infrastructure_failure.json').write_text(json.dumps(dict(status='timeout',seconds=180,scope='native execution, no verdict'),indent=2)+'\n')
        raise
    (output/'stdout.log').write_text(p.stdout);(output/'stderr.log').write_text(p.stderr)
    if p.returncode:raise RuntimeError(p.stderr)
    return json.loads((output/'result.json').read_text())

def captured(events):
    return [e['action'] for e in events if isinstance(e.get('action'),dict) and e['action'].get('tool')=='call' and e['action'].get('name') in {'verify_backup','create_account','add_song','add_album','create_playlist','update_playlist'} and 'error' not in e['reply']]

def evaluate_engine(engine,output):
    actions=captured(engine.events)
    result=replay(engine.variant,engine.answers,actions,output)
    return dict(status='passed' if result['native_passed'] else 'failed',native_api_actions=len(result['native_calls']),original_algorithm_calls=0,evidence=str(Path(output)/'result.json'),layer='actual_AppWorld_API_and_DB_checks_on_authored_supplemental_world',native_checks=result['native_checks'])
