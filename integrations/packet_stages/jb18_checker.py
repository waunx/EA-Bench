"""JB18 complete plant-scoring and conditional-consolidation artifact checks."""
from pathlib import Path
from dataclasses import asdict
import json,csv,re,zipfile,xml.etree.ElementTree as ET
from .jobbench import load_task,OfficialJudge
from .native import artifact_hashes,JobBenchAcceptance
ROOT=Path(__file__).resolve().parents[2];PACKET=ROOT/'data/expanded/JB18'
EXTRA=[dict(rubric='Complete and reproducible scoring and redistribution',weight=1,criterion=[
'Rank all 19 plants using numeric factors, explicit normalization/direction, weights summing to one and reproducible scores. Define structural unviability; absent order/survey data is unknown evidence, not proven zero demand or satisfaction. Identify 3–5 candidates with balanced retention arguments.',
'For each candidate, identify receiving plants and shared-port feasibility, conserved transferred units and before/after capacity utilization only on compatible, explicitly stated units/time bases. Check joint receiving load if multiple closures share a receiver; do not claim feasibility from separately feasible cases that jointly overload it. If Daily_Capacity units or observation horizon cannot be reconciled, treat feasibility as conditional rather than forcing unsupported utilization math.',
'OrderList has one observed date, May 26 2013, while satisfaction is Q4 2023. Distinguish orders, Unit_Quant and daily-capacity units. Disclose unresolved capacity-unit/time mismatch and annualization assumptions rather than silently dividing single-day units by arbitrary annual capacity.',
'Net cost includes origin/receiver per-unit warehousing and applicable freight with carrier/route/weight-band/service/minimum-charge logic when matches exist. Do not treat all variable warehouse spend as avoidable fixed closure savings, invent unmatched freight quotes or ignore one-time transition costs. Annualized estimates are scenarios, not observed annual totals.',
'Board brief provides methodology, supporting metrics, candidate-specific redistribution/cost, implementation risks and one Close/Consolidate/Retain-and-Monitor action per candidate. Explicitly reconcile efficiency priorities with consolidation/concentration and customer-retention risks. Conditional Retain-and-Monitor or no-go is appropriate where feasibility cannot be established.'])]
EXTRA+=[dict(rubric='Complete operational and customer evidence reconciliation',weight=1,criterion=[
'Reconcile 9,215 order rows, 192 late orders and 29,513,315 units; distinguish PLANT03 order-share concentration from unit share. Verify 7 observed-order plants against all 19 reference plants and avoid extrapolating absent records to sustained inactivity.',
'Risk assessment uses per-plant satisfaction means with sample counts, complaint counts, high severity, resolution/open rates and categories. Align survey/complaint keys; do not count copies or historical waves as new evidence. State uncertainty from cross-period association.',
'Workbook and memo agree on candidate order, actions, scores and costs. Required Go/No-Go matrix fits on a single rendered page within the five-page brief.'])]
def structural_checks(artifacts):
 import openpyxl
 root=Path(artifacts);details={};books=[];memos=[]
 plants={r['Plant_Code'] for r in csv.DictReader((ROOT/'data/source/dataset/management_analysts/task2/files_required_to_search/WhCapacities.csv').open())}
 for p in root.rglob('*.xlsx'):
  try:
   w=openpyxl.load_workbook(p,data_only=False);required={'Composite_Score','Consolidation_Scenarios','Risk_Matrix','Data_Reconciliation'};valid=set(w.sheetnames)==required
   observed={m for row in w['Composite_Score'].values for v in row for m in re.findall(r'PLANT\d{2}',str(v))};valid=valid and plants<=observed
   books.append(valid);details[str(p.relative_to(root))]=dict(sheets=w.sheetnames,composite_plant_mentions=sorted(observed))
  except Exception as e:details[str(p.relative_to(root))]=dict(error=str(e))
 for p in root.rglob('*.docx'):
  try:
   with zipfile.ZipFile(p) as z:text=' '.join(ET.fromstring(z.read('word/document.xml')).itertext())
   memos.append(bool(text.strip()))
  except Exception as e:details[str(p.relative_to(root))]=dict(error=str(e))
 checks=dict(four_tab_all_plant_model=any(books),readable_board_brief=any(memos))
 return dict(status='pass' if all(checks.values()) else 'fail',checks=checks,details=details,artifact_hashes=artifact_hashes(root),scope='Format and plant mention coverage only; numeric model/feasibility/customer semantics judged separately')
def check(artifacts,private_root,variant='full',world=None,clarification_records=None,**judge_config):
 from .word_renderer import render
 private_root=Path(private_root);private_root.mkdir(parents=True,exist_ok=True);structure=structural_checks(artifacts)
 if not structure['artifact_hashes']:return dict(case='JB18',status='failed',structural=structure,original=dict(status='not_run'))
 pages=[]
 for i,p in enumerate(Path(artifacts).rglob('*.docx')):
  try:
   with zipfile.ZipFile(p) as z:ET.fromstring(z.read('word/document.xml'))
  except Exception:pages.append(dict(path=str(p),passed=False,error='Invalid DOCX'));continue
  report=render(p,private_root/('brief-render-'+str(i)));pages.append(dict(path=str(p),pages=report['pages'],passed=report['pages']<=5,renderer=report['renderer']))
 oracle=json.loads((PACKET/'private/oracle.json').read_text());assert variant in oracle['variants']
 unresolved=set(oracle['variants'][variant]['missing']+oracle['variants'][variant]['conflict'])
 if unresolved-set(world or {}):raise ValueError('Explicit private world values required for unresolved variant facts')
 from .jb18_judge_context import build
 from .jb18_rubric_adaptation import adapt
 records_path=private_root.parent/'user_records.json'
 records=clarification_records if clarification_records is not None else (json.loads(records_path.read_text()) if records_path.exists() else [])
 context=build(PACKET,variant,records)
 (private_root/'source_and_confirmation_context.json').write_text(json.dumps(context,indent=2,default=str)+'\n')
 extra=EXTRA+[dict(rubric='Customer evidence and scope under uncertainty',weight=1,criterion=[
 'Use sourced or actually confirmed customer values in per-plant satisfaction and complaint/severity counts. For unconfirmed attributes, present defensible conditional metrics/risk and material ranking sensitivity; do not invent a point fact or require a particular clarification. Private evaluator context, not requested artifact text: '+json.dumps(context,default=str),
 'Q4 2022 survey is not Q4 2023; complaint/order copies are not new observations. Multi-plant customer activity does not identify the servicing plant of one complaint.'])]
 source,path,rubrics=load_task('JB18');native_judge=OfficialJudge(path,private_root/'original_judge',**judge_config)
 native=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,rubrics,native_judge)({},{})
 adapted,adaptation=adapt(rubrics)
 for index in [0,3,6]:adapted[index]['rubric']+=' Private source/confirmation context (not required output text): '+json.dumps(context,default=str)
 active=adapted+extra
 (private_root/'rubric_adaptation.json').write_text(json.dumps(adaptation,indent=2)+'\n')
 extra_file=private_root/'authored_completion_rubrics.json';extra_file.write_text(json.dumps(dict(rubrics=active),indent=2,default=str)+'\n')
 judge=OfficialJudge(extra_file,private_root/'completion_judge',**judge_config)
 completion=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,active,judge)({},{})
 passed=structure['status']=='pass' and any(p['passed'] for p in pages) and completion.status=='passed'
 return dict(case='JB18',status='passed' if passed else 'failed',structural=structure,pagination=pages,original_diagnostic_only=True,original=asdict(native),completion=dict(asdict(completion),layer='adapted_original_and_authored'),adaptation=adaptation,original_judge_run=str(native_judge.last_run),completion_judge_run=str(judge.last_run),scope='Byte-identical original rubric diagnostic scored separately. Blocking completion retains all compatible original criteria with recorded narrow adaptations, plus authored checks; structural and pagination gates also apply.')
