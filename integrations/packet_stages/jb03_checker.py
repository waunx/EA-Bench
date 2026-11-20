"""Full JB03 deliverable evaluation; native and authored criteria stay distinct."""
import csv,json,copy
from pathlib import Path
from dataclasses import asdict
from datetime import date
from .jobbench import load_task,OfficialJudge
from .native import artifact_hashes,JobBenchAcceptance
from .validate_jb03 import resolve,metrics
EXTRA=[dict(rubric='Complete original deliverables, schedule and dependency feasibility',weight=10,criterion=[
'All four named deliverables must exist and agree. Budget has exactly four sheets covering procurement, annual operations, funding and dashboard.',
'Revised schedule retains every original WBS activity and adds critical_path, risk_level and audit_note. Leaf durations agree with dates, finish-to-start dependencies do not overlap, phase summaries contain child activities and dates finish within nine months of 2025-03-01.',
'Procurement cannot precede budget authorization. Receiving respects 14-week DGX lead time after purchase order. Infrastructure, network, storage, power commissioning, software, test and handoff dependencies must be feasible. Any duration compression or changed dependency is justified with resources or a credible assumption.',
'Critical path is calculated consistently from durations, lead-time constraints and dependencies, with specific risk mitigation. Audit describes every original broken dependency, phase rollup and lead-time conflict.']),
dict(rubric='Complete comparative analysis and genuine capacity feasibility',weight=10,criterion=[
'Compute cloud-only cost using provided rates and memory tiers, with reproducible SQL or equivalent data calculations. State how multiple workloads per researcher are treated.',
'Use the task-requested per-researcher >500 monthly GPU-hour threshold, aggregate multiple workloads by researcher and explain allocation assumptions. A per-workload sensitivity is optional; knowledge of private native rubric wording is not required.',
'Right-size hybrid with explicit GPU counts and load arithmetic. Sustained hours exceed quoted 64-GPU maximum calendar capacity; do not claim a smaller cluster serves all sustained workloads without quantified deferral, spillover or additional hardware. Price any required additions or disclose quotes needed, with comparable service assumptions for all options.',
'Provide six-dimension matrix with weights 30%,20%,15%,10%,15%,10%, justified scores, weighted arithmetic, recommendation and limitations. Sustainability uses cited LBNL facility-class data.',
'Query workload types, volumes, wait distributions and priority relationships. Distinguish cross-sectional peak-to-average proxy from temporal peak data, which are not provided; any temporal peak scenario is labeled.',
'Benchmark $8.2M against actual FY2023 NSF HERD peer values in thousands, explaining peer selection and investment fraction.']),
dict(rubric='Full cash budget and funding reconciliation',weight=10,criterion=[
'Capital reflects line-level quantities, procurement discount and contingency plus explicit tax/shipping basis. Include WBS facility/preparation costs or clearly disclose exclusions consistently across scenarios.',
'Power uses reconciled pre-PUE baseline with PUE exactly once, staffing and licenses, explicit prepaid support at zero annual cash expense, and any cloud spending. No duplicate support amortization in TCO.',
'Funding sheet lists proposed sources, amounts, timing, committed versus assumed status and financing gap; do not invent commitments.',
'Dashboard reconciles all three strategy capital, operations, TCO, delivered GPU-hours and unit cost. Break-even uses actual installed capacity and justified blended cloud rate and identifies infeasibility above 100%. Calculations and sensitivities agree with audit and analysis.'])]
def structural_checks(artifacts):
 import openpyxl
 root=Path(artifacts);checks={};details={}
 for n in ['data_audit.md','strategy_analysis.md','adjusted_budget.xlsx','revised_schedule.csv']:checks[n]=(root/n).is_file()
 for n in ['data_audit.md','strategy_analysis.md']:
  if checks[n]:checks[n+'_nonempty']=bool((root/n).read_text().strip())
 if checks['adjusted_budget.xlsx']:
  try:
   b=openpyxl.load_workbook(root/'adjusted_budget.xlsx',data_only=False);checks['four_sheets']=len(b.worksheets)==4
   checks['no_formula_reference_errors']=not any('#REF!' in str(c.value) for s in b for row in s for c in row);details['sheets']=b.sheetnames
  except Exception as e:checks['readable_workbook']=False;details['workbook_error']=str(e)
 if checks['revised_schedule.csv']:
  try:
   rows=list(csv.DictReader((root/'revised_schedule.csv').open()));checks['schedule_columns']=bool(rows) and {'critical_path','risk_level','audit_note','WBS_ID','Start_Date','End_Date','Dependencies','Duration_Days'}<=set(rows[0])
   byid={r['WBS_ID']:r for r in rows};checks['unique_wbs']=len(byid)==len(rows)
   dates={k:(date.fromisoformat(r['Start_Date']),date.fromisoformat(r['End_Date'])) for k,r in byid.items()}
   checks['nine_months']=min(s for s,e in dates.values())==date(2025,3,1) and max(e for s,e in dates.values())<date(2025,12,1)
   checks['durations']=all((e-s).days+1==int(byid[k]['Duration_Days']) for k,(s,e) in dates.items())
   checks['dependency_dates']=all(p in dates and dates[p][1]<dates[k][0] for k,r in byid.items() if not k.endswith('.0') for p in r['Dependencies'].split(';') if p)
   from .author_english_jb03 import RELEASE
   original=list(csv.DictReader((RELEASE/'variants/full/inputs/project_schedule_wbs.csv').open()))
   checks['all_original_activities']={r['WBS_ID'] for r in original}<=set(byid);details['schedule_rows']=len(rows)
   checks['phase_rollups']=all(dates[k][0]<=dates[c][0] and dates[c][1]<=dates[k][1]
       for k in byid if k.endswith('.0') for c in byid if c!=k and c.split('.')[0]==k.split('.')[0])
   checks['funding_before_purchase_order']=dates['1.7'][1]<dates['1.6'][0]
   checks['dgx_delivery_lead_time']=(dates['3.1'][0]-dates['1.6'][1]).days>=98
  except Exception as e:checks['readable_schedule']=False;details['schedule_error']=str(e)
 return dict(status='pass' if all(checks.values()) else 'fail',checks=checks,details=details,artifact_hashes=artifact_hashes(root),scope='Structural and schedule checks; semantics require judge')
def completion_rubrics(context):
 active=copy.deepcopy(load_task('JB03')[2])
 active[1]['criterion']=[
  'Compute sustained demand by researcher as the task requests and explain aggregation and memory-tier allocation.',
  'Compute allocations from source rows and actual confirmations, without duplicated or lost demand. Conditional quantities are valid for unresolved cells with explicit effects on capacity and cost.',
  'Size against calendar GPU-hours and memory constraints. If a smaller footprint is infeasible, disclose and evaluate a feasible alternative rather than dropping demand.']
 active[4]['criterion'][4]='Price the justified capacity-feasible hybrid footprint with line quantities, discount and contingency; a smaller footprint is not required when demand makes it infeasible.'
 active[5]['criterion'][3]='For hybrid use the justified electrical baseline and cloud operating costs.'
 active[8]['criterion'][0]='Audit every discrepancy with sources, affected field, observed differences, severity and resolution recommendation; clear prose or equivalent columns accepted.'
 active[7]['criterion'][0]='Compute workload-type counts from the actual source and confirmations. Unknown categories remain conditional; do not require historical full-data counts.'
 active[9]['criterion'][0]='Compute infrastructure status counts from actual source and confirmations; unknown status may remain conditional. Reconcile GPU and system totals.'
 active[9]['criterion'][1]='Quantify capacity and utilization against source-derived GPU-hour demand, with explicitly bounded or conditional calculations for unknown cells.'
 active[9]['rubric']='Does the analysis quantify infrastructure capacity, status and utilization against observed or explicitly conditional workload demand?'
 active[3]['criterion'][3]='Identify large storage allocations from the actual visible/confirmed researcher ownership and explain capacity risks; do not require historical owner associations for unknown or changed ownership.'
 active[7]['criterion'][2]='Quantify priority/wait relationships from visible or confirmed rows. Unknown wait cells remain explicitly conditional; do not require historical full-data ranges for unresolved observations.'
 active+=copy.deepcopy(EXTRA)
 for row in active:
  row['criterion'].append('Authoritative visible/confirmed evidence and acceptance policy: '+json.dumps(context,sort_keys=True))
 return active

def check(artifacts,private_root,variant='full',world=None,clarification_records=None,**config):
 from .jb03_evidence import build
 private_root=Path(private_root);private_root.mkdir(parents=True,exist_ok=True);structure=structural_checks(artifacts)
 if structure['status']!='pass':
  return dict(status='fail',case='JB03',variant=variant,structural=structure,original=dict(status='not_run'),completion=dict(status='not_run'))
 context=build(variant,world,clarification_records)
 (private_root/'source_confirmation_context.json').write_text(json.dumps(context,indent=2)+'\n')
 source,path,original=load_task('JB03');judge=OfficialJudge(path,private_root/'original',**config)
 try:
  native=asdict(JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,original,judge)({},{}))
 except Exception as error:
  native=dict(status='error',error=type(error).__name__+': '+str(error),scope='Historical diagnostic infrastructure failure; no task-quality verdict')
 active=completion_rubrics(context);rp=private_root/'completion_rubrics.json';rp.write_text(json.dumps(dict(rubrics=active),indent=2)+'\n')
 other=OfficialJudge(rp,private_root/'completion',**config)
 completion=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,active,other)({},{})
 assert artifact_hashes(artifacts)==structure['artifact_hashes']
 result=dict(status='pass' if completion.status=='passed' else 'fail',case='JB03',variant=variant,structural=structure,original=native,completion=asdict(completion),scope='Separate unchanged historical rubric and source/confirmation-aware full-task semantic judgments; no native replay or universal deterministic arithmetic certification.')
 (private_root/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--artifacts',required=True);p.add_argument('--private-root');p.add_argument('--output',required=True);p.add_argument('--structural-only',action='store_true');a=p.parse_args()
 r=structural_checks(a.artifacts) if a.structural_only else check(a.artifacts,a.private_root)
 Path(a.output).write_text(json.dumps(r,indent=2)+'\n')
