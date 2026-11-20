"""Selected local inputs only; private confirmation and artifact evaluation."""
import json
from pathlib import Path
from .jb30_checker import PACKET,check as full_check
REFERENCES={}
ORACLE_PATH=PACKET/'private/oracle.json'
def knowledge(facts):
 atoms=json.loads(ORACLE_PATH.read_text())['atoms'];units={'warranty':' years','seat_capacity':' lbs','desk_low':' inches'}
 return {k:dict(value=v,answer='For quotation MOS-2025-04871, '+atoms[k]['issuer']+' confirms '+atoms[k]['subject']+' is '+str(v)+units[k]+'.') for k,v in facts.items()}
def check(artifacts,private_root,variant,world):
 from .run_artifact_case import configure_judge_from_eval
 records=Path(private_root).parent/'user_records.json'
 return full_check(artifacts,private_root,variant,world,clarification_records=json.loads(records.read_text()) if records.exists() else [],**configure_judge_from_eval())
