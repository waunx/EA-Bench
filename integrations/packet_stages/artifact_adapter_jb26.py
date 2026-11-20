"""JB26 four variants with valid cached public references and semantic judging."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[2];PACKET=ROOT/'data/expanded/JB26'
ORACLE_PATH=PACKET/'private/oracle.json'
REF=ROOT/'data/source/dataset/licensing_examiners_and_inspectors/task1/files_required_to_search'
REFERENCES={n:dict(path=REF/n,sha256=hashlib.sha256((REF/n).read_bytes()).hexdigest(),url=u) for n,u in {'wa_contractor_license_subset.csv':'https://data.wa.gov/resource/m8qx-ubtq','wa_contractor_insurance_subset.csv':'https://data.wa.gov/resource/ciwg-agsx'}.items()}
def knowledge(facts):return {}
def check(artifacts,private_root,variant,world):
 from .jb26_checker import check as judge
 from .run_artifact_case import configure_judge_from_eval
 return judge(Path(artifacts),Path(private_root),variant,world,**configure_judge_from_eval())
