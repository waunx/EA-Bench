"""JB16 isolated artifact evaluation and source references."""
import hashlib,json
from pathlib import Path
from .author_english_jb16 import REFERENCE_ROOT,URLS,ASSET_ROOT
from .jb16_checker import check as evaluate
REFERENCES={n:dict(path=REFERENCE_ROOT/n,sha256=hashlib.sha256((REFERENCE_ROOT/n).read_bytes()).hexdigest(),url=u) for n,u in URLS.items()}
REFERENCES['published_rebar_weights.csv']=dict(path=ASSET_ROOT/'published_rebar_weights.csv',sha256=hashlib.sha256((ASSET_ROOT/'published_rebar_weights.csv').read_bytes()).hexdigest(),url='https://en.wikipedia.org/wiki/Rebar')
def knowledge(facts):
 answers={'duration':f"For project RC-2024-BC-0847, the confirmed estimated construction duration is {facts['duration']} working days.",'material':f"The 10x8 precast culvert material component is {facts['material']} US dollars per linear foot.",'installation':f"The 10x8 precast culvert installation labor component is {facts['installation']} US dollars per linear foot."}
 return {k:dict(value=v,answer=answers[k]) for k,v in facts.items()}
def check(artifacts,private_root,variant,world):
 from .run_artifact_case import configure_judge_from_eval
 p=Path(private_root).parent/'user_records.json'
 return evaluate(artifacts,private_root,variant,world,clarification_records=json.loads(p.read_text()) if p.exists() else [],**configure_judge_from_eval())
