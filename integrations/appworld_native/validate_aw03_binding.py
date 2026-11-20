"""AW03 every reviewed basket plus missing-item and no-purchase native controls."""
import argparse,json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from integrations.packet_stages.english_packet import ROOT,RELEASE
from integrations.packet_stages.authored import reviewed_worlds
from .aw03_replay import replay

def world(job):
    output,variant,i,answers,target=job
    from integrations.packet_stages.author_english_aw03 import SKU_IDS
    arguments=dict(sku=SKU_IDS[target['sku']],quantity=4,gift_wrap=True,destination='home')
    def action(**changes):return [dict(tool='call',name='place_order',arguments=dict(arguments,**changes))]
    controls=[('positive',action()),('no_purchase',[]),('unwrapped',action(gift_wrap=False)),('short_quantity',action(quantity=3))]
    rows=[]
    for label,actions in controls:
        folder=output/variant/str(i)/label;r=replay(variant,answers,actions,folder)
        assert r['native_passed']==(label=='positive'),(variant,i,label,r['native_checks'])
        assert r['supplemental_verdict']['success']==(label=='positive')
        rows.append(dict(label=label,native_passed=r['native_passed'],native_api_actions=len(r['native_calls']),evidence=str(folder.relative_to(ROOT))))
    return dict(variant=variant,world=i,status='passed',controls=rows)

def validate(output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True);jobs=[]
    for variant in json.loads((RELEASE/'AW03/MANIFEST.json').read_text()):
        jobs += [(output,variant,i,a,t) for i,(a,t) in enumerate(reviewed_worlds('AW03',variant))]
    with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(world,jobs))
    result=dict(case='AW03',variants=len({r['variant'] for r in rows}),worlds=len(rows),branch_controls=rows,original_evaluator_runs=0,layer='Actual native Amazon effects and database assertions on authored supplemental worlds')
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(validate(a.output)))
