"""JB06 isolated artifact runner adapter."""
import hashlib,json
from pathlib import Path
from .author_english_jb06 import REFERENCE,URL
from .jb06_checker import check as evaluate
REFERENCES={REFERENCE.name:dict(path=REFERENCE,sha256=hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),url=URL)}
def knowledge(facts):
 labels={'issued':'invoice issue date','amount':'total amount in cents','due':'contractual due date'}
 return {k:dict(value=v,answer=f'For Ace Hardware invoice INV-2024-0435, the confirmed {labels[k]} is {v}.') for k,v in facts.items()}
def check(artifacts,private_root,variant,world):
 from .run_artifact_case import configure_judge_from_eval
 records=Path(private_root).parent/'user_records.json'
 return evaluate(artifacts,private_root,variant,world,clarification_records=json.loads(records.read_text()) if records.exists() else [],**configure_judge_from_eval())
