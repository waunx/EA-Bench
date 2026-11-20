"""JB08 host-only facts and artifact-checker interface."""
import hashlib,json
from pathlib import Path
from .author_english_jb08 import REFERENCE_ROOT,URLS
from .jb08_checker import check as evaluate
REFERENCES={n:dict(path=REFERENCE_ROOT/n,sha256=hashlib.sha256((REFERENCE_ROOT/n).read_bytes()).hexdigest(),url=u) for n,u in URLS.items()}
def knowledge(facts):
 answers={'profit':f"For order CA-2016-152156, product FUR-BO-10001798, realized profit is {facts['profit']} dollars.",'quality_coupon':f"The Product Quality Guarantee goodwill discount code is {facts['quality_coupon']} percent.",'photo_required':'Photo documentation is '+('required' if facts['photo_required'] else 'not required')+' for Product Quality Guarantee claims.'}
 return {k:dict(value=v,answer=answers[k]) for k,v in facts.items()}
def check(artifacts,private_root,variant,world):
 from .run_artifact_case import configure_judge_from_eval
 p=Path(private_root).parent/'user_records.json'
 return evaluate(artifacts,private_root,variant,world,clarification_records=json.loads(p.read_text()) if p.exists() else [],**configure_judge_from_eval())
