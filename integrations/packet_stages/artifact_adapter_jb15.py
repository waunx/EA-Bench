"""JB15 public references and private study-custodian confirmations."""
import hashlib,json
from .jb15_checker import ROOT,PACKET,check as full_check
REFERENCE_ROOT=ROOT/'data/source/dataset/social_science_research_assistants/task3/files_required_to_search'
URLS={'Climate_Change_Opinion_Survey_Codebooks_2021to2023.xlsx':'https://data.humdata.org/dataset/climate-change-opinion-survey','ESS_Climate_Change_Topline_Results.pdf':'https://www.europeansocialsurvey.org/findings/topline-series'}
REFERENCES={p.name:dict(path=p,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),url=URLS[p.name]) for p in REFERENCE_ROOT.iterdir() if p.is_file()}
def knowledge(facts):
 atoms=json.loads((PACKET/'private/oracle.json').read_text())['atoms']
 return {k:dict(value=v,answer=f"For the supplied study snapshot, the custodian confirms {atoms[k]['subject']} is {v}.") for k,v in facts.items()}
def check(artifacts,private_root,variant,world):
 from .run_artifact_case import configure_judge_from_eval
 return full_check(artifacts,private_root,variant,world,**configure_judge_from_eval())
