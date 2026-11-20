"""JB06-specific English release: month-end reconciliation and invoice evidence."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'data/authored/JB06'
RELEASE=ROOT/'data/expanded/JB06'
REFERENCE=ROOT/'data/source/dataset/bookkeeping_accounting_and_auditing_clerks/task2/files_required_to_search/IRS_Schedule_C_Form_2024.pdf'
URL='https://www.irs.gov/pub/irs-prior/f1040sc--2024.pdf'
FRAME='Use document identity, invoice and service dates, payment status and revision information to determine accounting relevance. Distinguish proposed adjustments from approved entries, and document the accounting basis and transaction-matching assumptions for the accountant reviewing the close.'
def build():
 if RELEASE.exists():raise FileExistsError(RELEASE)
 source=json.loads((SOURCE/'SOURCE.json').read_text());old=json.loads((SOURCE/'MANIFEST.json').read_text());manifest={}
 for variant,files in old.items():
  folder=RELEASE/'variants'/variant
  for name,digest in files.items():
   raw=(SOURCE/'variants'/variant/name).read_bytes();assert hashlib.sha256(raw).hexdigest()==digest
   if name=='prompt.md':raw=(source['original_text']+'\n'+FRAME+'\n').encode()
   dst=folder/name;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(raw)
  shutil.copyfile(REFERENCE,folder/'inputs'/REFERENCE.name)
  manifest[variant]={str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()}
 (RELEASE/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
 source.update(presentation_revision='Original English text verbatim plus integrated provenance and clarification narrative.',reference=dict(name=REFERENCE.name,url=URL,sha256=hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),origin='Original JobBench cached files_required_to_search; retrieval date unrecorded'))
 (RELEASE/'SOURCE.json').write_text(json.dumps(source,indent=2)+'\n');(RELEASE/'private').mkdir()
 for name in ['oracle.json','mc_pairs.json']:shutil.copyfile(SOURCE/'private'/name,RELEASE/'private'/name)
 # Preserve reviewed case-specific calculations; never regenerate the manifest during checks.
 oldcheck=(SOURCE/'check.py').read_text().replace("ROOT=Path(__file__).resolve().parent", "ROOT=Path(__file__).resolve().parent.parent")
 oldcheck=oldcheck.replace("(ROOT/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\\n')", "assert manifest==json.loads((ROOT/'MANIFEST.json').read_text()), 'Frozen packet hash mismatch'")
 (RELEASE/'private/packet_check.py').write_text(oldcheck)
 (RELEASE/'check.py').write_text("from integrations.packet_stages.validate_jb06 import main\nif __name__=='__main__':main()\n")
if __name__=='__main__':build()
