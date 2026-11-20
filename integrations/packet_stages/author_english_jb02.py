"""Preserve JB02 original narrative and independently reviewed redundant records."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'data/authored/JB02'
PACKET=ROOT/'data/expanded/JB02'
REFERENCE_ROOT=ROOT/'data/source/dataset/statisticians/task3/files_required_to_search'
REFERENCES={
 'education_attainment_1970_2023.csv':'https://www.ers.usda.gov/data-products/county-level-data-sets/educational-attainment',
 'population_estimates_2020_23.csv':'https://www.ers.usda.gov/data-products/county-level-data-sets/population',
 'unemployment_income_2000_23.csv':'https://www.ers.usda.gov/data-products/county-level-data-sets/unemployment',
 'us_states.geojson':'https://raw.githubusercontent.com/PublicaMundi/MappingAPI/master/data/geojson/us-states.json'}
def build():
 source=json.loads((SOURCE/'SOURCE.json').read_text());manifest={};catalog=[]
 for name,url in REFERENCES.items():
  p=REFERENCE_ROOT/name if name.endswith('.csv') else ROOT/'data/references/JB02'/name
  catalog.append(dict(file=name,url=url,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),origin='Original JobBench cached external file' if name.endswith('.csv') else 'PublicaMundi simplified state boundaries, downloaded 2026-10-11; spatial proxy, not original JobBench data'))
 for variant,files in json.loads((SOURCE/'MANIFEST.json').read_text()).items():
  manifest[variant]={}
  for name,digest in files.items():
   raw=(SOURCE/'variants'/variant/name).read_bytes();assert hashlib.sha256(raw).hexdigest()==digest
   if name=='prompt.md':raw=(source['original_text']+'\n\nUse the reference-source service to retrieve cached external sources and document their provenance. Supplemental health extracts, when supplied, are authored records with their own geography and prevalence type; reconcile them according to the county-level crude-prevalence scope of this analysis. Explain limitations of the simplified state boundary proxy used for spatial analysis.\n').encode()
   p=PACKET/'variants'/variant/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw);manifest[variant][name]=hashlib.sha256(raw).hexdigest()
  raw=(json.dumps(catalog,indent=2)+'\n').encode();name='inputs/reference_sources.json';(PACKET/'variants'/variant/name).write_bytes(raw);manifest[variant][name]=hashlib.sha256(raw).hexdigest()
 source.update(data_origin='Full retains the original local CSV files. R1 adds an authored tract record; R2 also adds an authored age-adjusted county record; R3 also adds an authored exact county crude copy. The source catalog and simplified geometry access are authored supplements, not native snapshots.',references=catalog,presentation_revision='English source-service instruction and explicit authored-extract provenance; original text verbatim',added_condition_purpose='Make external-data access reproducible while retaining county crude-prevalence scope',original_rubric_compatibility='Unchanged original rubrics plus private task-completeness criteria for original requirements omitted from RUBRICS.json')
 (PACKET/'SOURCE.json').write_text(json.dumps(source,indent=2)+'\n');(PACKET/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
if __name__=='__main__':build()
