"""JB01 explicit primary study frame; no private rubric or results in inputs."""
import hashlib,json,re
from .authored import SOURCE,read_json
from .english_packet import RELEASE,ROOT
PACKET=RELEASE/'JB01'
FRAME="For this audit, use 2023 total-adult obesity estimates in the primary analysis to align the exposure year with the requested socioeconomic estimates. The primary cohort must include every jurisdiction represented by state-level outcome, 2023 total-adult exposure and education records in the study inputs. Use the study point estimates and document source provenance, cohort eligibility and temporal limitations. The supplied study inputs are authored supplements. Use the reference-source service for the original task's cached external files. Submit the technical memo as a PDF so reviewers receive a stable paginated copy."
REFERENCES={
    'state_poverty_2023.csv':'https://ers.usda.gov/media/5496/poverty-estimates-for-the-united-states-states-and-counties-2023.csv',
    'state_unemployment_2023.csv':'https://ers.usda.gov/media/5497/unemployment-and-median-household-income-for-the-united-states-states-and-counties-2000-23.csv',
    'covid_vax_final_snapshot.csv':'https://data.cdc.gov/api/views/unsk-b7fc/rows.csv',
    'us_census_regions_divisions.pdf':'https://www2.census.gov/programs-surveys/sahie/reference-maps/2022/us_regdiv.pdf'}
REFERENCE_ROOT=ROOT/'data/source/dataset/statisticians/task1/files_required_to_search'

def build():
    if (PACKET/'MANIFEST.json').exists():raise FileExistsError('JB01 already exists')
    source=read_json(SOURCE/'JB01/SOURCE.json');manifest={}
    catalog=[dict(file=name,url=url,origin='Original JobBench files_required_to_search copy; download date not recorded',sha256=hashlib.sha256((REFERENCE_ROOT/name).read_bytes()).hexdigest()) for name,url in REFERENCES.items()]
    for variant,hashes in read_json(SOURCE/'JB01/MANIFEST.json').items():
        manifest[variant]={};files={}
        for name,digest in hashes.items():
            raw=(SOURCE/'JB01/variants'/variant/name).read_bytes();assert hashlib.sha256(raw).hexdigest()==digest
            if name=='prompt.md':raw=(source['original_text']+'\n'+FRAME+'\n').encode()
            assert not re.search('[\u3400-\u9fff]',raw.decode()),name
            files[name]=raw
        files['inputs/reference_sources.json']=(json.dumps(catalog,indent=2)+'\n').encode()
        for name,raw in files.items():
            p=PACKET/'variants'/variant/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
            manifest[variant][name]=hashlib.sha256(raw).hexdigest()
    source.update(presentation_revision='Explicit authored 2023 primary study frame and cohort-preservation requirement',
        added_condition_purpose='Align authored exposure variants to requested 2023 socioeconomic sources; avoid dropping unresolved local point estimates',
        references=catalog,original_rubric_compatibility='Original private rubric assumes 2021 obesity; separately identified adapted full-artifact acceptance is required')
    (PACKET/'SOURCE.json').write_text(json.dumps(source,indent=2)+'\n')
    (PACKET/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Authored JB01',len(manifest),'variants; full artifact acceptance still pending')
if __name__=='__main__':build()
