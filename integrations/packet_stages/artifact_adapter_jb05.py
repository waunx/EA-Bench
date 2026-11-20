"""Host-only JB05 reference, user knowledge and complete artifact adapter."""
import hashlib,json
from pathlib import Path
from .jb05_checker import check as full_check
ROOT=Path(__file__).resolve().parents[2]
PACKET=ROOT/'data/expanded/JB05'
REFERENCE_ROOT=ROOT/'data/source/dataset/civil_engineers/task2/files_required_to_search'
URLS={'codot_2024_cost_data_book.pdf':'https://oitco.hylandcloud.com/cdotrmpop/docpop/docpop.aspx?docid=61241553','wisdot_average_unit_prices.pdf':'https://wisconsindot.gov/Pages/doing-bus/eng-consultants/cnslt-rsrces/strct/estimate.aspx'}
REFERENCES={p.name:dict(path=p,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),url=URLS[p.name]) for p in REFERENCE_ROOT.iterdir() if p.is_file()}
def knowledge(facts):
 atoms=json.loads((PACKET/'private/oracle.json').read_text())['atoms']
 return {k:dict(value=v,answer=f"For Bridge B-42-0117 in the 2025 project, the county confirms {atoms[k]['subject']} is {v}.") for k,v in facts.items()}
def check(artifacts,private_root,variant,world):
 from .run_artifact_case import configure_judge_from_eval
 return full_check(artifacts,private_root,variant,world,**configure_judge_from_eval())
