"""Private isolated native replay of captured AW01 effects."""
from ea_bench.paths import APPWORLD_ROOT, APPWORLD_PYTHON
import argparse, hashlib, json, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from integrations.appworld_native.aw01_binding import NativeAW01

def run(request, output):
    os.environ['APPWORLD_ROOT']=APPWORLD_ROOT
    os.chdir(APPWORLD_ROOT)
    engine=NativeAW01(request['variant'],request['answers'],experiment_name=request['experiment_name'])
    try:
        engine.confirm(request['answers'])
        for action in request['actions']:
            reply=engine.step(action)
            if 'error' in reply:
                raise ValueError('Native replay rejected a successful host effect: '+str(reply))
        engine.native.execute('pass')
        checks=engine.native_checks()
        packet=ROOT/'data/expanded/AW01/variants'/request['variant']
        paths=list(Path(__file__).parent.glob('aw01_*.py'))+[Path(__file__).with_name('validate_aw01.py')]
        result=dict(case='AW01',variant=request['variant'],answers=request['answers'],native_checks=checks,native_passed=all(checks.values()),native_calls=engine.native_calls,order_map=engine.order_map,quote_map=engine.quote_map,original_evaluator_runs=0,provenance='Authored supplemental seed and offer adapter over real AppWorld Amazon APIs; original fixed-world evaluator is separate',financial_projection='Quote total is represented by native pretax price plus native 10-percent tax; Prime shipping is zero. Pending refund and label fee remain supplemental checks.',source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},packet_sha256={str(p.relative_to(packet)):hashlib.sha256(p.read_bytes()).hexdigest() for p in packet.rglob('*') if p.is_file()})
        output.write_text(json.dumps(result,indent=2,default=str)+'\n')
        return result
    finally:
        engine.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--request',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();run(json.loads(args.request.read_text()),args.output)
