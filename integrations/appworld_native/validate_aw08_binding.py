"""AW08 request amount/privacy/replacement controls, independent native effects."""
from ea_bench.paths import APPWORLD_ROOT, APPWORLD_PYTHON
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
from integrations.packet_stages.authored import reviewed_worlds
from integrations.packet_stages.open_aw08 import OpenAW08
from integrations.appworld_native.aw08_replay import ROOT,replay,captured

def actions_for(variant,answers):
    e=OpenAW08(variant,answers);t=e.checker.target;actions=[]
    for identity in t['cancel_requests']:
        actions.append(dict(tool='call',name='cancel_request',arguments={'request':identity}))
    for person,amount in t['new_requests'].items():
        actions.append(dict(tool='call',name='create_request',arguments=dict(
            person=person,event_ref='LUNCH-0928',amount_cents=amount,public=True,note='Lunch Meeting Order')))
    return actions

def world(job):
    variant,index,answers,output=job
    correct=actions_for(variant,answers);rows=[]
    labels=['correct','omission','wrong_amount','private']
    if any(a['name']=='cancel_request' for a in correct):labels.append('late_cancel')
    for label in labels:
        actions=deepcopy(correct)
        if label=='omission':actions=[]
        elif label=='wrong_amount':actions[-1]['arguments']['amount_cents']+=1
        elif label=='private':actions[-1]['arguments']['public']=False
        elif label=='late_cancel':actions.sort(key=lambda a:a['name']=='cancel_request')
        result=replay(variant,answers,actions,output/variant/str(index)/label)
        wanted=label in {'correct','late_cancel'}
        assert result['native_passed']==wanted,(variant,index,label,result['native_checks'])
        assert (result['supplemental']['status']=='passed')==(label=='correct')
        rows.append(dict(label=label,native_passed=result['native_passed'],supplemental=result['supplemental']['status']))
    return dict(variant=variant,world=index,controls=rows)

def validate(output,smoke=False):
    manifest=json.loads((ROOT/'data/expanded/AW08/MANIFEST.json').read_text())
    jobs=[(v,i,a,output) for v in manifest for i,(a,t) in enumerate(reviewed_worlds('AW08',v))]
    if smoke:jobs=jobs[:1]
    with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(world,jobs))
    result=dict(case='AW08',status='passed',worlds=len(rows),variants=len({r['variant'] for r in rows}),rows=rows)
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def historical(output):
    from hashlib import sha256
    batch=ROOT/'experiments/full-evaluation-gpt55-20261011/AW08'
    manifest=json.loads((ROOT/'data/expanded/AW08/MANIFEST.json').read_text());rows=[]
    for variant in manifest:
        episode=batch/variant/'attempt-1'
        config=json.loads((episode/'configuration.json').read_text())
        folder=ROOT/'data/expanded/AW08/variants'/variant
        assert config['packet_hashes']=={str(p.relative_to(folder)):sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()}
        path=episode/'private/events.jsonl'
        events=[json.loads(s) for s in path.read_text().splitlines()]
        answers=json.loads((episode/'private/world.json').read_text())
        result=replay(variant,answers,captured(events),output/variant)
        rows.append(dict(variant=variant,native_passed=result['native_passed'],trace_sha256=sha256(path.read_bytes()).hexdigest(),packet_identity_verified=True))
    (output/'result.json').write_text(json.dumps(rows,indent=2)+'\n')
    return rows

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--smoke',action='store_true');p.add_argument('--historical',action='store_true');p.add_argument('--baseline',action='store_true')
    a=p.parse_args();out=a.out.resolve()
    if a.baseline:
        import os,subprocess
        env=dict(os.environ,APPWORLD_ROOT=APPWORLD_ROOT,PYTHONPATH=str(ROOT),OPENBLAS_NUM_THREADS='1')
        subprocess.run([APPWORLD_PYTHON,'-m','integrations.appworld_native.aw08_baseline','--out',str(out)],cwd=APPWORLD_ROOT,env=env,check=True)
    else:
        out.mkdir(parents=True,exist_ok=True)
        print(historical(out) if a.historical else validate(out,a.smoke))
