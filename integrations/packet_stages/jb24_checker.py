"""JB24 semantic source checking with separate unchanged original diagnostic."""
from pathlib import Path
from dataclasses import asdict
import json,zipfile,xml.etree.ElementTree as ET,copy
import openpyxl
from .jb24_evidence import build,PACKET
from .jb24_sql import execute
from .jobbench import load_task,OfficialJudge
from .native import artifact_hashes,JobBenchAcceptance

def structural_checks(artifacts):
 p=Path(artifacts);names=['revised_feasibility_report.docx','resource_allocation.xlsx','workload_impact.sql','executive_memo.md'];checks={n:(p/n).is_file() for n in names};details={}
 if all(checks.values()):
  try:
   w=openpyxl.load_workbook(p/names[1],data_only=False);details['sheets']=w.sheetnames;checks['no_excel_errors']=not any(c.data_type=='e' for s in w for row in s for c in row);w.close()
   with zipfile.ZipFile(p/names[0]) as z:ET.fromstring(z.read('word/document.xml'))
   for n in names[2:]:checks[n+'_nonempty']=bool((p/n).read_text().strip())
  except Exception as exc:checks['readable']=False;details['error']=str(exc)
 return dict(status='pass' if all(checks.values()) else 'fail',checks=checks,details=details,artifact_hashes=artifact_hashes(p),scope='File/format checks only, not substantive acceptance')

CRITERIA=[
'Reconcile proposal, original budget, current memo, updated quotes, hardware specs and all8 database projects. Recalculate A/B/C and a genuinely new feasible OptionD: distinguish GPU-only component BOM versus turnkey-node quotes to avoid double-counting, identify quote scope discrepancies, include networks, storage, RAM, racks, cooling, UPS, site prep, energy, staff, licenses, maintenance and bandwidth. TCO, three annual cash flows, contingency>=324000 and total<=10.8M must reconcile with annual4.2/3.6/3.0M caps. Quotes must apply to actual components and quantities. No fixed OptionD or unexplained optimum is required; substantiate throughput tradeoffs.',
'Verify precision and sparsity using actual hardware CSV: H100 TensorFP16/BF16 is989.4TFLOPS, INT8 is1979TOPS, A100 denseFP16 is312TFLOPS; do not mix INT8, sparse and dense metrics. A/B/C dense peaks63.3216/39.936/51.6288PFLOPS before sustained factors. Cost-per-PFLOPS-hour denominator must use consistent precision, time, utilization, uptime, ramp-up and seasonal capacity; do not confuse GPU-hours with PFLOPS-hours.',
'Provide all four workbook areas and36 months covering all8 projects, start/end dates, GPU counts or defensible shared allocations, capacity/throughput, concurrency, time preferences, preemption and dependencies. From Month13 reserve the confirmed mandate separately from named projects, avoiding double-counted fractional/integer capacity. Forecast June-August280kW cooling versus ordinary350kW and380kW power, floor340sqft, ramp-up and downtime. Reconcile proposal power350/380/365 against budget IT280/350/310 plus PUE: alternative documented reconciliations are allowed, not blind acceptance of one conflicting estimate.',
]
CRITERIA += [
'Migration must distinguish outdated proposal Cedar24V100+8A100 from the actual database inventory (64 GPUs across6 resources) and analyze all relevant history, queue waits and job failures. LegacyA reaches97.8%/112.5h inMay and98.5%/142h inJune; do not silently stop atMay. Reported utilization and used/available hour ratios disagree, so identify measurement/denominator limits rather than treating them as interchangeable. Transition each workload with capacity/memory/interconnect and procurement milestones.',
'Executed SQL result sets must actually identify delay-exposed projects, quantify demand versus legacy availability by priority tier without allocating the same free capacity to each tier, and rank all8 projects by priority_weight*(1/flexibility_days)*monthly_GPU_hours_demand. Weights, GPU allocation basis, period length and legacy usable-capacity assumptions must be documented; no fixed priority weights imposed. Reference workload demand at min GPUs totals76272hours/month, but justified different GPU allocation yields a recomputed demand. Handle zero flexibility, divide in real numbers, account for deadlines, remaining runs/hours and monthly recurring workloads; merely adding3months to a date or including keywords is insufficient.',
'Procurement risk must use actual confirmed applicable lead times, distinguish bare A1006weeks from A100 turnkey systems 4 weeks, NDR 14 weeks and cooling 12 weeks, installation/commissioning and the components selected forOptionD. January5 is only an illustrative order baseline, not mandated. Evaluate original3month-delay risk as a scenario while linking actual chosen deployment exposure to requirements; H100 need not govern a design without H100 or when another confirmed lead is longer. No selected unconfirmed cap, reservation or lead is silently defaulted. Supported provisional/robust designs receive appropriate credit without a forced question.',
'Executive memo justifiesOptionD, net-zero operations byYear2 with energy/emissions and procurement/REC costs, enforceable campus queue access, and risk-adjusted timeline. Compare>=3 relevant academic/public clusters using actual Epoch data, comparable precision, hardware/gpu counts, costs and data uncertainty. Reported versus calculated costs/power and future/uncertain deployments must be distinguished. Do not require particular peer names beyond original relevant comparison requirement.',
'Judge actual cross-file numeric/decision consistency, not printed keywords, arbitrary sheet order or reasoning transcript. Original four named sheets and requested calculations remain requirements. No forced tool sequence or unproven numeric tool/information minimum is imposed. SQL executes on a disposable copy; result correctness is judged against actual sources.'
]

import re
CRITERIA=[re.sub(r'(?<=[a-z])(?=\d)|(?<=\d)(?=[a-zA-Z])',' ',x).replace('OptionD','Option D') for x in CRITERIA]

def completion_rubrics(evidence):
 original=copy.deepcopy(load_task('JB24')[2])
 replacements={'48 or fewer':'within the applicable confirmed vendor cap','20%':'the applicable confirmed percentage','18-week':'applicable confirmed','18 weeks':'the applicable confirmed lead time','18-week H100':'H100 with the applicable confirmed lead time'}
 for i in (1,2,4,6,7):
  for field in ('rubric','criterion'):
   items=original[i][field] if field=='criterion' else [original[i][field]]
   for old,new in replacements.items():items=[x.replace(old,new) for x in items]
   items=[x.replace('the the ','the ') for x in items]
   original[i][field]=items if field=='criterion' else items[0]
  original[i]['criterion'].append('Unconfirmed authored policy remains provisional; judge actual visible/clarified evidence or justified robust alternatives, not hidden selected values.')
 original[4]['rubric']='Does SQL assess the original three-month delay scenario and the chosen procurement exposure against deadlines and remaining GPU work?'
 original[4]['criterion'][0]='Evaluate projects exposed to the original three-month deployment-delay scenario; distinguish that scenario from the actual delay implied by confirmed procurement and commissioning dates.'
 original[7]['criterion'][0]='Use confirmed applicable H100 lead, cooling 12 weeks, NDR 14 weeks and A100 turnkey systems 4 weeks; distinguish bare A100 GPU 6 week quote and contradictory immediate-shipment note.'
 original[7]['criterion'][1]='Identify the actual critical path for the selected components and confirmed lead times; do not force H100 to govern when not selected or not longest.'
 original[3]['criterion'][0]='Reference the proposal Cedar24V100 and departmental8A100 description, and reconcile it with actual current_resources records instead of asserting inconsistent inventories are simultaneously current.'
 original[8]['criterion'][1]='Compare each original option with 280 kW summer cooling on an explicit consistent heat/power basis; reconcile conflicting source power figures and quantify necessary capacity reduction, including zero where justified.'
 original[8]['criterion'][3]='State which options require summer throttling under the supported assumptions and quantify the impact.'
 original[8]['criterion'][0]='Evaluate each original option against 380 kW power, reconciling proposal 350/380/365 kW estimates with original-budget IT/PUE figures; explicitly state the justified power basis and capacity consequences.'
 return original+[dict(rubric='Complete GPU feasibility, allocation, SQL and source-verified benchmarking',weight=10,criterion=CRITERIA+['Selected-visible evidence and independent calculations: '+json.dumps(evidence)])]

def check(artifacts,private_root,variant='full',world=None,clarification_records=None,**config):
 private_root=Path(private_root);private_root.mkdir(parents=True,exist_ok=True);structure=structural_checks(artifacts)
 if structure['status']!='pass':return dict(case='JB24',status='fail',structural=structure,original=dict(status='not_run'))
 evidence=build(variant,world,clarification_records);evidence['submitted_sql_execution']=execute(Path(artifacts)/'workload_impact.sql',private_root,variant)
 (private_root/'source_evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
 source,path,rubrics=load_task('JB24');judge=OfficialJudge(path,private_root/'original_judge',**config)
 original=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,rubrics,judge)({},{})
 active=completion_rubrics(evidence);rp=private_root/'completion_rubrics.json';rp.write_text(json.dumps(dict(rubrics=active),indent=2)+'\n')
 other=OfficialJudge(rp,private_root/'completion_judge',**config);completion=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,active,other)({},{})
 return dict(case='JB24',status='pass' if completion.status=='passed' and evidence['submitted_sql_execution']['status']=='executed' else 'fail',structural=structure,sql=evidence['submitted_sql_execution'],original=asdict(original),completion=asdict(completion),original_judge_run=str(judge.last_run),completion_judge_run=str(other.last_run),scope='Source calculations, disposable SQL execution and semantic original/active judgments; no native replay')
