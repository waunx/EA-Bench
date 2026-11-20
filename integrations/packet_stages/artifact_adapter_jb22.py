"""JB22 exposes only genuine public guidance/calculator references."""
import hashlib,json
from .jb22_checker import ROOT,PACKET,check as full_check
REFERENCE_ROOT=ROOT/'data/source/dataset/biostatisticians/task1/files_required_to_search'
URLS={'FDA_E9_Statistical_Principles_Clinical_Trials.pdf':'https://www.fda.gov/regulatory-information/search-fda-guidance-documents/e9-statistical-principles-clinical-trials','Sample_Size_Calculator_v2.0.xls':'https://wnarifin.github.io/'}
REFERENCES={name:dict(path=REFERENCE_ROOT/name,sha256=hashlib.sha256((REFERENCE_ROOT/name).read_bytes()).hexdigest(),url=url) for name,url in URLS.items()}
def knowledge(facts):
 atoms=json.loads((PACKET/'private/oracle.json').read_text())['atoms']
 return {k:dict(value=v,answer=f"For XR-2847, the protocol owner confirms {atoms[k]['subject']} is {v}.") for k,v in facts.items()}
def check(artifacts,private_root,variant,world):
 from .run_artifact_case import configure_judge_from_eval
 return full_check(artifacts,private_root,variant,world,**configure_judge_from_eval())
