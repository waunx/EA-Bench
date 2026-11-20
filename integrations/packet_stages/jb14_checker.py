"""JB14 complete artifact gate with unchanged vendor scores kept separate."""
from pathlib import Path
from dataclasses import asdict
import json,zipfile,xml.etree.ElementTree as ET
from .jobbench import load_task,OfficialJudge
from .native import artifact_hashes,JobBenchAcceptance
from .jb14_analysis import analyze
ROOT=Path(__file__).resolve().parents[2];PACKET=ROOT/'data/expanded/JB14'
SHEETS={'Capacity_Utilization_Model','Demand_Allocation_Analysis','Reorder_Optimization_Scenario','Investment_Recommendation'}
def structural_checks(artifacts):
 import openpyxl
 root=Path(artifacts);books=[];docs=[];details={}
 for p in root.rglob('*.xlsx'):
  try:
   w=openpyxl.load_workbook(p,data_only=False);books.append(set(w.sheetnames)==SHEETS);details[str(p.relative_to(root))]=dict(sheets=w.sheetnames);w.close()
  except Exception as e:details[str(p.relative_to(root))]=dict(error=str(e))
 for p in root.rglob('*.docx'):
  try:
   with zipfile.ZipFile(p) as z:t=' '.join(ET.fromstring(z.read('word/document.xml')).itertext())
   docs.append(bool(t.strip()))
  except Exception as e:details[str(p.relative_to(root))]=dict(error=str(e))
 checks=dict(four_required_sheets=any(books),readable_revised_sop=any(docs))
 return dict(status='pass' if all(checks.values()) else 'fail',checks=checks,details=details,artifact_hashes=artifact_hashes(root),scope='OOXML structure only; substantive quality judged separately')
def completion_rubrics(variant,world,clarification_records=None):
 evidence=analyze(variant,world)
 o=json.loads((PACKET/'private/oracle.json').read_text());spec=o['variants'][variant]
 provided={x['fact_id'] for r in clarification_records or [] for x in r.get('provided',[])}
 evidence['clarification_audit']=dict(records=clarification_records or [],unconfirmed_world_attributes=sorted(set(spec['missing']+spec['conflict'])-provided))
 # Keep every compatible original business criterion in the active gate.
 compatible=[load_task('JB14')[2][i] for i in (1,2,4,5)]
 return compatible+[dict(rubric='Transaction control and network scope',weight=1,criterion=[
 'Reconcile shipment-level dispatch intervals versus schedule, discounted net sales and realized profit over the full customer-outbound population before deriving warehouse/region/year measures. Whole-population results must be reproducible from the source records; one worked transaction cannot substitute for the network analysis. Use justified disclosed handling of accounting dashes and consistent rounding. Do not interpret dispatch-after-schedule as observed customer arrival lateness.',
 'Use actual files and supplied clarification as evidence; private selected-world values do not establish confirmation. Supported provisional ranges or conditions can earn analytical credit but do not establish completed factual network measures. Do not reward a correct hidden guess as a confirmed value. No prescribed questions, calculation printouts, line-by-line output ledger or fixed action sequence is required.',
 'Private reference evidence for all warehouse-region-year aggregates, network totals, monthly volume and master-data scope. Evaluate alternative disclosed assumptions on their own basis: '+json.dumps(evidence),
 'Exclude reverse-logistics returns, unaccepted quotes and warehouse transfers from customer outbound measures by direction/status/kind; no additive sales or double counting. Analyze both warehouses, all three years 2015–2017 and warehouse-region volumes, identifying meaningful growth corridors.']),dict(rubric='Complete capacity and investment analysis',weight=1,criterion=[
 'Calculate actual and theoretical capacity for both DCs using source 12,000 and 18,000 pallet positions, actual monthly order volumes and a dimensionally coherent time/turn/units conversion. Do not merely restate reported 91%/73% utilization. Make the basis auditable through workbook formulas, linked values or an equivalent explained model; no separately printed sequence of intermediate calculations is required. Distinguish order lines, units, storage and throughput. Quantify recoverable waste/safety-stock capacity without double counting.',
 'Evaluate all 22 department-warehouse reorder combinations with safety stock, reorder point, lead time and EOQ; distinguish stockout protection from overstock reduction and disclose target assumptions.',
 'Compare $1.2M expansion with 3,000 positions and 12 hires against operational deferral: impacts, payback, costs/growth assumptions, recommendation, uncertainty and decision triggers.',
 'Use inventory.csv and fulfillment.csv. They lack warehouse identifiers: disclose DC allocation assumptions instead of inventing observed DC facts. Assess regional OTD and actual routing; dispatch intervals do not prove historical arrival performance deterioration.']),dict(rubric='Operational rollout and governance',weight=1,criterion=[
 'Revised SOP includes actionable steps justified by specific quantitative findings; a capacity-recovery table links each process improvement to quantified impact, disclosing assumptions and overlap.',
 'Phased timeline includes specific changes, responsible roles and explicit prerequisites. Establish reliable inventory/WMS data before dependent automated reorder or slotting changes, then ongoing KPI-driven improvement. A 30/60/90-day schedule or another justified feasible schedule is acceptable; preserve operational dependencies. KPI governance specifies owners, escalation thresholds/actions and review cadence tied to rollout milestones.'])]
def check(artifacts,private_root,variant='full',world=None,clarification_records=None,**judge_config):
 private_root=Path(private_root);private_root.mkdir(parents=True,exist_ok=True);structure=structural_checks(artifacts)
 if not structure['artifact_hashes']:return dict(case='JB14',status='failed',structural=structure,original=dict(status='not_run'))
 source,path,rubrics=load_task('JB14');native_judge=OfficialJudge(path,private_root/'original_judge',**judge_config)
 native=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,rubrics,native_judge)({},{})
 extra=completion_rubrics(variant,world,clarification_records);extra_file=private_root/'authored_completion_rubrics.json';extra_file.write_text(json.dumps(dict(rubrics=extra),indent=2)+'\n')
 judge=OfficialJudge(extra_file,private_root/'completion_judge',**judge_config);completion=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,extra,judge)({},{})
 return dict(case='JB14',status='passed' if structure['status']=='pass' and completion.status=='passed' else 'failed',structural=structure,original=asdict(native),completion=asdict(completion),original_judge_run=str(native_judge.last_run),completion_judge_run=str(judge.last_run),original_score_role='Diagnostic: vendor rubric mandates an ambiguous throughput formula and intermediate presentation beyond current business acceptance',scope='Authored business completion and structure determine acceptance; unchanged original score is separate, with no mandatory printed intermediate sequence')
