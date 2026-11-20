"""AW11 every reviewed basket plus missing-item and no-purchase native controls."""
import argparse,json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from integrations.packet_stages.english_packet import ROOT,RELEASE
from integrations.packet_stages.authored import reviewed_worlds
from .aw11_replay import replay

def world(job):
    output,variant,i,answers,target=job
    def action(identity):return dict(tool='call',name='follow_artist',arguments=dict(artist=identity))
    correct=[action(identity) for identity in target['add']]
    extras=set(['A1','A2','A3','X1','X2','A9'])-set(target['final'])
    controls=[('positive',correct),('missing_follow',correct[1:]),('unrelated_follow',correct+[action(sorted(extras)[0])])]
    rows=[]
    for label,actions in controls:
        folder=output/variant/str(i)/label;r=replay(variant,answers,actions,folder)
        assert r['native_passed']==(label=='positive'),(variant,i,label,r['native_checks'])
        assert r['supplemental_verdict']['success']==(label=='positive')
        rows.append(dict(label=label,native_passed=r['native_passed'],native_api_actions=len(r['native_calls']),evidence=str(folder.relative_to(ROOT))))
    return dict(variant=variant,world=i,status='passed',controls=rows)

def validate(output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True);jobs=[]
    for variant in json.loads((RELEASE/'AW11/MANIFEST.json').read_text()):
        jobs += [(output,variant,i,a,t) for i,(a,t) in enumerate(reviewed_worlds('AW11',variant))]
    with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(world,jobs))
    result=dict(case='AW11',variants=len({r['variant'] for r in rows}),worlds=len(rows),branch_controls=rows,original_evaluator_runs=0,layer='Actual native Spotify effects and database assertions on authored supplemental worlds')
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(validate(a.output)))
