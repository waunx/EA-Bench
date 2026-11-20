"""Evidence-aware purchasing gate; original rubrics are separate diagnostics."""
from pathlib import Path
import csv,json,zipfile,xml.etree.ElementTree as ET
from dataclasses import asdict
import openpyxl
from .jb30_evidence import PACKET,build
from .jobbench import load_task,OfficialJudge
from .native import JobBenchAcceptance,artifact_hashes
EXTRA=[dict(rubric='Quotation arithmetic and budget scenarios',weight=1,criterion=[
'The bid template compares all three vendors item by item: original quoted/recomputed totals, adopted PR-normalized quantities, permitted-reduction totals, and installation/freight-inclusive totals. Explain adopted baselines, reconcile extensions, and show lowest item prices and vendor spreads. Preserve150 desks/chairs,4 large/8 small tables and88 conference chairs; only cabinets75-to50 and reception30-to20 may be reduced.',
'Atlas84 chairs conflicts with extension25080 already pricing88 at285: raw subtotal311045, normalized312185. Do not add1140 twice. Reduced merchandise370390/297810/252450 plus installation8550/7200/5700 and freight0/4500/6200 yields378940/309510/264350. Reconciled negotiated alternatives are allowed. Apply310000 pre-tax, no contingency. Flag repricing, split shipments and Pinnacle1800 inside delivery as applicable costs, not guaranteed omissions.'
]),
dict(rubric='Complete PR and compliance audit',weight=1,criterion=[
'The CSV covers all vendors, severity, recommended actions and every CR identifier. Audit all two-drawer versus required three-drawer cabinets; Atlas/Pinnacle desk depth and missing presets; Pinnacle fixed lumbar and unstated seat-depth adjustment; Atlas unstated seat-depth adjustment; Pinnacle table dimensions; non-swivel conference chairs; small-table power gaps; and unconfirmed CAD/removal scope. Do not invent unquoted services.',
'Keep known failures distinct from verification gaps: Atlas/Pinnacle reception fabric60K/45K fails80K; their desk lows27.5/28 fail27; Pinnacle task capacity250 fails275 and no partial shipments fails phased delivery. Grommets/access doors do not satisfy large-table2AC power/data. Certification/BIFMA documentation, conference-chair fabric/capacity and phased commitments need evidence; Meridian task300 does not prove conference-chair capacity. CR007 is PREFERRED, not mandatory. Do not turn undocumented Meridian FSC/phasing into passes.'
]),
dict(rubric='Evidence-aware specification decisions',weight=1,criterion=[
'Use visible facts and actually delivered confirmations for Meridian structural warranty, task-seat capacity and desk minimum. Unknown/conflicting values may remain pending with conditional pass/fail thresholds and verification actions; do not demand hidden defaults or a clarification call. Structural warranty must reach5 years, seated capacity275lbs and adjustable minimum at most27 inches. Fabric warranty, old desk models and transport stacking loads do not establish these facts.'
]),
dict(rubric='Weighted evaluation and performance evidence',weight=1,criterion=[
'Use the evaluation template, score all three vendors1-5 for all seven criteria and apply weights20/15/15/10/20/10/10 percent. Calculate weighted totals and rank correctly, explain rating anchors and link budget, lead time/phasing, warranty, history, compliance and payment ratings to evidence. Compliance denominators distinguish nine mandatory rules, preferred CR007 and unresolved verification.',
'Use the historical database to substantiate delivery/quality and claims: Meridian6/7 on time, mean4.53 and two promptly resolved claims; Atlas4/6, mean3.9 and denied claims; Pinnacle1/5, mean3.18 and pending claims9/10 concerning weld instability and occupied-chair gas-cylinder sudden drop. Do not treat past claims as current model certification or a warranty substitute.'
]),
dict(rubric='Actionable recommendation and negotiation',weight=1,criterion=[
'The memo is addressed to Procurement Manager and includes a per-vendor CR001-010 table with evidence-supported pass/fail/pending status and CR007 preferred status. Explain the recommendation, budget, safety/schedule/payment risks and unresolved award conditions; lowest price alone cannot authorize unresolved mandatory failures. Pinnacle50-percent deposit needs CFO review and possible2-3-week delay. Escalate to VP of Operations before PO if cap remains unattainable.',
'Provide2-3 concrete vendor counter-offer line items/terms with target prices, quantified total effect and fallback positions. Meridian baseline exceeds cap68940; a5-percent conference-furniture discount saves3027, not enough alone. Do not double-count already-applied discounts or claim unsupported savings make an award affordable.'
]),
dict(rubric='Cross-deliverable integrity',weight=1,criterion=[
'All four artifacts agree on quantities, adopted prices, extended costs, installation/freight, budget gaps, CR decisions, weighted scores/rank and recommended conditions. Trace calculations to sources. Numerical disagreement or contradictory pass/approval claims cannot be excused by correct numbers appearing elsewhere. Preserve template function while adding useful scenario/source columns.'
])]

def authored_rubrics(context):
 import copy
 rubrics=copy.deepcopy(EXTRA)
 for r in rubrics:r['criterion'].append('Apply this private source context independently to the preceding criteria; it is not requested output text: '+json.dumps(context))
 return rubrics

def structural_checks(artifacts):
 root=Path(artifacts);books=list(root.rglob('*.xlsx'));csvs=list(root.rglob('*.csv'));memos=[p for p in root.rglob('*') if p.suffix.lower() in ['.docx','.pdf','.md','.txt'] and p.is_file()]
 checks=dict(two_workbooks=len(books)>=2,audit_csv=bool(csvs),memo=bool(memos))
 try:
  for p in books:
   w=openpyxl.load_workbook(p,read_only=True,data_only=False);assert w.sheetnames;w.close()
  for p in csvs:
   with p.open(encoding='utf-8-sig') as stream:assert len(list(csv.reader(stream)))>=2
  for p in memos:
   if p.suffix.lower()=='.docx':
    with zipfile.ZipFile(p) as z:assert ''.join(ET.fromstring(z.read('word/document.xml')).itertext()).strip()
  checks['readable']=True
 except Exception as exc:checks['readable']=False;checks['format_error']=str(exc)
 return dict(status='pass' if all(v is True for v in checks.values()) else 'fail',checks=checks,scope='Format only; semantic requirements judged separately.')

def check(artifacts,private_root,variant='full',world=None,clarification_records=None,run_judge=True,**judge_config):
 artifacts=Path(artifacts);private_root=Path(private_root);private_root.mkdir(parents=True,exist_ok=True);before=artifact_hashes(artifacts)
 records_path=private_root.parent/'user_records.json';records=clarification_records if clarification_records is not None else (json.loads(records_path.read_text()) if records_path.exists() else [])
 context=build(variant,clarification_records=records);(private_root/'evidence_context.json').write_text(json.dumps(context,indent=2)+'\n')
 structure=structural_checks(artifacts);result=dict(case='JB30',variant=variant,status='failed',structural=structure,artifact_hashes=before,original_evaluator_runs=0,native_environment_replays=0,original_rubric_judge_runs=0,authored_judge_runs=0,scope='Original rubrics remain unchanged diagnostic evidence; corrected evidence-aware authored criteria determine acceptance.')
 if structure['status']=='pass' and run_judge:
  source,path,rubrics=load_task('JB30');judge=OfficialJudge(path,private_root/'original',**judge_config)
  original=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,rubrics,judge)({},None);result['original']=asdict(original);result['original_rubric_judge_runs']=1
  extra=authored_rubrics(context);path=private_root/'authored_rubrics.json';path.write_text(json.dumps(dict(rubrics=extra),indent=2)+'\n')
  judge=OfficialJudge(path,private_root/'authored',**judge_config);adapted=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,extra,judge)({},None)
  result['adapted']=dict(asdict(adapted),layer='authored_evidence_aware');result['authored_judge_runs']=1;result['status']=adapted.status
 assert artifact_hashes(artifacts)==before,'Artifact bytes changed'
 (private_root/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');return result
