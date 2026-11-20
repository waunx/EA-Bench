"""Isolated AW10 native replay; actual actions only."""
from ea_bench.paths import APPWORLD_ROOT, APPWORLD_PYTHON
import argparse,json,os,sys,hashlib,faulthandler
faulthandler.dump_traceback_later(90,repeat=False)
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from integrations.appworld_native.aw10_binding import NativeAW10

def run(request,output):
 os.environ['APPWORLD_ROOT']=APPWORLD_ROOT;os.chdir(APPWORLD_ROOT)
 e=NativeAW10(request['variant'],request['answers'],experiment_name=request['experiment_name'])
 try:
  e.confirmed=dict(request['answers'])
  for a in request['actions']:
   reply=e.step(a)
   if 'error' in reply:raise ValueError(str(reply))
  e.step(dict(tool='submit',result=dict(summary='Native effect replay.')))
  checks=e.native_checks()
  result=dict(case='AW10',variant=request['variant'],answers=request['answers'],native_checks=checks,native_passed=all(checks.values()),supplemental_verdict=e.result,native_calls=e.native_calls,song_binding=e.song_map,isrc_projection=e.isrc_projection,recording_identity_layer='Native title/year and membership only; no authored artist field. ISRC remains an explicit supplemental mapping because native Spotify has no ISRC column',native_request_id=e.request_id,native_thread_id=e.thread.id,subject_projection='Native reply API mandates Re: prefix; authored envelope remains byte-preserved by supplemental checker',provenance='Authored supplemental seed on 1b988ac_1 native database',original_evaluator_runs=0,source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('aw10_*.py')})
  output.write_text(json.dumps(result,indent=2,default=str)+'\n');return result
 finally:e.native.close()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--request',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(json.loads(a.request.read_text()),a.output)
