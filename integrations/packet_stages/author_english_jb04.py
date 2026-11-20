"""Preserve JB04 original English task and scope-safe redundant evidence."""
import hashlib,json
from pathlib import Path
from .authored import SOURCE
from .english_packet import RELEASE,ROOT
PACKET=RELEASE/'JB04'
REFERENCE_ROOT=ROOT/'data/source/dataset/civil_engineers/task3/files_required_to_search'
REFERENCES={
'CODOT_2024_Cost_Data_Book.pdf':'https://oitco.hylandcloud.com/cdotrmpop/docpop/docpop.aspx?docid=61241553',
'CODOT_2024_Item_Code_Book.xlsx':'https://www.codot.gov/business/eema/assets/2024-item-code-book-1.xlsx',
'Michigan_LAP_Bridge_Cost_Estimating_Worksheet.pdf':'https://mml.org/inside208/wp-content/uploads/sites/3/2024/02/Exhibit-4-2024-LAP-Bridge-Cost-Estimating-Worksheet.pdf'}
FRAME='Use the reference-source service to obtain cached copies of the external pricing and item-code publications. Cite the publications and identify any pricing assumptions. Supplemental inspection records and memo extracts, where supplied, are authored reference aids with their own structure identifiers and source attribution.'
def build():
    if PACKET.exists():raise FileExistsError(PACKET)
    source=json.loads((SOURCE/'JB04/SOURCE.json').read_text());manifest={}
    catalog=[dict(file=n,url=u,origin='Original JobBench files_required_to_search copy; download date not recorded',sha256=hashlib.sha256((REFERENCE_ROOT/n).read_bytes()).hexdigest()) for n,u in REFERENCES.items()]
    for variant,files in json.loads((SOURCE/'JB04/MANIFEST.json').read_text()).items():
        manifest[variant]={}
        for name,digest in files.items():
            raw=(SOURCE/'JB04/variants'/variant/name).read_bytes();assert hashlib.sha256(raw).hexdigest()==digest
            if name=='prompt.md':raw=(source['original_text']+'\n'+FRAME+'\n').encode()
            dst=PACKET/'variants'/variant/name;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(raw)
            manifest[variant][name]=hashlib.sha256(raw).hexdigest()
        raw=(json.dumps(catalog,indent=2)+'\n').encode();(PACKET/'variants'/variant/'inputs/reference_sources.json').write_bytes(raw)
        manifest[variant]['inputs/reference_sources.json']=hashlib.sha256(raw).hexdigest()
    source.update(presentation_revision='Original text preserved verbatim; cached external reference access and authored supplement provenance identified',references=catalog,external_references_frozen=True)
    (PACKET/'SOURCE.json').write_text(json.dumps(source,indent=2)+'\n');(PACKET/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
if __name__=='__main__':build()
