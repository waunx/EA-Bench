"""JB12 FQHC financial reconciliation and honest rate/peer comparisons."""
from pathlib import Path
from dataclasses import asdict
from decimal import Decimal
import csv,json,zipfile,xml.etree.ElementTree as ET
from .jobbench import load_task,OfficialJudge
from .native import artifact_hashes,JobBenchAcceptance
ROOT=Path(__file__).resolve().parents[2];PACKET=ROOT/'data/expanded/JB12'
def number(value):return Decimal(str(value).replace('$','').replace(',','').replace('%','').strip())
COLUMNS=['Service_Line','Payer_Type','Total_Visits','Weighted_Avg_Actual_Rate','Benchmark_Rate','Deviation_Pct','Compliance_Flag']
EXTRA=[dict(rubric='Complete and financially reconciled Board package',weight=1,criterion=[
'Rate CSV covers every service/payer pair; actual rate is sum reimbursement divided by visits, not mean monthly rates. Explain flag conventions and unavailable/inapplicable benchmarks without inventing rates.',
'Revenue and Expense Variance show actual-minus-budget dollars and budget-relative percentages for every category/month and annual totals; annual percentages use annual sums. Red flags apply below -5% total revenue and above +5% total expense.',
'Peer ratios use stated sources and comparable denominators, with differences over three percentage points identified. Riverside lacks gross charges: any contractual-adjustment estimate is transparent, not presented as audited fact.',
'Service profitability gives visits/reimbursement and a defensible service-cost allocation with total expense tie-out. Memo quantifies monthly variances, Medicaid reconciliation, service-cost options, workforce tradeoffs and 340B operational eligibility; do not assume peer revenue is guaranteed.'])]
EXTRA+=[dict(rubric='Benchmark identity, timing and fiscal-year discipline',weight=1,criterion=[
'Do not identify Riverside with a different provider merely because AHCA name contains Riverside. Identify provider/site and geographic-factor uncertainty; use disclosed provisional comparison or REVIEW when exact identity is unverified.',
'FY2024 is October 2023–September 2024. Distinguish CY2023/2024 historical Medicare rates from January 2025 change; do not apply CY2025 as unqualified historical rate. October 2024 Medicaid schedule is prospective to FY2024; disclose timing and seek historical/provider reconciliation before alleging confirmed underpayment.',
'FY2025 Medicare projection states volume/GAF assumptions and applies rates to appropriate service dates. Dental payment may differ from medical PPS; private/self-pay do not inherit governmental PPS as mandated rates.',
'Exclude October 2024 visits and HealthFirst records from Riverside FY2024. Deduplicate same-key Riverside copies rather than add visits or dollars. Total scope remains 44,951 visits and $6,153,852.04 reimbursement.'])]
def financial_expectations():
 """Private source-derived checks; never require a solver-specific cell layout."""
 import openpyxl
 inputs=PACKET/'variants/full/inputs'
 book=openpyxl.load_workbook(inputs/'Riverside_CHC_FY2024_Budget_vs_Actuals.xlsx',data_only=True)
 tables={}
 for sheet in book:
  values=list(sheet.values);headers=values[0];rows=[dict(zip(headers,r)) for r in values[1:]]
  categories=[h.removeprefix('Budget_') for h in headers if h.startswith('Budget_')]
  expected=[]
  for month in [r['Month'] for r in rows]+['Annual']:
   selected=rows if month=='Annual' else [r for r in rows if r['Month']==month]
   for category in categories:
    budget=sum(number(r['Budget_'+category]) for r in selected)
    actual=sum(number(r['Actual_'+category]) for r in selected)
    delta=actual-budget;percent=100*delta/budget
    expected.append([month,category,str(budget),str(actual),str(delta),str(percent.quantize(Decimal('.0001')))])
  tables[sheet.title]=expected
 service={}
 for r in csv.DictReader((inputs/'Riverside_CHC_Monthly_Visit_Volume_FY2024.csv').open()):
  v=service.setdefault(r['Service_Line'],dict(visits=0,reimbursement=Decimal(0)))
  v['visits']+=int(r['Actual_Visits']);v['reimbursement']+=number(r['Actual_Total_Reimbursement'])
 for v in service.values():
  v['average_reimbursement']=str((v['reimbursement']/v['visits']).quantize(Decimal('.0001')))
  v['reimbursement']=str(v['reimbursement'])
 return dict(variance_columns=['month','category','budget','actual','actual_minus_budget','variance_percent'],variance=tables,service_lines=service)

def completion_rubrics():
 expected=financial_expectations()
 return EXTRA+[dict(rubric='All source-derived monthly and annual calculations',weight=1,criterion=[
  'Verify EVERY Revenue Variance and Expense Variance category/month and annual amount and percentage against the private reference below, allowing ordinary displayed rounding. Rows have columns '+json.dumps(expected['variance_columns'])+'. Annual percentage is annual delta/annual budget. Do not accept selected illustrative months in place of complete tables. Output layout is unrestricted; work may be evidenced in workbook cells, formulas with evaluated values, or supporting source annotations. Reference: '+json.dumps(expected['variance'],separators=(',',':')),
  'Verify all five Service Line Profitability rows against these source totals and weighted averages: '+json.dumps(expected['service_lines'],separators=(',',':'))+'. Each row also needs a cost-per-visit estimate with explicit allocation assumptions and a cross-reference to applicable benchmark rates. Allocated annual costs must reconcile to source annual expenses; do not substitute a government benchmark for service cost.',
  'The memo and workbook must distinguish visit-file reimbursement from budget/actual workbook revenue where measures differ. Financial-performance claims use the appropriate source rather than forcing unrelated totals to match.'])]

def structural_checks(artifacts):
 import openpyxl
 root=Path(artifacts);checks={};details={};books=[];memos=[];audits=[]
 source=list(csv.DictReader((PACKET/'variants/full/inputs/Riverside_CHC_Monthly_Visit_Volume_FY2024.csv').open()));expected={}
 for r in source:
  k=(r['Service_Line'],r['Payer_Type']);v,n=expected.get(k,(0,Decimal(0)));expected[k]=(v+int(r['Actual_Visits']),n+Decimal(r['Actual_Total_Reimbursement']))
 for p in root.rglob('*.csv'):
  try:
   reader=csv.DictReader(p.open(encoding='utf-8-sig'));rows=list(reader);keys=[(r['Service_Line'],r['Payer_Type']) for r in rows]
   valid=reader.fieldnames==COLUMNS and len(keys)==len(set(keys)) and set(keys)==set(expected)
   for r in rows:
    visits,amount=expected[(r['Service_Line'],r['Payer_Type'])]
    valid=valid and number(r['Total_Visits'])==visits and abs(number(r['Weighted_Avg_Actual_Rate'])-amount/visits)<=Decimal('0.02') and r['Compliance_Flag'] in {'PASS','REVIEW','FAIL'}
    try:benchmark=number(r['Benchmark_Rate'])
    except Exception:benchmark=None
    if benchmark is not None and benchmark>0:
     try:deviation=number(r['Deviation_Pct']);valid=valid and abs(deviation-100*(number(r['Weighted_Avg_Actual_Rate'])-benchmark)/benchmark)<=Decimal('0.03')
     except Exception:valid=False
   audits.append(valid and p.name=='FY2024_Rate_Compliance_Audit.csv');details[str(p.relative_to(root))]=dict(rows=len(rows),weighted_rate_reconciliation=valid)
  except Exception as e:details[str(p.relative_to(root))]=dict(error=str(e))
 for p in root.rglob('*.xlsx'):
  try:
   w=openpyxl.load_workbook(p,data_only=False);books.append(p.name=='FY2024_Board_Financial_Report.xlsx' and {s.strip().lower() for s in w.sheetnames}=={'revenue variance','expense variance','peer benchmark','service line profitability'});details[str(p.relative_to(root))]=dict(sheets=w.sheetnames)
  except Exception as e:details[str(p.relative_to(root))]=dict(error=str(e))
 for p in root.rglob('*.docx'):
  try:
   with zipfile.ZipFile(p) as z:text=' '.join(ET.fromstring(z.read('word/document.xml')).itertext())
   memos.append(bool(text.strip()) and p.name=='FY2024_Financial_Compliance_Memo.docx')
  except Exception as e:details[str(p.relative_to(root))]=dict(error=str(e))
 checks.update(reconciled_all_payer_csv=any(audits),four_required_sheets=any(books),readable_docx=any(memos))
 return dict(status='pass' if all(checks.values()) else 'fail',checks=checks,details=details,artifact_hashes=artifact_hashes(root),scope='Artifact structure and source-derived visits/weighted actual rates; benchmark legality and financial semantics judged separately')
def applicable_original_rubrics(original):
 """Keep historical scores unchanged; reconcile three source-applicability clauses."""
 import copy
 active=copy.deepcopy(original)
 active[0]['rubric']='Dental Medicaid reconciliation with verified benchmark applicability'
 active[0]['criterion'][1]='Dental Medicaid actual reimbursement must reconcile to the supplied visits and dollars (approximately $91.31 per visit). Compare against an applicable, sourced historical provider and service benchmark when available. The October 2024 schedule may be illustrated prospectively or provisionally, but cannot alone establish FY2024 underpayment; REVIEW is appropriate when identity, service payment basis or historical rate remains unverified.'
 active[1]['rubric']='Medicare benchmark by service period and documented geography'
 active[1]['criterion'][0]='Use the appropriate CY2023 and CY2024 Medicare FQHC PPS base rates for their respective FY2024 service dates, including the CY2024 base rate of $195.99. Accept a transparently labeled approximate comparison or REVIEW where exact service-period/GAF application remains unresolved. Do not assert a single rate is the verified historical benchmark for all twelve months.'
 active[1]['criterion'][1]='Apply the verified center geographic adjustment factor where available, or explain GAF methodology, the missing site/geographic evidence, and its effect on the comparison. An unavailable GAF may remain explicitly pending; do not invent a provider match.'
 active[3]['rubric']='Comparable peer ratios with disclosed unavailable denominators'
 active[3]['criterion'][2]='Riverside has no explicit gross charges. State this source limitation; explain the methodology and assumptions for any estimate, or the additional evidence required when no defensible estimate can be made.'
 active[3]['criterion'][1]='Present HealthFirst contractual adjustments / gross charges alongside a comparable Riverside estimate only if its assumptions and source basis are defensible. When gross charges cannot be established from supplied data, explicitly mark the Riverside ratio unavailable and identify the needed evidence; do not fabricate a denominator.'
 active[3]['criterion'][3]='Identify differences exceeding three percentage points for computable comparable ratios; disclose why a difference is not computable when a required Riverside denominator is unavailable.'
 active[5]['criterion'][2]='Include Medicare and Medicaid for each service line and evaluate benchmark applicability; an unavailable or inapplicable benchmark must be explicitly explained rather than invented.'
 active[5]['criterion'][3]='Use PASS/REVIEW/FAIL. For an applicable sourced benchmark, deviations within ±5% are PASS and deviations exceeding ±5% are REVIEW or FAIL. Unverified provider, service-payment basis, geographic factor or historical rate warrants explicit REVIEW rather than an unsupported compliance conclusion.'
 active[7]['criterion'][3]='Connect Medicaid revenue shortfalls to rate reconciliation findings while distinguishing a supported historical payment deviation from a provisional/future benchmark comparison. Discuss timing, volume and claims explanations without asserting confirmed underpayment from an unverified provider or inapplicable rate.'
 return active

def check(artifacts,private_root,variant='full',world=None,**judge_config):
 private_root=Path(private_root);private_root.mkdir(parents=True,exist_ok=True);structure=structural_checks(artifacts)
 if variant not in {'full','R1','R2','R3'}:raise ValueError('Unknown JB12 variant')
 if not structure['artifact_hashes']:return dict(case='JB12',status='failed',structural=structure,original=dict(status='not_run'))
 source,path,rubrics=load_task('JB12');native_judge=OfficialJudge(path,private_root/'original_judge',**judge_config)
 native=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,rubrics,native_judge)({},{})
 extra=applicable_original_rubrics(rubrics)+completion_rubrics()
 extra_file=private_root/'authored_completion_rubrics.json';extra_file.write_text(json.dumps(dict(rubrics=extra),indent=2)+'\n');judge=OfficialJudge(extra_file,private_root/'completion_judge',**judge_config)
 completion=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,extra,judge)({},{})
 return dict(case='JB12',status='passed' if structure['status']=='pass' and completion.status=='passed' else 'failed',structural=structure,original=asdict(native),completion=asdict(completion),original_judge_run=str(native_judge.last_run),completion_judge_run=str(judge.last_run),scope='Original rubrics remain diagnostic. Active copied-original business criteria with source-applicability corrections plus full-deliverable checks determine acceptance; no native replay')
