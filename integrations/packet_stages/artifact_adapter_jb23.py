"""Selected Meridian accounting inputs and IRS form reference."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[2];PACKET=ROOT/'data/expanded/JB23';ORACLE_PATH=PACKET/'private/oracle.json'
REF=ROOT/'data/source/dataset/bookkeeping_accounting_and_auditing_clerks/task1/files_required_to_search/IRS_Schedule_C_2024.pdf'
REFERENCES={REF.name:dict(path=REF,sha256=hashlib.sha256(REF.read_bytes()).hexdigest(),url='https://www.irs.gov/forms-pubs/about-schedule-c-form-1040')}
def knowledge(facts):
 atoms=json.loads(ORACLE_PATH.read_text())['atoms']
 return {k:dict(value=v,answer=f"For Meridian Digital Solutions, {atoms[k]['issuer']} confirms {atoms[k]['subject']} is {v}.") for k,v in facts.items()}
def check(artifacts,private_root,variant,world):
 from .jb23_checker import check as judge
 from .run_artifact_case import configure_judge_from_eval
 records=Path(private_root).parent/'user_records.json'
 return judge(Path(artifacts),Path(private_root),variant,world,clarification_records=json.loads(records.read_text()) if records.exists() else [],**configure_judge_from_eval())
