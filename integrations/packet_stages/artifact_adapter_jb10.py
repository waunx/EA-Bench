"""JB10 isolated-runner facts and assessment interface."""
import hashlib,json
from pathlib import Path
from .author_english_jb10 import REFERENCE_ROOT,URLS
from .jb10_checker import check as evaluate
REFERENCES={n:dict(path=REFERENCE_ROOT/n,sha256=hashlib.sha256((REFERENCE_ROOT/n).read_bytes()).hexdigest(),url=u) for n,u in URLS.items()}
def knowledge(facts):
 answers={'room':f"For the week starting April 14, 2025, Training Room B in Building 1 is {facts['room']}.",'robert_wed':f"Robert Williams is available on Wednesdays for {facts['robert_wed']}.",'robert_cap':f"Robert Williams may teach at most {facts['robert_cap']} sessions per week."}
 return {k:dict(value=v,answer=answers[k]) for k,v in facts.items()}
def check(artifacts,private_root,variant,world):
 from .run_artifact_case import configure_judge_from_eval
 p=Path(private_root).parent/'user_records.json'
 return evaluate(artifacts,private_root,variant,world,clarification_records=json.loads(p.read_text()) if p.exists() else [],**configure_judge_from_eval())
