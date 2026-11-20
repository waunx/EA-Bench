"""JB14 network-capacity audit: case-specific release narrative and source binding."""
from pathlib import Path
import json,hashlib,shutil
ROOT=Path(__file__).resolve().parents[2];SOURCE=ROOT/'data/authored/JB14';PACKET=ROOT/'data/expanded/JB14';REFERENCE_ROOT=ROOT/'data/source/dataset/supply_chain_managers/task2/files_required_to_search'
FRAME='Base the network service and financial comparison on reconciled shipment-level dispatch timing, discounted sales and realized profit across customer outbound activity. Use these measures to assess which demand corridors create service exposure and how the investment alternatives affect the business. Obtain the cached inventory and fulfillment files through the reference-source service. Additional logistics records, commercial documents and source renditions supplied with this task are authored supplemental datasets. Distinguish storage capacity, shipped units, order lines and throughput, and disclose conversion, growth, cost and warehouse-allocation assumptions used in the capital comparison.'
def build():
 PACKET.mkdir(exist_ok=False);source=json.loads((SOURCE/'SOURCE.json').read_text());refs=[]
 for f in sorted(REFERENCE_ROOT.iterdir()):refs.append(dict(file=f.name,sha256=hashlib.sha256(f.read_bytes()).hexdigest(),origin='Original JobBench cached Just In Time source copy; acquisition date not recorded'))
 for v,files in json.loads((SOURCE/'MANIFEST.json').read_text()).items():
  for n,h in files.items():
   raw=(SOURCE/'variants'/v/n).read_bytes();assert hashlib.sha256(raw).hexdigest()==h
   if n=='prompt.md':raw=(source['original_text']+'\n'+FRAME+'\n').encode()
   p=PACKET/'variants'/v/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
  (PACKET/'variants'/v/'inputs/reference_sources.json').write_text(json.dumps(refs,indent=2)+'\n')
 shutil.copytree(SOURCE/'private',PACKET/'private',ignore=shutil.ignore_patterns('check_result.json'));shutil.copyfile(SOURCE/'check.py',PACKET/'decision_check.py')
 source.update(references=refs,presentation_revision='English original preserved with transaction reconciliation, source-scope handling and modeling assumption requirements integrated.')
 (PACKET/'SOURCE.json').write_text(json.dumps(source,indent=2)+'\n')
 (PACKET/'check.py').write_text('from pathlib import Path\nimport runpy,sys\np=Path(__file__).resolve().parent\nsys.path.insert(0,str(p.parents[2]))\nrunpy.run_path(str(p/"decision_check.py"),run_name="__main__")\nfrom integrations.packet_stages.validate_jb14 import validate\nvalidate(p)\n')
if __name__=='__main__':build()
