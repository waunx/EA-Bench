"""JB03-only interface for the shared isolated artifact runner."""
import hashlib,json
from pathlib import Path
from .author_english_jb03 import ROOT,RELEASE
from .jb03_checker import check as check_artifacts
PATH=ROOT/'data/source/dataset/computer_and_information_research_scientists/task2/files_required_to_search/lbnl_datacenter_energy_report_2024.pdf'
REFERENCES={PATH.name:dict(path=PATH,sha256=hashlib.sha256(PATH.read_bytes()).hexdigest(),url='https://eta-publications.lbl.gov/sites/default/files/2024-12/lbnl-2024-united-states-data-center-energy-usage-report.pdf')}
def knowledge(facts):
 atoms=json.loads((RELEASE/'private/oracle.json').read_text())['atoms'];out={}
 for key,value in facts.items():
  if key not in atoms:raise ValueError('Unknown JB03 fact: '+key)
  a=atoms[key];out[key]=dict(value=value,answer=f"For {a['database']}, table {a['table']}, row id {a['id']}, the confirmed {a['field']} value is {value}.")
 return out

def check(artifacts,private_root,variant,world):
 from .run_artifact_case import configure_judge_from_eval
 records=Path(private_root).parent/'user_records.json'
 return check_artifacts(artifacts,private_root,variant,world,clarification_records=json.loads(records.read_text()) if records.exists() else [],**configure_judge_from_eval())
