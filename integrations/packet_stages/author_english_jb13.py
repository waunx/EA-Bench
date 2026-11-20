"""JB13 risk-report and constrained credit-decision release."""
import json,hashlib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'data/authored/JB13'
RELEASE=ROOT/'data/expanded/JB13'
REFERENCE_ROOT=ROOT/'data/source/dataset/financial_managers_branch_or_department/task2/files_required_to_search'
URLS={'fdic_qbp_loan_performance_q4_2024.xlsx':'https://www.fdic.gov','rating_credit_risk_occ.pdf':'https://www.occ.treas.gov'}
FRAME='The supplied FDIC loan-performance workbook and OCC handbook are cached external references. Supplemental credit reports and application extracts, when present, are authored supporting records; use their applicant identity, reporting period and verification scope. Request clarification when a material proposed conclusion depends on an unresolved fact, or base the decision on sufficient independently supported grounds. Distinguish proposed conditions and unverified financial assumptions from approved waivers, confirmed borrower data or binding commitments.'
def build():
 if RELEASE.exists():raise FileExistsError(RELEASE)
 source=json.loads((SOURCE/'SOURCE.json').read_text());manifest={}
 for v,files in json.loads((SOURCE/'MANIFEST.json').read_text()).items():
  folder=RELEASE/'variants'/v
  for n,digest in files.items():
   raw=(SOURCE/'variants'/v/n).read_bytes();assert hashlib.sha256(raw).hexdigest()==digest
   if n=='prompt.md':raw=(source['original_text']+'\n'+FRAME+'\n').encode()
   dst=folder/n;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(raw)
  for n in URLS:shutil.copyfile(REFERENCE_ROOT/n,folder/'inputs'/n)
  manifest[v]={str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()}
 (RELEASE/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
 source['references']={n:dict(source_site=u,sha256=hashlib.sha256((REFERENCE_ROOT/n).read_bytes()).hexdigest(),origin='Original JobBench external reference cache; exact retrieval URL/date unrecorded') for n,u in URLS.items()}
 (RELEASE/'SOURCE.json').write_text(json.dumps(source,indent=2)+'\n');(RELEASE/'private').mkdir()
 for n in ['oracle.json','mc_pairs.json']:shutil.copyfile(SOURCE/'private'/n,RELEASE/'private'/n)
 s=(SOURCE/'check.py').read_text().replace('ROOT=Path(__file__).resolve().parent','ROOT=Path(__file__).resolve().parent.parent')
 s=s.replace("(ROOT/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\\n')","assert manifest==json.loads((ROOT/'MANIFEST.json').read_text()), 'Frozen packet hash mismatch'")
 (RELEASE/'private/packet_check.py').write_text(s)
 (RELEASE/'check.py').write_text('from pathlib import Path\nimport sys\nsys.path.insert(0,str(Path(__file__).resolve().parents[3]))\nfrom integrations.packet_stages.validate_jb13 import main\nif __name__=="__main__":main()\n')
if __name__=='__main__':build()
