import hashlib
from .author_english_jb01 import REFERENCES as URLS, REFERENCE_ROOT
from .jb01_acceptance import check as check_artifacts
REFERENCES={name:dict(path=REFERENCE_ROOT/name,sha256=hashlib.sha256((REFERENCE_ROOT/name).read_bytes()).hexdigest(),url=url) for name,url in URLS.items()}
def knowledge(facts):
 return {
  'life':dict(value=facts['life'],answer=f"The confirmed Alabama state life expectancy is {facts['life']} years."),
  'obesity':dict(value=facts['obesity'],answer=f"The confirmed Alabama 2023 total-adult obesity point estimate is {facts['obesity']} percent."),
  'education':dict(value=facts['education'],answer=f"The confirmed Alabama bachelor degree or higher estimate is {facts['education']} percent.")}
def check(artifacts,private_root,variant,world):
 from .run_artifact_case import configure_judge_from_eval
 return check_artifacts(artifacts,private_root,variant,world,**configure_judge_from_eval())
