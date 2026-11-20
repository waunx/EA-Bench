"""Host wrapper for isolated AW14 native effect replay."""
from ea_bench.paths import APPWORLD_ROOT, APPWORLD_PYTHON
import hashlib,json,os,subprocess,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def replay(variant,answers,actions,output,fault=None):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    packet=ROOT/'data/expanded/AW14/variants'/variant
    request=dict(variant=variant,answers=answers,actions=actions,fault=fault,experiment_name='aw14-bound-'+uuid.uuid4().hex[:12],
                 packet_hashes={str(p.relative_to(packet)):hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in packet.rglob('*') if p.is_file()})
    (output/'request.json').write_text(json.dumps(request,indent=2)+'\n')
    env=dict(os.environ,APPWORLD_ROOT=APPWORLD_ROOT,PYTHONPATH=str(ROOT),
             OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',IPYTHONDIR='/tmp/ea-native-ipython')
    worker=Path(__file__).with_name('aw14_worker.py')
    with (output/'worker.log').open('w') as log:
        command=[APPWORLD_PYTHON,str(worker)]
        command+=['--request',str(output/'request.json'),'--output',str(output/'result.json')]
        p=subprocess.run(command,cwd=APPWORLD_ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180)
    if p.returncode:raise RuntimeError('Native AW14 worker failed; '+str(output/'worker.log'))
    result=json.loads((output/'result.json').read_text())
    result['source_hashes']={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in Path(__file__).parent.glob('aw14_*.py')}
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def captured(events):
    return [e['action'] for e in events if isinstance(e.get('action'),dict)
            and e['action'].get('tool')=='call'
            and e['action'].get('name') in {'create_expense','update_expense','delete_expense'}
            and 'error' not in e['reply'] and e.get('before')!=e.get('after')]

def evaluate_engine(engine,output):
    actions=captured(engine.events)
    for action in actions:
        args=action['arguments']
        if action['name']!='delete_expense' and (
            args['group']!=engine.data['account_context.json']['group'] or args['amount_cents']<=0):
            return dict(status='failed',native_api_actions=0,original_algorithm_calls=0,
                        unsupported_projection='Native binding requires known group and positive amount')
    result=replay(engine.variant,engine.answers,actions,output)
    return dict(status='passed' if result['native_passed'] else 'failed',
                native_api_actions=len(result['native_calls']),original_algorithm_calls=0,
                native_checks=result['native_checks'],evidence=str(Path(output)/'result.json'),
                layer='actual_AppWorld_API_and_DB_checks_on_authored_supplemental_world')
