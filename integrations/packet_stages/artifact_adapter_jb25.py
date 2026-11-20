"""LEEC public references; local inputs only come from the selected variant."""
import hashlib,json
from pathlib import Path
from .jb25_evidence import ROOT,PACKET,EXTERNAL
ORACLE_PATH=PACKET/'private/oracle.json'
REFERENCES={p.name:dict(path=p,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),url='https://www.eia.gov/electricity/sales_revenue_price/') for p in EXTERNAL.glob('*.xlsx')}
p=PACKET/'private/public_refs/PA_PUC_Chapter56.txt'
REFERENCES[p.name]=dict(path=p,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),url=json.loads((p.parent/'provenance.json').read_text())['url'])
def knowledge(facts):return {}
def check(artifacts,private_root,variant,world):
 from .run_artifact_case import configure_judge_from_eval
 from .jb25_checker import check as full_check
 return full_check(artifacts,private_root,variant,world,**configure_judge_from_eval())
