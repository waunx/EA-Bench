"""AW04 world-specific native delivery and subscription controls."""
import argparse,json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from integrations.packet_stages.english_packet import ROOT,RELEASE
from integrations.packet_stages.authored import reviewed_worlds
from integrations.packet_stages.open_aw04 import OpenAW04
from .aw04_replay import replay

def world(job):
 output,variant,i,answers=job
 host=OpenAW04(variant,answers);target=host.checker.target
 orders=[dict(tool='call',name='place_order',arguments={k:r[k] for k in ['person','address','sku','quantity','gift_wrap']}) for r in host.checker.expected_orders.values()]
 subscribe=[dict(tool='call',name='subscribe_prime',arguments={})]
 actions=(subscribe if target['prime'] else [])+orders
 controls=[('positive',actions),('missing_recipient',actions[:-1]),('unwrapped',[(dict(a,arguments=dict(a['arguments'],gift_wrap=False)) if a['name']=='place_order' else a) for a in actions]),('membership_choice',orders if target['prime'] else subscribe+orders)]
 rows=[]
 for label,actions in controls:
  folder=output/variant/str(i)/label;r=replay(variant,answers,actions,folder)
  assert r['native_passed']==(label=='positive'),(variant,i,label,r['native_checks'])
  assert r['supplemental_verdict']['success']==(label=='positive')
  rows.append(dict(label=label,native_passed=r['native_passed'],native_api_actions=len(r['native_calls']),evidence=str(folder.relative_to(ROOT))))
 return dict(variant=variant,world=i,status='passed',controls=rows)

def validate(output):
 output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True);jobs=[]
 for variant in json.loads((RELEASE/'AW04/MANIFEST.json').read_text()):jobs += [(output,variant,i,a) for i,(a,t) in enumerate(reviewed_worlds('AW04',variant))]
 with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(world,jobs))
 result=dict(case='AW04',variants=len({r['variant'] for r in rows}),worlds=len(rows),branch_controls=rows,original_evaluator_runs=0,layer='Actual native Amazon deliveries and subscriptions; authored tariffs separately checked')
 (output/'result.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(validate(a.output)))
