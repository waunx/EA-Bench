"""Private isolated native replay of captured AW06 effects."""
from ea_bench.paths import APPWORLD_ROOT, APPWORLD_PYTHON
import argparse, hashlib, json, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from integrations.appworld_native.aw06_binding import NativeAW06

def run(request, output):
    os.environ['APPWORLD_ROOT']=APPWORLD_ROOT
    os.chdir(APPWORLD_ROOT)
    engine=NativeAW06(request['variant'],request['answers'],experiment_name=request['experiment_name'])
    try:
        engine.confirm(request['answers'])
        action_errors=[]
        for action in request['actions']:
            try:
                reply=engine.step(action)
            except Exception as exc:
                if not str(exc).startswith(('Response status code is 400:','Response status code is 422:')):
                    raise
                reply={'error':str(exc)}
            if 'error' in reply:
                action_errors.append(dict(action=action,error=reply['error']))
                break
        engine.native.execute('pass')
        checks=engine.native_checks()
        checks['native_actions_accepted']=not action_errors
        packet=ROOT/'data/expanded/AW06/variants'/request['variant']
        paths=list(Path(__file__).parent.glob('aw06_*.py'))+[Path(__file__).with_name('validate_aw06.py')]
        result=dict(case='AW06',variant=request['variant'],answers=request['answers'],native_checks=checks,native_passed=all(checks.values()),native_calls=engine.native_calls,product_map=engine.product_map,card_map=engine.card_map,original_evaluator_runs=0,provenance='Authored supplemental seed and offer adapter over real AppWorld Amazon APIs; original fixed-world evaluator is separate',financial_projection='Authored retail prices; real EA006 native promo offsets native 10-percent tax. Prime shipping is zero. Native cart stores product quantity/gift and coupon; authored selected/seller/line/note/address metadata remain supplemental. Distinct owner labels satisfy native account-card uniqueness.',source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},packet_sha256={str(p.relative_to(packet)):hashlib.sha256(p.read_bytes()).hexdigest() for p in packet.rglob('*') if p.is_file()})
        result['native_action_errors']=action_errors
        output.write_text(json.dumps(result,indent=2,default=str)+'\n')
        return result
    finally:
        engine.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--request',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();run(json.loads(args.request.read_text()),args.output)
