"""JB09 public references and private company confirmations."""
import hashlib,json
from pathlib import Path
from .jb09_checker import ROOT,PACKET,check as full_check
REFERENCE_ROOT=ROOT/'data/source/dataset/computer_user_support_specialists/task2/files_required_to_search'
REFERENCES={p.name:dict(path=p,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),url=None) for p in REFERENCE_ROOT.iterdir() if p.is_file()}
p=PACKET/'references/microsoft_windows11_supported_intel.html'
REFERENCES[p.name]=dict(path=p,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),url='https://learn.microsoft.com/en-us/windows-hardware/design/minimum/supported/windows-11-supported-intel-processors')
def knowledge(facts):
 atoms=json.loads((PACKET/'private/oracle.json').read_text())['atoms']
 return {k:dict(value=v,answer=f"For the current MFS migration plan, {atoms[k]['issuer']} confirms {atoms[k]['subject']} is {v}.") for k,v in facts.items()}
def check(artifacts,private_root,variant,world):
 from .run_artifact_case import configure_judge_from_eval
 records=Path(private_root).parent/'user_records.json'
 return full_check(artifacts,private_root,variant,world,clarification_records=json.loads(records.read_text()) if records.exists() else [],**configure_judge_from_eval())
