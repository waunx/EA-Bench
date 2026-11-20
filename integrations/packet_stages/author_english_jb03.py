"""JB03 immutable English release authoring; no oracle material is mounted."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'data/authored/JB03'
RELEASE=ROOT/'data/expanded/JB03'
FRAME='Use the survey collection, institution and approval scope to determine which records apply to this university. Distinguish measured workload evidence from planning assumptions, and keep procurement, capacity, operating costs and the schedule consistent across all four deliverables.'
def build():
 if RELEASE.exists():raise FileExistsError(RELEASE)
 source=json.loads((SOURCE/'SOURCE.json').read_text());manifest={}
 reference=ROOT/'data/source/dataset/computer_and_information_research_scientists/task2/files_required_to_search/lbnl_datacenter_energy_report_2024.pdf'
 for variant,files in json.loads((SOURCE/'MANIFEST.json').read_text()).items():
  folder=RELEASE/'variants'/variant;folder.mkdir(parents=True)
  for name,digest in files.items():
   raw=(SOURCE/'variants'/variant/name).read_bytes();assert hashlib.sha256(raw).hexdigest()==digest
   if name=='prompt.md':raw=(source['original_text']+'\n'+FRAME+'\n').encode()
   dst=folder/name;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(raw)
  shutil.copyfile(reference,folder/'inputs'/reference.name)
  manifest[variant]={str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.rglob('*')) if p.is_file()}
 (RELEASE/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
 source.update(external_references_frozen=True,presentation_revision='Original English task retained verbatim; authored supplement provenance and clarification behavior integrated into narrative.',reference_sha256=hashlib.sha256(reference.read_bytes()).hexdigest(),reference_origin='Original JobBench files_required_to_search cached public LBNL report; retrieval date not recorded')
 (RELEASE/'SOURCE.json').write_text(json.dumps(source,indent=2)+'\n')
 (RELEASE/'private').mkdir();shutil.copyfile(SOURCE/'private/oracle.json',RELEASE/'private/oracle.json')
 (RELEASE/'check.py').write_text("from pathlib import Path\nimport sys, argparse, json\nsys.path.insert(0, str(Path(__file__).resolve().parents[3]))\nfrom integrations.packet_stages.validate_jb03 import main\nfrom integrations.packet_stages.jb03_checker import check, structural_checks\nif __name__ == '__main__':\n p=argparse.ArgumentParser();p.add_argument('--artifacts');p.add_argument('--private-root');p.add_argument('--variant',default='full');p.add_argument('--world-json');p.add_argument('--output');p.add_argument('--structural-only',action='store_true');a=p.parse_args()\n if not a.artifacts:main()\n else:\n  world=json.loads(Path(a.world_json).read_text()) if a.world_json else {}\n  if not a.structural_only and not a.private_root:p.error('--private-root is required for semantic evaluation')\n  result=structural_checks(a.artifacts) if a.structural_only else check(a.artifacts,a.private_root,a.variant,world)\n  if a.output:Path(a.output).write_text(json.dumps(result,indent=2)+'\\n')\n  print(json.dumps(result))\n  if result.get('status') in {'fail','failed','error','unavailable'}:raise SystemExit(1)\n")
if __name__=='__main__':build()
