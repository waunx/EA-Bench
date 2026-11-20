"""JB29 selected simulation inputs and full public historical source."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[2];PACKET=ROOT/'data/expanded/JB29';ORACLE_PATH=PACKET/'private/oracle.json'
REF=PACKET/'references/911_calls_montcoalert.csv'
REFERENCES={REF.name:dict(path=REF,sha256=hashlib.sha256(REF.read_bytes()).hexdigest(),url='https://www.kaggle.com/datasets/mchirico/montcoalert')}
def knowledge(facts):
 atoms=json.loads(ORACLE_PATH.read_text())['atoms']
 return {k:dict(value=v,answer=f"For the09:00 dispatch simulation, {atoms[k]['issuer']} confirms {atoms[k]['subject']} is {v}.") for k,v in facts.items()}
def check(artifacts,private_root,variant,world):
 from .jb29_checker import check as judge
 from .run_artifact_case import configure_judge_from_eval
 records=Path(private_root).parent/'user_records.json'
 return judge(Path(artifacts),Path(private_root),variant,world,clarification_records=json.loads(records.read_text()) if records.exists() else [],**configure_judge_from_eval())
