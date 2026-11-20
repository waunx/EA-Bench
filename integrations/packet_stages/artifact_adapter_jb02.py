from pathlib import Path
import hashlib
from .author_english_jb02 import REFERENCES as URLS,REFERENCE_ROOT,ROOT
from .jb02_acceptance import check as check_artifacts
REFERENCES={}
for name,url in URLS.items():
 path=REFERENCE_ROOT/name if name.endswith('.csv') else ROOT/'data/references/JB02'/name
 REFERENCES[name]=dict(path=path.resolve(),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),url=url)
def knowledge(facts):
 return {}

def check(artifacts,private_root,variant,world):
 from .run_artifact_case import configure_judge_from_eval
 return check_artifacts(artifacts,private_root,variant,world,**configure_judge_from_eval())
