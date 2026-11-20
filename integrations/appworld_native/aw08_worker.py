"""Real Venmo request replay in an authored, private native seed."""
import argparse,json
from pathlib import Path
from integrations.appworld_native.aw08_binding import NativeAW08

def run(request,output):
    e=NativeAW08(request['variant'],request['answers'],request['experiment_name'])
    try:
        for action in request['actions']:e.step(action)
        checks=e.native_checks()
        result=dict(native_passed=all(checks.values()),native_checks=checks,
                    supplemental=e.checker.final({'summary':'Completed'}).to_dict(),
                    native_calls=e.native_calls,native_state=e.native_snapshot(),
                    request_mapping=e.request_map,payment_mapping=e.payment_map,
                    original_evaluator_runs=0,
                    projection='Cancellation removes pending native request; authored tombstone, event attribution and cent policy remain supplemental')
        output.write_text(json.dumps(result,indent=2,default=str)+'\n')
    finally:e.native.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--request',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(json.loads(a.request.read_text()),a.output)
