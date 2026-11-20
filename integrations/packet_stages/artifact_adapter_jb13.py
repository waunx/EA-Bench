"""JB13 host-side facts and source-aware credit artifact evaluation."""
import hashlib,json
from pathlib import Path
from .author_english_jb13 import REFERENCE_ROOT,URLS
from .jb13_checker import check as evaluate
REFERENCES={n:dict(path=REFERENCE_ROOT/n,sha256=hashlib.sha256((REFERENCE_ROOT/n).read_bytes()).hexdigest(),url=u) for n,u in URLS.items()}
def knowledge(facts):
 answers={'fico':f"For Derek Bowman, application APP-2025-006, the current verified FICO is {facts['fico']}.",'income':f"For Derek Bowman, application APP-2025-006, gross annual personal income is {facts['income']} US dollars.",'discharged':f"For Derek Bowman, application APP-2025-006, the Chapter 7 discharge date is {facts['discharged']}."}
 return {k:dict(value=v,answer=answers[k]) for k,v in facts.items()}
def check(artifacts,private_root,variant,world):
 from .run_artifact_case import configure_judge_from_eval
 p=Path(private_root).parent/'user_records.json'
 return evaluate(artifacts,private_root,variant,world,clarification_records=json.loads(p.read_text()) if p.exists() else [],**configure_judge_from_eval())
