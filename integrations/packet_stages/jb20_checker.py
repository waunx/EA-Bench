"""JB20 complete source-grounded audit grading, separate from original diagnostics."""
import copy,json
from pathlib import Path
from dataclasses import asdict
import openpyxl
from .jb20_evidence import source_context
from .jobbench import load_task,OfficialJudge
from .native import artifact_hashes,JobBenchAcceptance

def structural_checks(artifacts):
 p=Path(artifacts);hashes=artifact_hashes(p);checks={'structured_output':any(Path(n).suffix.lower() in {'.xlsx','.csv'} for n in hashes)}
 for f in p.rglob('*.xlsx'):
  try:
   w=openpyxl.load_workbook(f,read_only=True);checks[str(f.name)+'_readable']=any(s.max_row>0 for s in w);w.close()
  except Exception:checks[str(f.name)+'_readable']=False
 return dict(status='pass' if hashes and all(checks.values()) else 'fail',checks=checks,artifact_hashes=hashes,scope='Format only; no keyword, fixed-file-count or layout acceptance')

def active_original(original):
 r=copy.deepcopy(original)
 r[9]['rubric']='Does the error log resolve or explicitly qualify the ORD-202509-0026 channel comparison using authoritative available evidence?'
 r[9]['criterion']=['Use the current visible or actually confirmed CRM channel for order0026. If unresolved, identify the pending comparison without claiming a verified channel.', 'CRM outranks ERP for this unscanned order. Mark ERP wrong only when the supported CRM value differs; do not invent an error when they agree.', 'Classify channel error patterns using actual supported instances, including order0007; qualify a suspected repeated pattern if order0026 remains unresolved.']
 r[10]['criterion'][1]='Calculate the metric using current source counts for the chosen unit and phase. Counts can change with supported channel facts. Distinguish source disagreements, missing information and registration findings. Qualify counts dependent on unresolved facts.'
 r[11]['criterion'][0]="The completed compliance checklist must mark CRT-005 Total Revenue calculations are accurate (Units x Unit Price) as Fail; the output filename may differ from the supplied template."
 return r

EXTRA=[
'Deliver all four logical products: completed error log using the provided fields, reconciled master, executive audit report and completed compliance checklist. They may share a workbook or use separate readable files; do not require four physical files or exact filenames.',
'Reconcile all30 order rows and every supplied field using scan over CRM over ERP. Explain malformed ERP order-ID recovery with the matching evidence, not an invented row correspondence. Master values, provenance and verification status must agree. Unresolved facts cannot be called verified; identify appropriate follow-up.',
'Document every supported source discrepancy and source system, with consistent systematic/random classification. Include identity, quantity, price, country, customer, date and channel errors outside the original rubric examples. Distinguish date formatting from actual-day differences and preserve the authority rules.',
'Validate customer name/country against all35 master entries. Flag known unregistered entities, distinguish unknown legal-name status from a verified match, and do not rename an order entity merely to force registration. Apply only relevant current source copies; duplicates do not add records.',
'Recompute revenue with exact decimal units-times-price and a0.01 tolerance. Distinguish raw internal formula errors from stored-total errors against authoritative corrected quantities/prices; a wrong input can invalidate a raw formula even when stored revenue is correct. Show reproducible variance evidence for material errors.',
'Complete every supplied checklist criterion with supported status, checked/passed counts, rates and evidence, respecting template instructions and stated pre/post-correction phase. Unknown information cannot count as verified. Report critical failures and consistent totals rather than copying blanket Pass/Fail labels.',
'Executive findings give correctly labeled quantitative metrics and reproducible numerators/denominators, supported systematic and random patterns, material financial effects and actionable process improvements. Reconcile report, error log, master and checklist; disclose unresolved limitations rather than fabricate certainty.'
]

def check(artifacts,private_root,variant='full',world=None,clarification_records=None,**config):
 root=Path(private_root);root.mkdir(parents=True,exist_ok=True);structure=structural_checks(artifacts)
 if structure['status']!='pass':return dict(case='JB20',variant=variant,status='fail',structural=structure,original={'status':'not_run'},completion={'status':'not_run'})
 context=source_context(variant,clarification_records)
 (root/'source_context.json').write_text(json.dumps(context,indent=2,default=str)+'\n')
 source,path,original=load_task('JB20');active=active_original(original)
 active.append(dict(rubric='Complete source-grounded reconciliation and compliance audit',weight=1,criterion=EXTRA+['Private source evidence, not a required output layout: '+json.dumps(context,default=str)]))
 j=OfficialJudge(path,root/'original_judge',**config)
 native=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,original,j)({},{})
 rp=root/'active_rubrics.json';rp.write_text(json.dumps(dict(rubrics=active),indent=2)+'\n')
 aj=OfficialJudge(rp,root/'active_judge',**config)
 verdict=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,active,aj)({},{})
 return dict(case='JB20',variant=variant,status='pass' if verdict.status=='passed' else 'fail',structural=structure,original=asdict(native),completion=asdict(verdict),original_judge_run=str(j.last_run),completion_judge_run=str(aj.last_run),scope='Separate unchanged original diagnostic and all-compatible-original plus complete source-grounded business acceptance; no native replay')
