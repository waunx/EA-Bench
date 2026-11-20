"""JB07 municipal restructuring: artifacts, pagination and isolated rubric runs."""
from pathlib import Path
from copy import deepcopy
from dataclasses import asdict
import json,zipfile,xml.etree.ElementTree as ET
from .jobbench import load_task,OfficialJudge
from .native import artifact_hashes,JobBenchAcceptance
from .session import BindingError
ROOT=Path(__file__).resolve().parents[2];PACKET=ROOT/'data/expanded/JB07'
EXTRA=[dict(rubric='Complete reproducible decision package and intervention models',weight=1,criterion=[
'Baseline gives vacancy, OT, average 311 days, worst on-time and Greenfield/NYC per-employee budget ratio with explicit weighting, missing/open 311 handling, fiscal years and denominators. Greenfield salary plus OT is a payroll proxy, not full expense budget; disclose non-comparable coverage rather than invent budget or headcount.',
'Proposal A projects merged headcounts, OT and cycle times with explicit overlap/shared-fleet assumptions. Proposal B gives numeric cross-training pools, OT caps and centralized hiring targets with applicable departments/divisions; distinguish annual thresholds from seasonal demand without suppressing essential services.',
'Comparison gives annual savings, FTE reallocation, SLA improvement, complexity 1–5 and risk 1–5, with transparent net recommendation score. Separate gross savings, one-time implementation and recurring costs; renaming departments does not itself save money.',
'Memo begins with staffing versus citizen outcomes, evaluates bottlenecks, overtime, SLA and workforce feasibility for both proposals and makes an evidence-based recommendation. Presentation includes comparative table/chart, NYC context and next steps. All quantities agree across memo, workbook and slides.',
'MMR analysis selects applicable agency, indicator and reporting-year records with units and scope caveats; do not use irrelevant agencies, future or NA values as current numeric benchmarks. Staffing context cites the Comptroller report.'])]
def compatible_rubrics(original, evidence):
 """Keep original business criteria, replacing only the variant-dependent SLA row."""
 rubrics=deepcopy(original)
 low70=[dict(process=p['process'],on_time_pct=p['on_time_pct']) for p in evidence['processes'] if p['below_70']]
 low65=[dict(process=p['process'],on_time_pct=p['on_time_pct']) for p in evidence['processes'] if p['below_65']]
 row=rubrics[5]
 row['rubric']='Does the response assess all source-grounded processes below 70% on-time and transition risk under both proposals?'
 row['criterion'][:2]=[
  'Identify every process below 70% using current applicable source data and actual clarification. Reference group: '+json.dumps(low70)+'. Unconfirmed attributes: '+json.dumps(evidence['unconfirmed_world_attributes'])+'. If on_time is unconfirmed, the Environmental Complaint Investigation reference is private context only; evaluate explicit evidence-supported conditional groups instead of demanding the hidden rate.',
  'Identify every process strictly below 65% as high-risk SLA using the same evidence basis. Reference group: '+json.dumps(low65)+'. Apply the strict threshold; do not require the historical count of eight or Environmental Complaint Investigation membership when its current rate is 70.1.'
 ]
 return rubrics

def structural_checks(artifacts):
 import openpyxl
 root=Path(artifacts);checks={};details={};books=[];slides=[];memos=[]
 for p in root.rglob('*.xlsx'):
  try:
   w=openpyxl.load_workbook(p,data_only=False)
   required={'baseline metrics','proposal a model','proposal b model','comparison summary'}
   books.append({n.strip().lower() for n in w.sheetnames}==required and any(len(s.conditional_formatting)>0 for s in w))
   details[str(p.relative_to(root))]=dict(sheets=w.sheetnames,conditional_formatting_rules=sum(len(s.conditional_formatting) for s in w))
  except Exception as e:details[str(p.relative_to(root))]=dict(error=str(e))
 for p in root.rglob('*.pptx'):
  try:
   with zipfile.ZipFile(p) as z:
    names=[n for n in z.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml')]
    for n in names:ET.fromstring(z.read(n))
    presentation=ET.fromstring(z.read('ppt/presentation.xml'))
    listed=presentation.findall('.//{http://schemas.openxmlformats.org/presentationml/2006/main}sldId')
    if len(listed)!=len(names):raise ValueError('Slide list does not match packaged slide count')
   slides.append(8<=len(names)<=12);details[str(p.relative_to(root))]=dict(slides=len(names))
  except Exception as e:details[str(p.relative_to(root))]=dict(error=str(e))
 for p in root.rglob('*.docx'):
  try:
   with zipfile.ZipFile(p) as z:text=' '.join(ET.fromstring(z.read('word/document.xml')).itertext())
   memos.append(bool(text.strip()))
  except Exception as e:details[str(p.relative_to(root))]=dict(error=str(e))
 checks.update(four_tab_workbook_with_conditional_formatting=any(books),eight_to_twelve_slides=any(slides),readable_docx=any(memos))
 return dict(status='pass' if all(checks.values()) else 'fail',checks=checks,details=details,artifact_hashes=artifact_hashes(root),scope='Format checks; memo pagination and semantic contents checked separately')
def check(artifacts,private_root,variant='full',world=None,clarification_records=None,**judge_config):
 from .word_renderer import render
 private_root=Path(private_root);private_root.mkdir(parents=True,exist_ok=True);structure=structural_checks(artifacts)
 if not structure['artifact_hashes']:return dict(case='JB07',status='failed',structural=structure,original=dict(status='not_run'))
 pagination=[]
 for i,p in enumerate(Path(artifacts).rglob('*.docx')):
  try:
   with zipfile.ZipFile(p) as z:ET.fromstring(z.read('word/document.xml'))
  except Exception:
   pagination.append(dict(path=str(p),passed=False,error='Invalid DOCX'));continue
  result=render(p,private_root/('memo-render-'+str(i)));pagination.append(dict(path=str(p),pages=result['pages'],passed=6<=result['pages']<=10,renderer=result['renderer']))
 oracle=json.loads((PACKET/'private/oracle.json').read_text());assert variant in oracle['variants']
 from .jb07_evidence import calculate
 evidence=calculate(variant,world,clarification_records)
 (private_root/'source_evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
 extra=EXTRA+[dict(rubric='All-process workload, current workflow and evidence-grounded operational comparison',weight=1,criterion=[
 'Cover every reported process across all five departments with its monthly volume, on-time rate, estimated monthly late workload and current automation. Late workload is volume times (1 - on-time percent/100), a statistical estimate, not observed integer complaints. Use justified consistent rounding; identify the relevant below-65 and below-70 risk groups and connect their exposures to both proposals. An isolated worked example does not satisfy all-process coverage.',
 'Check department scorecards, eight hiring-trigger divisions, annual and seasonal overtime, 311 agency mapping and resolution denominators against source data. State annual versus monthly OT interpretation; retain Fire risk and Sanitation seasonality. Proposals need explicit cross-training pools, OT caps, hiring targets, merged headcounts/costs/cycle-time assumptions and workforce/turnover feasibility. Compare all five requested dimensions with a transparent recommendation score.',
 'Only applicable files and actually supplied clarification establish confirmed facts. Private selected-world values are assessment context, not agent evidence. For unresolved facts, a supported labeled range or conditional analysis can receive analytical credit, but does not establish the requested completed factual process baseline. Do not reward unsupported hidden-value guesses as confirmed. No particular question wording, calculation printout, API action sequence, or memo recommendation is required.',
 'Current automation is a baseline, not proof of realized future savings. Historical-year records and scoped copies do not replace current process data or add staff/spending. Conditional formatting must be red for vacancy >12%, OT >10% and on-time <65% on the actual corresponding scorecard cells with correct percentage units. All reported figures must agree across the actual memo, workbook and presentation.',
 'Private source-derived reference values for every process and department; assess all rows, not only the imperfect record. Alternative justified 311 denominators, model assumptions and rounding conventions must be evaluated on their stated basis: '+json.dumps(evidence)])]

 source,path,rubrics=load_task('JB07')
 native_judge=OfficialJudge(path,private_root/'original_judge',**judge_config)
 native=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,rubrics,native_judge)({},{})
 extra=compatible_rubrics(rubrics,evidence)+extra
 extra_file=private_root/'authored_completion_rubrics.json';extra_file.write_text(json.dumps(dict(rubrics=extra),indent=2)+'\n')
 judge=OfficialJudge(extra_file,private_root/'completion_judge',**judge_config)
 completion=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,extra,judge)({},{})
 return dict(case='JB07',status='passed' if structure['status']=='pass' and any(p['passed'] for p in pagination) and completion.status=='passed' else 'failed',structural=structure,pagination=pagination,original=dict(asdict(native),role='historical_diagnostic',blocking=False),completion=dict(asdict(completion),role='active_compatible_complete',blocking=True),original_judge_run=str(native_judge.last_run),completion_judge_run=str(judge.last_run),scope='Original rubric is diagnostic only. Complete active acceptance requires every compatible original business criterion, authored completion, artifact structure and memo pagination.')
