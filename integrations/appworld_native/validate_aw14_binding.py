"""AW14 native expense controls and genuine captured-effect replay."""
from ea_bench.paths import APPWORLD_ROOT, APPWORLD_PYTHON
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
from integrations.packet_stages.authored import reviewed_worlds
from integrations.packet_stages.open_aw14 import OpenAW14
from integrations.appworld_native.aw14_replay import ROOT,replay,captured

def actions_for(variant,answers):
    e=OpenAW14(variant,answers);actions=[]
    for action in e.checker.target['actions']:
        args=deepcopy(e.checker.expected[action['month']]);args.pop('deleted')
        name='create_expense'
        if action['op']=='update':
            name='update_expense';args['expense']=action['expense']
        actions.append(dict(tool='call',name=name,arguments=args))
    return actions

def world(job):
    variant,index,answers,output=job;correct=actions_for(variant,answers);rows=[]
    for label in ['correct','omission','wrong_amount','wrong_note']:
        actions=deepcopy(correct)
        if label=='omission':actions=[]
        elif label=='wrong_amount':
            args=actions[-1]['arguments'];args['amount_cents']+=300
            for who in args['shares']:args['shares'][who]+=100
        elif label=='wrong_note':actions[-1]['arguments']['note']='electricity bill for 01/24'
        result=replay(variant,answers,actions,output/variant/str(index)/label)
        wanted=label=='correct'
        assert result['native_passed']==wanted,(variant,index,label,result['native_checks'])
        assert (result['supplemental']['status']=='passed')==wanted
        rows.append(dict(label=label,native_passed=result['native_passed']))
    return dict(variant=variant,world=index,controls=rows)

def validate(output,smoke=False):
    manifest=json.loads((ROOT/'data/expanded/AW14/MANIFEST.json').read_text())
    jobs=[(v,i,a,output) for v in manifest for i,(a,t) in enumerate(reviewed_worlds('AW14',v))]
    if smoke:jobs=jobs[:1]
    with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(world,jobs))
    result=dict(case='AW14',status='passed',worlds=len(rows),variants=len({r['variant'] for r in rows}),rows=rows)
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def historical(output):
    from hashlib import sha256
    batch=ROOT/'experiments/full-evaluation-gpt55-20261011/AW14'
    manifest=json.loads((ROOT/'data/expanded/AW14/MANIFEST.json').read_text());rows=[]
    for variant in manifest:
        episode=batch/variant/'attempt-1'
        config=json.loads((episode/'configuration.json').read_text())
        folder=ROOT/'data/expanded/AW14/variants'/variant
        assert config['packet_hashes']=={str(p.relative_to(folder)):sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()}
        path=episode/'private/events.jsonl'
        events=[json.loads(s) for s in path.read_text().splitlines()]
        answers=json.loads((episode/'private/world.json').read_text())
        result=replay(variant,answers,captured(events),output/variant)
        rows.append(dict(variant=variant,native_passed=result['native_passed'],trace_sha256=sha256(path.read_bytes()).hexdigest(),packet_identity_verified=True))
    (output/'result.json').write_text(json.dumps(rows,indent=2)+'\n')
    return rows

def focused(output):
    rows=[]
    for variant in ['full','R2']:
        for label in ['reverse_valid','duplicate','wrong_payer','wrong_split','wrong_group','protected','create_instead_update','duplicate_share']:
            actions=actions_for(variant,{})
            if label=='reverse_valid':actions.reverse()
            elif label=='duplicate':actions.append(deepcopy(actions[-1]))
            elif label=='wrong_payer':actions[-1]['arguments']['payer']='R1'
            elif label=='wrong_split':
                shares=actions[-1]['arguments']['shares'];shares['R1']+=1;shares['R2']-=1
            elif label=='wrong_group':actions[-1]['arguments']['group']='UNBOUND'
            elif label=='protected':
                e=OpenAW14(variant,{})
                args=deepcopy(next(r for r in e.state['expenses'] if r['expense']=='E90'))
                args.pop('deleted');args['amount_cents']+=3
                for who in args['shares']:args['shares'][who]+=1
                actions.append(dict(tool='call',name='update_expense',arguments=args))
            elif label=='create_instead_update':
                a=next(a for a in actions if a['name']=='update_expense')
                a['name']='create_expense';a['arguments'].pop('expense')
            result=replay(variant,{},actions,output/variant/label,
                          fault='duplicate_share' if label=='duplicate_share' else None)
            assert result['native_passed']==(label=='reverse_valid'),(variant,label)
            assert (result['supplemental']['status']=='passed')==(label in {'reverse_valid','duplicate_share'})
            rows.append(dict(variant=variant,label=label,native_passed=result['native_passed'],supplemental=result['supplemental']['status']))
    (output/'result.json').write_text(json.dumps(rows,indent=2)+'\n');return rows

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--smoke',action='store_true');p.add_argument('--historical',action='store_true');p.add_argument('--baseline',action='store_true');p.add_argument('--focused',action='store_true')
    a=p.parse_args();out=a.out.resolve()
    if a.baseline:
        import os,subprocess
        env=dict(os.environ,APPWORLD_ROOT=APPWORLD_ROOT,PYTHONPATH=str(ROOT),OPENBLAS_NUM_THREADS='1')
        subprocess.run([APPWORLD_PYTHON,'-m','integrations.appworld_native.aw14_baseline','--out',str(out)],cwd=APPWORLD_ROOT,env=env,check=True)
    else:
        out.mkdir(parents=True,exist_ok=True)
        print(focused(out) if a.focused else historical(out) if a.historical else validate(out,a.smoke))
