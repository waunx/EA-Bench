"""JB04 host adapter; no private facts are needed for redundant variants."""
import hashlib
from .author_english_jb04 import REFERENCE_ROOT,REFERENCES as URLS
from .jb04_checker import check as full_check
REFERENCES={name:dict(path=REFERENCE_ROOT/name,sha256=hashlib.sha256((REFERENCE_ROOT/name).read_bytes()).hexdigest(),url=url) for name,url in URLS.items()}
def knowledge(facts):return {}
def check(artifacts,private_root,variant,world):
    if variant not in ['full','R1','R2','R3']:raise ValueError('Unknown JB04 variant')
    from .run_artifact_case import configure_judge_from_eval
    return full_check(artifacts,private_root,**configure_judge_from_eval())
