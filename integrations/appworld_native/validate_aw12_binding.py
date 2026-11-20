"""AW12 migrated library controls: missing song and wrong playlist privacy."""
import argparse,json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from integrations.packet_stages.english_packet import ROOT,RELEASE
from integrations.packet_stages.authored import reviewed_worlds
from integrations.packet_stages.english_aw12 import fact,load
from .aw12_replay import replay

def actions_for(variant,answers,target):
 account='AC'+str(1000+len(load(variant)['account_registry.json']))
 def action(operation,**args):return dict(tool='call',name=operation,arguments=args)
 actions=[action('verify_backup',file=fact(load(variant),'batch',answers)),action('create_account')]
 actions += [action('add_song',account=account,track=t) for t in target['songs']]
 actions += [action('add_album',account=account,album=a) for a in target['albums']]
 actions += [action('create_playlist',account=account,**p) for p in target['playlists']]
 return actions

def world(job):
 output,variant,i,answers,target=job;actions=actions_for(variant,answers,target)
 missing=[a for a in actions if not (a['name']=='add_song' and a['arguments']['track']==target['songs'][0])]
 privacy=json.loads(json.dumps(actions));p=next(a for a in privacy if a['name']=='create_playlist');p['arguments']['private']=not p['arguments']['private']
 rows=[]
 for label,act in [('positive',actions),('missing_song',missing),('wrong_privacy',privacy)]:
  folder=output/variant/str(i)/label;r=replay(variant,answers,act,folder)
  assert r['native_passed']==(label=='positive'),(variant,i,label,r['native_checks'])
  assert r['supplemental_verdict']['success']==(label=='positive')
  rows.append(dict(label=label,native_passed=r['native_passed'],evidence=str(folder.relative_to(ROOT))))
 return dict(variant=variant,world=i,status='passed',controls=rows)

def validate(output):
 output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True);jobs=[]
 for variant in json.loads((RELEASE/'AW12/MANIFEST.json').read_text()):
  jobs += [(output,variant,i,a,t) for i,(a,t) in enumerate(reviewed_worlds('AW12',variant))]
 with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(world,jobs))
 result=dict(case='AW12',variants=len({r['variant'] for r in rows}),worlds=len(rows),branch_controls=rows,original_evaluator_runs=0,layer='Actual Spotify API and DB checks on authored supplemental worlds')
 (output/'result.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(validate(a.output)))
