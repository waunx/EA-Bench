"""JB08 authored English release with frozen traffic and review references."""
import json,hashlib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'data/authored/JB08'
RELEASE=ROOT/'data/expanded/JB08'
REFERENCE_ROOT=ROOT/'data/source/dataset/online_merchants/task2/files_required_to_search'
URLS={'website_traffic_data.csv':'https://archive.ics.uci.edu/dataset/468/online+shoppers+purchasing+intention+dataset','customer_reviews.csv':'https://www.kaggle.com/datasets/nicapotato/womens-ecommerce-clothing-reviews'}
FRAME='The traffic and customer-review CSVs are cached external reference datasets. Supplemental order records and policy excerpts are authored supporting business records.'
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
 source['references']={n:dict(url=u,sha256=hashlib.sha256((REFERENCE_ROOT/n).read_bytes()).hexdigest(),origin='Original JobBench external reference cache; retrieval date unrecorded') for n,u in URLS.items()}
 (RELEASE/'SOURCE.json').write_text(json.dumps(source,indent=2)+'\n');(RELEASE/'private').mkdir()
 for n in ['oracle.json','mc_pairs.json']:shutil.copyfile(SOURCE/'private'/n,RELEASE/'private'/n)
 s=(SOURCE/'check.py').read_text().replace('ROOT=Path(__file__).resolve().parent','ROOT=Path(__file__).resolve().parent.parent')
 s=s.replace("(ROOT/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\\n')","assert manifest==json.loads((ROOT/'MANIFEST.json').read_text()), 'Frozen packet hash mismatch'")
 (RELEASE/'private/packet_check.py').write_text(s)
 (RELEASE/'check.py').write_text('from pathlib import Path\nimport sys\nsys.path.insert(0,str(Path(__file__).resolve().parents[3]))\nfrom integrations.packet_stages.validate_jb08 import main\nif __name__=="__main__":main()\n')
if __name__=='__main__':build()
