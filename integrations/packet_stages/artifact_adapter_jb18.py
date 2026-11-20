"""JB18 cached logistics tables and private customer-record confirmations."""
import hashlib,json
from .jb18_checker import ROOT,PACKET,check as full_check
REFERENCE_ROOT=ROOT/'data/source/dataset/management_analysts/task2/files_required_to_search'
REFERENCES={p.name:dict(path=p,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),url='https://brunel.figshare.com/articles/dataset/Supply_Chain_Logistics_Problem_Dataset/') for p in REFERENCE_ROOT.iterdir() if p.is_file()}
def knowledge(facts):
 atoms=json.loads((PACKET/'private/oracle.json').read_text())['atoms']
 return {k:dict(value=v,answer=f"For the current Q4 2023 customer records, the owner confirms {atoms[k]['subject']} is {v}.") for k,v in facts.items()}
def check(artifacts,private_root,variant,world):
 from .run_artifact_case import configure_judge_from_eval
 return full_check(artifacts,private_root,variant,world,**configure_judge_from_eval())
