"""Render submitted PDFs privately without modifying source artifacts."""
import hashlib,json,shutil,sys,importlib
from pathlib import Path

def prepare(artifacts,run,max_pages=8):
    artifacts,run=Path(artifacts),Path(run)
    pdfs=sorted(artifacts.rglob('*.pdf'))
    if not pdfs:return artifacts
    try:pymupdf=importlib.import_module('pymupdf')
    except ModuleNotFoundError:
        managed='/tmp/ea-bench-analysis-deps'
        if managed not in sys.path:sys.path.append(managed)
        pymupdf=importlib.import_module('pymupdf')
    target=run/'visual_evidence_input'
    if any(p.is_symlink() for p in artifacts.rglob('*')):raise ValueError('Symlink artifact')
    shutil.copytree(artifacts,target)
    original_files=[str(p.relative_to(artifacts)) for p in sorted(artifacts.rglob('*')) if p.is_file()]
    (target/'_HOST_RENDERING_NOTICE.txt').write_text('Evaluator-provided visual evidence: _derived_pdf_page images are renderings of submitted PDF pages, not additional model deliverables. Original submitted files: '+json.dumps(original_files)+'\n')
    rendered=0;records=[]
    for path in pdfs:
        record=dict(source=str(path.relative_to(artifacts)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),pages=[])
        with pymupdf.open(path) as pdf:
            record['source_page_count']=len(pdf)
            for index,page in enumerate(pdf):
                if rendered>=max_pages:break
                name='_derived_pdf_page_'+str(rendered+1).zfill(2)+'.png'
                page.get_pixmap(matrix=pymupdf.Matrix(1.25,1.25),alpha=False).save(target/name)
                record['pages'].append(dict(page=index+1,file=name,sha256=hashlib.sha256((target/name).read_bytes()).hexdigest()))
                rendered+=1
        records.append(record)
    metadata=dict(kind='host_rendered_submitted_pdf_pages',source_artifacts_unchanged=True,
        max_pages=max_pages,records=records,pdf_backend_version=pymupdf.VersionBind,pdf_backend_module=pymupdf.__file__,scope='Derived images are not model deliverables. Judge vision selection limits still apply.')
    (run/'visual_evidence.json').write_text(json.dumps(metadata,indent=2)+'\n')
    return target
