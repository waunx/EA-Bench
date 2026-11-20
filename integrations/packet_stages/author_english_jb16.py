"""JB16 skewed culvert estimate release with repaired duration leakage."""
import json,hashlib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'data/authored/JB16'
RELEASE=ROOT/'data/expanded/JB16'
REFERENCE_ROOT=ROOT/'data/source/dataset/civil_engineers/task1/files_required_to_search'
ASSET_ROOT=ROOT/'data/references/JB16'
URLS={'WSDOT_Bid_Tabulation_24Z011.pdf':'https://wsdot.wa.gov'}
FRAME='Use documented estimating assumptions and identify their cost effects. Distinguish calculated quantities and allowances from verified design quantities. Price each required work item once, accounting for work already included in installed unit rates.'
def build():
 if RELEASE.exists():raise FileExistsError(RELEASE)
 source=json.loads((SOURCE/'SOURCE.json').read_text());manifest={};oracle=json.loads((SOURCE/'private/oracle.json').read_text())
 for v,files in json.loads((SOURCE/'MANIFEST.json').read_text()).items():
  folder=RELEASE/'variants'/v
  for n,digest in files.items():
   raw=(SOURCE/'variants'/v/n).read_bytes();assert hashlib.sha256(raw).hexdigest()==digest
   if n=='prompt.md':raw=(source['original_text']+'\n'+FRAME+'\n').encode()
   if 'duration' in oracle['variants'][v]['missing']+oracle['variants'][v]['conflict'] and n.endswith('.csv'):
    raw=raw.replace(b'45-day project estimate',b'Project duration requires confirmation').replace(b'Typical 45-day project',b'Reference lump-sum allowance; current project duration not confirmed')
   dst=folder/n;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(raw)
  for n in URLS:shutil.copyfile(REFERENCE_ROOT/n,folder/'inputs'/n)
  for n in ['published_rebar_weights.csv','rebar_reference_provenance.json']:shutil.copyfile(ASSET_ROOT/n,folder/'inputs'/n)
  manifest[v]={str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()}
 (RELEASE/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
 source['external_references_frozen']=True
 source['published_bar_table']=json.loads((ASSET_ROOT/'rebar_reference_provenance.json').read_text())
 source['source_full_input_hashes']=source.pop('full_input_hashes',{})
 source['release_correction']='Duration-unknown variants also remove the current-project 45-day takeoff note and the 45-day allowance basis, which the historical packet leaked. Full remains byte-preserved; historical records untouched.'
 source['references']={n:dict(source_site=u,sha256=hashlib.sha256((REFERENCE_ROOT/n).read_bytes()).hexdigest(),origin='Original JobBench external reference cache; exact retrieval URL/date unrecorded') for n,u in URLS.items()}
 (RELEASE/'SOURCE.json').write_text(json.dumps(source,indent=2)+'\n');(RELEASE/'private').mkdir()
 for n in ['oracle.json','mc_pairs.json']:shutil.copyfile(SOURCE/'private'/n,RELEASE/'private'/n)
 s=(SOURCE/'check.py').read_text().replace('ROOT=Path(__file__).resolve().parent','ROOT=Path(__file__).resolve().parent.parent')
 s=s.replace("(ROOT/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\\n')","assert manifest==json.loads((ROOT/'MANIFEST.json').read_text()), 'Frozen packet hash mismatch'")
 (RELEASE/'private/packet_check.py').write_text(s)
 (RELEASE/'check.py').write_text('from pathlib import Path\nimport sys\nsys.path.insert(0,str(Path(__file__).resolve().parents[3]))\nfrom integrations.packet_stages.validate_jb16 import main\nif __name__=="__main__":main()\n')
if __name__=='__main__':build()
