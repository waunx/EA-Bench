"""JB27 selected inputs and reviewed external vibration guidance."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[2];PACKET=ROOT/'data/expanded/JB27';ORACLE_PATH=PACKET/'private/oracle.json'
REF=ROOT/'data/source/dataset/mechanical_engineering_technicians/task3/files_required_to_search'
REFERENCES={n:dict(path=REF/n,sha256=hashlib.sha256((REF/n).read_bytes()).hexdigest(),url=None) for n in ['europump_vibration_guidelines.pdf','iso10816_vibration_standard.pdf']}
def knowledge(facts):
 atoms=json.loads(ORACLE_PATH.read_text())['atoms']
 return {k:dict(value=v,answer=f"For P-2415A, {atoms[k]['issuer']} confirms {atoms[k]['subject']} is {v}.") for k,v in facts.items()}
def check(artifacts,private_root,variant,world):
 from .jb27_checker import check as judge
 from .run_artifact_case import configure_judge_from_eval
 records=Path(private_root).parent/'user_records.json'
 return judge(Path(artifacts),Path(private_root),variant,world,clarification_records=json.loads(records.read_text()) if records.exists() else [],**configure_judge_from_eval())
