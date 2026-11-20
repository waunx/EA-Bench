"""Host-owned full artifact checker, with native rubric scores separate."""
from pathlib import Path
import csv,json,zipfile,xml.etree.ElementTree as ET
from dataclasses import asdict
from .jobbench import load_task,OfficialJudge
from .native import artifact_hashes,JobBenchAcceptance
from .session import BindingError
EXTRA=[dict(rubric='Complete cost comparison and recommendation',weight=1,criterion=[
'Both summaries have correct extensions, 8% mobilization and 15% contingency with explicit bases. Memo and workbook totals agree.',
'Option B uses 40% full-depth repair at 8 inches, 60% hydrodemolition and patching at 2 inches, and 100% overlay. All non-deck work remains identical between options.',
'Memo identifies three largest cost drivers per option with dollars, flags pricing uncertainty above 20%, compares both options to $2,000,000 and quantitatively compares 40-year and 15-year lives with stated lifecycle assumptions.',
'Painting crew-day buildup traces local labor, burden, equipment, materials and production and benchmarks installed cost with real DOT prices. Material prices are not installed prices.'])]
EXTRA[0]['criterion'] += [
'Reconcile the scope memo quantities with independent takeoffs, including the memo 62,400 lb rebar allowance versus separately computed top/bottom longitudinal/transverse mats. Explain adopted quantities and any laps, cover, waste or constructability allowances rather than silently copying conflicting totals.',
'Use Colorado DOT as the primary published pricing reference and cross-check at least one other state DOT. Document comparable item descriptions, units and source locations; explain scope differences, missing comparisons and justified estimates rather than inventing citations or treating material-only prices as installed rates.']

def structural_checks(artifacts):
    import openpyxl
    root=Path(artifacts);hashes=artifact_hashes(root);checks={};details={}
    books=list(root.rglob('*.xlsx'));memos=list(root.rglob('*.docx'));csvs=list(root.rglob('*.csv'))
    checks.update(xlsx_present=bool(books),memo_present=bool(memos) or any(root.rglob('*.pdf')) or any(root.rglob('*.md')) or any(root.rglob('*.txt')))
    validbooks=[]
    for path in books:
        try:
            book=openpyxl.load_workbook(path,data_only=False)
            formulas=[c.value for s in book for row in s for c in row if c.data_type=='f']
            validbooks.append(len(book.worksheets)==6 and not any('#REF!' in f for f in formulas))
            details[str(path.relative_to(root))]=dict(sheets=book.sheetnames,formula_count=len(formulas))
        except Exception as exc:validbooks.append(False);details['xlsx_error']=str(exc)
    checks['six_tab_workbook']=any(validbooks)
    validmemos=[]
    for path in memos:
        try:
            with zipfile.ZipFile(path) as z:text=' '.join(ET.fromstring(z.read('word/document.xml')).itertext())
            validmemos.append(bool(text.strip()))
        except Exception:validmemos.append(False)
    if memos:checks['readable_word_memo']=any(validmemos)
    validcsv=[]
    for path in csvs:
        try:validcsv.append(len(list(csv.reader(path.open(encoding='utf-8-sig'))))>=3)
        except Exception:validcsv.append(False)
    # No CSV required.
    return dict(status='pass' if all(checks.values()) else 'fail',checks=checks,details=details,artifact_hashes=hashes,scope='Artifact format preflight only; semantic and rendered checks require official judge')

def check(artifacts,private_root,variant="full",world=None,clarification_records=None,**judge_config):
    private_root=Path(private_root);private_root.mkdir(parents=True,exist_ok=True)
    structure=structural_checks(artifacts)
    if not structure['artifact_hashes']:
        return dict(case='JB05',status='failed',structural=structure,original=dict(status='not_run'),completion=dict(status='failed',reason='No deliverable artifacts'),scope='Empty submission rejected without judge')
    source,path,rubrics=load_task('JB05')
    packet=Path(__file__).resolve().parents[2]/'data/expanded/JB05'
    oracle=json.loads((packet/'private/oracle.json').read_text());assert variant in oracle['variants']
    unresolved=set(oracle['variants'][variant]['missing']+oracle['variants'][variant]['conflict'])
    if unresolved-set(world or {}):raise ValueError('Explicit private world values required for unresolved variant facts: '+', '.join(sorted(unresolved-set(world or {}))))
    from .jb05_judge_context import build
    records_path=private_root.parent/'user_records.json'
    records=clarification_records if clarification_records is not None else (json.loads(records_path.read_text()) if records_path.exists() else [])
    context=build(packet,variant,records)
    (private_root/'source_and_confirmation_context.json').write_text(json.dumps(context,indent=2)+'\n')
    extra=EXTRA+[dict(rubric='Repairs, provisional assumptions and applicable local sources',weight=1,criterion=[
      'Use or explicitly reconcile sourced/actually confirmed quantities and local rate components. For unconfirmed attributes, accept clearly provisional engineering assumptions with justified bases, quantified material sensitivity of both totals and recommendation, and remaining verification needs. Do not require a selected hidden point, any specific sensitivity endpoints, or a clarification call. Never represent an assumption as county-confirmed. Keep distinct localized plate repair and 450 lb stiffener replacement scopes; preserve identical non-deck work between options. Benchmark M-009 material/injection equipment separately from justified labor without duplicate equipment. Private evaluator source context, not requested output text: '+json.dumps(context),
      'B-42-0118 inspection records do not set B-42-0117 quantities; equipment-only quotes do not replace combined material/equipment quotes; 2026 work orders do not change the 2025 project.'])]
    original_judge=OfficialJudge(path,private_root/'original_judge',**judge_config)
    native=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,rubrics,original_judge)({},{})
    extra_file=private_root/'authored_completion_rubrics.json'
    extra_file.write_text(json.dumps(dict(rubrics=extra),indent=2)+'\n')
    completion_judge=OfficialJudge(extra_file,private_root/'completion_judge',**judge_config)
    completion=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,extra,completion_judge)({},{})
    for judge in [original_judge,completion_judge]:
        extraction=json.loads((judge.last_run/'extraction.json').read_text())
        if '[ERROR: mammoth not available' in extraction.get('text','') or '[ERROR: Failed to read DOCX' in extraction.get('text',''):
            raise BindingError('DOCX extraction failure is infrastructure failure')
    return dict(case='JB05',status='passed' if structure['status']=='pass' and native.status=='passed' and completion.status=='passed' else 'failed',structural=structure,original=asdict(native),completion=dict(asdict(completion),layer='authored_completion'),original_judge_run=str(original_judge.last_run),completion_judge_run=str(completion_judge.last_run),scope='Unmodified original rubric file scored in its own official judge run; authored completion criteria in a separate private judge run')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--artifacts',required=True);p.add_argument('--private-root');p.add_argument('--output',required=True);p.add_argument('--structural-only',action='store_true');a=p.parse_args()
    result=structural_checks(a.artifacts) if a.structural_only else check(a.artifacts,a.private_root)
    Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
