"""JB12 external FQHC references; no hidden factual clarifications."""
import hashlib
from .jb12_checker import ROOT,check as full_check
REFERENCE_ROOT=ROOT/'data/source/dataset/medical_and_health_services_managers/task1/files_required_to_search'
URLS={'CMS_FQHC_PPS_Rate_Update_2025.pdf':'https://www.cms.gov/files/document/r12951cp.pdf','Florida_FQHC_Medicaid_Rates_Oct2024.xlsx':'https://ahca.myflorida.com/medicaid/cost-reimbursement/fqhc-rhc'}
REFERENCES={p.name:dict(path=p,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),url=URLS[p.name]) for p in REFERENCE_ROOT.iterdir() if p.is_file()}
def knowledge(facts):return {}
def check(artifacts,private_root,variant,world):
 from .run_artifact_case import configure_judge_from_eval
 return full_check(artifacts,private_root,variant,world,**configure_judge_from_eval())
