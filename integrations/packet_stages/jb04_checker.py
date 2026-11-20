"""Host-owned full artifact checker, with native rubric scores separate."""
from pathlib import Path
import csv,json,zipfile,xml.etree.ElementTree as ET
from dataclasses import asdict
from .jobbench import load_task,OfficialJudge
from .native import artifact_hashes,JobBenchAcceptance
from .session import BindingError
EXTRA=[dict(rubric='Complete original deliverables and cost consistency',weight=1,criterion=[
'Workbook has four functional tabs: verification, takeoff, estimate, summary. Accept arbitrary filenames and equivalent sheet names.',
'Every computed CSV quantity is independently reconciled; unverified allowances such as uncoated rebar are explicitly identified as requiring design details.',
'CSV compares full replacement and HPC overlay on comparable bases with a bottom-row 30-year lifecycle recommendation and service-life assumptions.',
'Word memo is at most one page, includes total agreeing with workbook, principal cost drivers, data quality findings and specific design risks.']),
dict(rubric='Reproducible quantities and complete estimate arithmetic',weight=1,criterion=[
'Takeoff has functioning geometry, conversion and Alaska rounding formulas, retaining unrounded calculations where needed and consistent estimate quantities.',
'Authorized base includes slab, asphalt and barrier removal; concrete and haunches; reinforcement; barriers and railing; waterproofing; joints; twelve drains; approach slabs; and traffic/detour work without duplicate charges.',
'Prices have actual applicable CDOT codes, quantities, payment units, source citations and correct extensions, converting SF to SY where necessary.',
'Summary has category subtotals, 10% mobilization, 20% contingency with stated consistent base, 15% construction engineering on construction including mobilization, correct grand total, and separate add-alternates.']),
dict(rubric='Honest source use and engineering assumptions',weight=1,criterion=[
'Available comparable CDOT prices take priority. Fallback rates, material-class mappings and provisional allowances are identified; nonexistent CDOT Class AA codes are not invented.',
'Haunch flange width, rebar basis, patch depth, market adjustment and unresolved design assumptions are disclosed.',
'Overlay avoids charging hydrodemolition and joints twice since the Michigan Deep Overlay bundle includes them; partial-joint applicability is explained.',
'F-17-DL records do not change F-17-DK scope or dimensions; duplicate memo extracts do not increase quantities.'])]

def structural_checks(artifacts):
    import openpyxl
    root=Path(artifacts);hashes=artifact_hashes(root);checks={};details={}
    books=list(root.rglob('*.xlsx'));memos=list(root.rglob('*.docx'));csvs=list(root.rglob('*.csv'))
    checks.update(xlsx_present=bool(books),docx_present=bool(memos),csv_present=bool(csvs))
    validbooks=[]
    for path in books:
        try:
            book=openpyxl.load_workbook(path,data_only=False)
            formulas=[c.value for s in book for row in s for c in row if c.data_type=='f']
            validbooks.append(len(book.worksheets)==4 and bool(formulas) and not any('#REF!' in f for f in formulas))
            details[str(path.relative_to(root))]=dict(sheets=book.sheetnames,formula_count=len(formulas))
        except Exception as exc:validbooks.append(False);details['xlsx_error']=str(exc)
    checks['four_tab_workbook_with_formulas']=any(validbooks)
    validmemos=[]
    for path in memos:
        try:
            with zipfile.ZipFile(path) as z:text=' '.join(ET.fromstring(z.read('word/document.xml')).itertext())
            validmemos.append(bool(text.strip()))
        except Exception:validmemos.append(False)
    checks['readable_word_memo']=any(validmemos)
    validcsv=[]
    for path in csvs:
        try:validcsv.append(len(list(csv.reader(path.open(encoding='utf-8-sig'))))>=3)
        except Exception:validcsv.append(False)
    checks['readable_comparison_csv']=any(validcsv)
    return dict(status='pass' if all(checks.values()) else 'fail',checks=checks,details=details,artifact_hashes=hashes,scope='Artifact format preflight only; semantic and rendered checks require official judge')

def check(artifacts,private_root,**judge_config):
    private_root=Path(private_root);private_root.mkdir(parents=True,exist_ok=True)
    structure=structural_checks(artifacts)
    if structure['status']!='pass':
        return dict(case='JB04',status='failed',structural=structure,original=dict(status='not_run'),completion=dict(status='failed',reason='Required artifact format missing or invalid'),scope='Required artifact gate failed; no original rubric score inferred')
    source,path,rubrics=load_task('JB04')
    combined=private_root/'rubrics_with_completion_checks.json'
    combined.write_text(json.dumps(dict(rubrics=rubrics+EXTRA),indent=2)+'\n')
    judge=OfficialJudge(combined,private_root/'judge',**judge_config)
    acceptance=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,rubrics+EXTRA,judge)
    full=acceptance({},{});raw=json.loads((judge.last_run/'details.json').read_text())
    extraction=json.loads((judge.last_run/'extraction.json').read_text())
    if '[ERROR: mammoth not available' in extraction.get('text','') or '[ERROR: Failed to read DOCX' in extraction.get('text',''):
        raise BindingError('DOCX extraction failed; judge feedback is not a valid task score')
    native=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,rubrics,judge)._score(raw['rubrics'][:len(rubrics)],structure['artifact_hashes'])
    from .word_renderer import render
    pages=[];render_error=None
    try:
        for index,memo in enumerate(sorted(Path(artifacts).rglob('*.docx'))):
            pages.append(dict(file=str(memo.relative_to(artifacts)),**render(memo,private_root/('word-render-'+str(index)))))
    except Exception as exc:render_error=type(exc).__name__+': '+str(exc)
    pagination=dict(status='unavailable' if render_error else 'evaluated',documents=pages,error=render_error)
    status='failed' if full.status!='passed' or any(p['pages']>1 for p in pages) else ('unavailable' if render_error else 'passed')
    return dict(case='JB04',status=status,rendered_pagination=pagination,structural=structure,original=asdict(native),completion=asdict(full),judge_run=str(judge.last_run),scope='Original rubrics and authored completion feedback, plus actual Word pagination; no native environment replay')

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--artifacts',required=True);p.add_argument('--private-root');p.add_argument('--output',required=True);p.add_argument('--structural-only',action='store_true');a=p.parse_args()
    result=structural_checks(a.artifacts) if a.structural_only else check(a.artifacts,a.private_root)
    Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
