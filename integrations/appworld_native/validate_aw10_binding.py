"""AW10 every reviewed basket plus missing-item and no-purchase native controls."""
import argparse,json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from integrations.packet_stages.english_packet import ROOT,RELEASE
from integrations.packet_stages.authored import reviewed_worlds
from .aw10_replay import replay

def world(job):
    output,variant,i,answers,target=job
    message=target['message']
    def action(name,**args):return dict(tool='call',name=name,arguments=dict(draft_id='MAIL1',**args))
    controls=[('positive',[action('update_draft',message=message),action('send_draft')]),('no_send',[]),('wrong_body',[action('update_draft',message=message.replace('<SONGS>','<SONGS>\nWrong entry')),action('send_draft')])]
    rows=[]
    for label,actions in controls:
        folder=output/variant/str(i)/label;r=replay(variant,answers,actions,folder)
        assert r['native_passed']==(label=='positive'),(variant,i,label,r['native_checks'])
        assert r['supplemental_verdict']['success']==(label=='positive')
        rows.append(dict(label=label,native_passed=r['native_passed'],native_api_actions=len(r['native_calls']),evidence=str(folder.relative_to(ROOT))))
    return dict(variant=variant,world=i,status='passed',controls=rows)

def validate(output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True);jobs=[]
    for variant in json.loads((RELEASE/'AW10/MANIFEST.json').read_text()):
        jobs += [(output,variant,i,a,t) for i,(a,t) in enumerate(reviewed_worlds('AW10',variant))]
    with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(world,jobs))
    result=dict(case='AW10',variants=len({r['variant'] for r in rows}),worlds=len(rows),branch_controls=rows,original_evaluator_runs=0,layer='Actual native Gmail effects and database assertions on authored supplemental worlds')
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(validate(a.output)))
