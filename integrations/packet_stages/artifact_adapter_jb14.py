from .jb14_checker import check as full_check
from .author_english_jb14 import REFERENCE_ROOT
import hashlib,json
from pathlib import Path
REFERENCES={p.name:dict(path=p,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in REFERENCE_ROOT.glob('*.csv')}
def knowledge(facts):
 sentences={'ship_day':f"The confirmed shipment date for order 3535, item 8793 is February {facts['ship_day']}, 2015.",'discount':f"The confirmed discount for order 3535, item 8793 is {facts['discount']*100:g}%.",'profit':f"The confirmed realized profit for order 3535, item 8793 is ${facts['profit']:g}."}
 return {k:dict(value=facts[k],answer=v) for k,v in sentences.items()}
def check(artifacts,private_root,variant,world):
 from .run_artifact_case import configure_judge_from_eval
 records=Path(private_root).parent/'user_records.json'
 return full_check(artifacts,private_root,variant,world,clarification_records=json.loads(records.read_text()) if records.exists() else [],**configure_judge_from_eval())
