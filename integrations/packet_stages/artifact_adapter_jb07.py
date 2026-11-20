"""JB07-only knowledge and public reference interface."""
from pathlib import Path
import hashlib,json
from .jb07_checker import check as full_check
ROOT=Path(__file__).resolve().parents[2];PACKET=ROOT/'data/expanded/JB07'
REFERENCE_ROOT=ROOT/'data/source/dataset/management_analysts/task3/files_required_to_search'
URLS={'NYC_MMR_Selected_Agencies.csv':'https://data.cityofnewyork.us/City-Government/Mayor-s-Management-Report-MMR-Agency-Performance-Indi/rbed-zzin','NYC_Staffing_Trends_2024.pdf':'https://www.osc.ny.gov/reports/osdc/2024-update-new-york-city-staffing-trends'}
REFERENCES={p.name:dict(path=p,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),url=URLS[p.name]) for p in REFERENCE_ROOT.iterdir() if p.is_file()}
def knowledge(facts):
 atoms=json.loads((PACKET/'private/oracle.json').read_text())['atoms']
 return {k:dict(value=v,answer=f"For Greenfield FY2024, the City confirms {atoms[k]['subject']} is {v}.") for k,v in facts.items()}
def check(artifacts,private_root,variant,world):
 from .run_artifact_case import configure_judge_from_eval
 records=Path(private_root).parent/'user_records.json'
 return full_check(artifacts,private_root,variant,world,clarification_records=json.loads(records.read_text()) if records.exists() else [],**configure_judge_from_eval())
