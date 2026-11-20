"""JB19 dated early-alert and evidence-based advising release."""
import json,hashlib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'data/authored/JB19'
RELEASE=ROOT/'data/expanded/JB19'
REFERENCE_ROOT=ROOT/'data/source/dataset/sociology_teachers_postsecondary/task1/task_folder'
ASSET_ROOT=Path(__file__).parent/'jb19_reference_assets'
URLS={'Effective_Advising_Practice_Guide.pdf':'https://ies.ed.gov/ncee/wwc/'}
FRAME='The advising guide, Portuguese student dataset and accompanying UCI coding dictionary are supplied reference resources. Any additional course-policy records or dated student-record extracts supplied with this task are authored supplemental datasets.'
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
  for n in ['UCI_Student_Performance_Data_Dictionary.txt','uci_reference_provenance.json']:shutil.copyfile(ASSET_ROOT/n,folder/'inputs'/n)
  manifest[v]={str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()}
 (RELEASE/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
 source['external_references_frozen']=True
 source['source_full_input_hashes']=source.pop('full_input_hashes',{})
 source['uci_dictionary_reference']=json.loads((ASSET_ROOT/'uci_reference_provenance.json').read_text())
 source['references']={n:dict(source_site=u,sha256=hashlib.sha256((REFERENCE_ROOT/n).read_bytes()).hexdigest(),origin='Original JobBench external reference cache; exact retrieval URL/date unrecorded') for n,u in URLS.items()}
 (RELEASE/'SOURCE.json').write_text(json.dumps(source,indent=2)+'\n');(RELEASE/'private').mkdir()
 for n in ['oracle.json','mc_pairs.json']:shutil.copyfile(SOURCE/'private'/n,RELEASE/'private'/n)
 s=(SOURCE/'check.py').read_text().replace('ROOT=Path(__file__).resolve().parent','ROOT=Path(__file__).resolve().parent.parent')
 s=s.replace("(ROOT/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\\n')","assert manifest==json.loads((ROOT/'MANIFEST.json').read_text()), 'Frozen packet hash mismatch'")
 s=s.replace('    for bits in itertools.product','    checked_worlds=[]\n    for bits in itertools.product')
 s=s.replace('        assert project(data,answers)==EXPECTED[label],(name,label,project(data,answers),EXPECTED[label])','        assert project(data,answers)==EXPECTED[label],(name,label,project(data,answers),EXPECTED[label])\n        checked_worlds.append(dict(answers=answers,expected=EXPECTED[label]))')
 s=s.replace('worlds_checked=2**len(unknown),input_hashes=hashes','worlds_checked=2**len(unknown),reviewed_worlds=checked_worlds,input_hashes=hashes')
 (RELEASE/'private/packet_check.py').write_text(s)
 (RELEASE/'check.py').write_text('from pathlib import Path\nimport sys\nsys.path.insert(0,str(Path(__file__).resolve().parents[3]))\nfrom integrations.packet_stages.validate_jb19 import main\nif __name__=="__main__":main()\n')
if __name__=='__main__':build()
