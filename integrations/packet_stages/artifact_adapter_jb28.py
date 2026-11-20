"""JB28 selected client files and original searched public references."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[2]
PACKET=ROOT/'data/expanded/JB28'
ORACLE_PATH=PACKET/'private/oracle.json'
REF=ROOT/'data/source/dataset/personal_financial_advisors/task1/files_required_to_search'
REFERENCES={n:dict(path=REF/n,sha256=hashlib.sha256((REF/n).read_bytes()).hexdigest(),url=u) for n,u in {
 'treasury_yield_curve_2024.csv':'https://home.treasury.gov/resource-center/data-chart-center/interest-rates',
 'sp500_monthly_2024.csv':'https://fred.stlouisfed.org/series/SP500',
 'irs_pub590b_rmd_tables.pdf':'https://www.irs.gov/publications/p590b'}.items()}
def knowledge(facts):
 atoms=json.loads(ORACLE_PATH.read_text())['atoms']
 return {k:dict(value=v,answer=f"For the Chens' planning analysis, {atoms[k]['issuer']} confirms {atoms[k]['subject']} is {v}.") for k,v in facts.items()}
def check(artifacts,private_root,variant,world):
 from .jb28_checker import check as judge
 from .run_artifact_case import configure_judge_from_eval
 records=Path(private_root).parent/'user_records.json'
 return judge(Path(artifacts),Path(private_root),variant,world,clarification_records=json.loads(records.read_text()) if records.exists() else [],**configure_judge_from_eval())
