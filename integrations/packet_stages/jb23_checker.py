"""Source-backed Meridian judging and separate original diagnostic."""
from pathlib import Path
from dataclasses import asdict
import json,copy,csv,openpyxl
from .jb23_evidence import build,PACKET
from .jobbench import load_task,OfficialJudge
from .native import artifact_hashes,JobBenchAcceptance

def structural_checks(artifacts):
 p=Path(artifacts);checks={};details={}
 try:
  w=openpyxl.load_workbook(p/'Q1_2024_Reconciliation_Workbook.xlsx',data_only=False);details['sheets']=w.sheetnames;checks['workbook_readable']=True;checks['no_excel_errors']=not any(c.data_type=='e' for s in w for row in s for c in row);w.close()
 except Exception as e:checks['workbook_readable']=False;details['workbook_error']=str(e)
 for name,columns in {'Q1_2024_Schedule_C_Expense_Summary.csv':['GL_ID','TxnDate','AccountNumber','AccountName','Amount','ScheduleC_Line','ScheduleC_Category','Notes'],'Q1_2024_Reconciliation_Exceptions.csv':['Exception_ID','Source_File','Reference','Description','Amount','Resolution','Status']}.items():
  try:
   rows=list(csv.DictReader((p/name).open(encoding='utf-8-sig')));checks[name]=bool(rows) and set(columns)<=set(rows[0])
  except Exception:checks[name]=False
 return dict(status='pass' if all(checks.values()) else 'fail',checks=checks,details=details,artifact_hashes=artifact_hashes(p),scope='Named readable outputs and user-required CSV columns; content judged separately.')

CRITERIA=[
'Recompute bank running balances from$95,000; deposits$27,924.78,withdrawals$85,362.83,end$37,561.95. Distinguish actual GL cash from revenue-minus-expense proxy: no cash1000 postings or full double entries are supplied. Certified accrual bank-to-GL reconciliation is unsupported. Show unresolved difference/control records needed, without balancing plugs or invented outstanding checks/deposits. Accrued revenues/expenses are not automatically cash.',
'FilterQ1 andUSD explicitly; foreign currencies require rates/scope, not nominal summation. Map every eligible expense GLID, debit-credit, normalized COA account, ScheduleC line/category/notes; reconcile subtotals/grand total. OutsideQ1 excludes target row regardless of unknown amount/account. Missing quantities permit known subtotal plus conditional contribution, not a hidden default.',
'Audit7 vendor withdrawals:6 amount/vendor invoice candidates plus unmatchedCHK1402. Include6 ABC invoices and partial hypothesis$4,433.05-$1,847.50=$2,585.55, not confirmed allocation. Investigate FastTravel status and AP10758 January10 clearance versusFebruary9 PaidDate. Payment clearing is not necessarily expense recognition.',
]
CRITERIA += [
'AsofMarch31 aging includes invoices paidApril: AP10027$296.65,AP10251$2,609.45,AP10260$3,084.27 are not yet due. Exclude FastTravel after supported bank correction. AP10003/AP10454/AP10234 are53/50/37 days past due; AP10498/AP10155/AP10485 are25/7/6 days. Partial statuses lack payment amounts: use stated face-value upper bounds or conditional remaining balance, not unsupported full balance as certainty. Show source and adjusted aging with reconciliation. Include earlier outstanding invoices in a separate or combined asof aging view; clearly reconcile any Q1-only subset.',
'Investigate payroll bank$51,000 versusGL$5,861.39 gap$45,138.61, rent$9,600,utilities$1,275,bankcharges$105,interest$37.56,NSF$750,insurance annual premium$1,875,loan payments$3,750. Proposed journals must balance and separate confirmed correction from estimate/awaiting evidence. Loan principal is not expense; obtain interest split. Insurance accrual uses coverage dates/prepaid allocation rather than expensing full annual premium by default. NSF may restore receivable rather than automatically create bad-debt expense. AP settlements debitAP, not duplicated expense.',
'DEP0129$4,127.26 net fees: compare same-day GL000434$4,172.26 yielding$45 with other plausible references, but DEP0125 already also matches$4,172.26. Avoid matching oneGL revenue twice. Keep fee allocation tentative pending remittance; the alternative GL001447$4,741 implies$613.74. Other unmatched revenues/deposits may reflect accrual timing, not necessarily errors.',
'ScheduleC draft must tie source income/expense and separately proposed adjustments. Gross receipts$40,557.62 are known; COGS/grossprofit/expense totals depend on actual target facts. MapCOGSLine4/PartIII,travel24a,wages26; separate meals if evidenced. Discuss business interest eligibility versus ScheduleB, no unsupported loan-principal deduction, prepaid insurance, owner versus employee wage and LLC tax classification. ShowPartI/II and relevantPartIII/V, deductions and net profit with explicit provisional status where unresolved. Do not force unsupported deductions solely because bank paid cash.',
'Exceptions must state source/reference/amount/resolution/status, cover major known discrepancies and unresolved limitations. Client confirmations or supported alternatives/formulas/bounds are legitimate; no forced questions, selected hidden point, fixed tool count or mandatory default choice. Current source and actual clarification are the sole basis for target row values.'
]

def completion_rubrics(evidence):
 original=copy.deepcopy(load_task('JB23')[2])
 changes={
 (3,0):'Age all requestedQ1USD invoices outstanding asofMarch31, including three markedPaid with AprilPaidDate; present raw and corrected FastTravel status. Partial balances need evidence or qualified upper bounds.',
 (3,1):'Due-date aging AP10003/AP10454/AP10234 gives53/50/37 days and31-60 bucket. Partial amounts are not necessarily full face value; exact remaining balances require payment detail.',
 (3,2):'AP10498/AP10155/AP10485 are25/7/6 days past due in0-30; distinguish not-yet-due April-paid invoices AP10027/AP10251/AP10260.',
 (4,0):'Map actual supportedQ1USD account5000 expense toLine4. Known contribution excluding unresolved GL000072 is$4,264.67; include target only if date/account/debit support it. Conditional subtotal allowed.',
 (4,1):'Map actual supportedQ1USD account5010 expense toLine24a. Known contribution excluding target is$7,534.42; include target only if date/account/debit support it.',
 (9,0):'ReplicateScheduleC PartI: receipts$40,557.62 fromSales$23,318.47+Online$17,239.15; actual supportedCOGS Line4 determinesLine5. Treat bankinterest$37.56 separately with business eligibility/adjustment assumption forLine6;Line7 reconciles. Conditional target effects permitted.',
 (9,1):'PartII should map insurance15,rent20b,travel24a,utilities25,wages26,bankcharges27a with supporting GL/adjustment bridge. Bankrent$9,600,utilities$1,275,charges$105 are investigated proposed adjustments, not automatically verified accrual deductions. Insurance needs coverage/prepaid allocation; target uncertainty affectstravel.',
 }
 for (r,c),value in changes.items():original[r]['criterion'][c]=value
 original[3]['rubric']='Does aging correctly reflect source dates and supported outstanding balances asofMarch31?'
 original[4]['rubric']='Does expense mapping correctly use actual supportedQ1USD amounts and ScheduleC categories?'
 original[9]['rubric']='Does the draftScheduleC preserve form structure and reconcile known and proposed amounts?'
 import re
 clean=lambda s:re.sub(r'(?<=[a-zA-Z])(?=\d)|(?<=\d)(?=[a-zA-Z])',' ',s)
 for row in original:row['criterion']=[clean(s) for s in row['criterion']]
 return original+[dict(rubric='Complete supported accrual reconciliation and draft tax work',weight=10,criterion=[clean(s) for s in CRITERIA]+['Selected evidence and source numeric controls: '+json.dumps(evidence)])]

def check(artifacts,private_root,variant='full',world=None,clarification_records=None,**config):
 private_root=Path(private_root);private_root.mkdir(parents=True,exist_ok=True);structure=structural_checks(artifacts)
 if structure['status']!='pass':return dict(case='JB23',status='fail',structural=structure,original=dict(status='not_run'))
 evidence=build(variant,world,clarification_records);(private_root/'source_evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
 source,path,rubrics=load_task('JB23');judge=OfficialJudge(path,private_root/'original_judge',**config)
 original=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,rubrics,judge)({},{})
 active=completion_rubrics(evidence);rp=private_root/'completion_rubrics.json';rp.write_text(json.dumps(dict(rubrics=active),indent=2)+'\n');other=OfficialJudge(rp,private_root/'completion_judge',**config)
 completion=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,active,other)({},{})
 return dict(case='JB23',status='pass' if completion.status=='passed' else 'fail',structural=structure,original=asdict(original),completion=asdict(completion),original_judge_run=str(judge.last_run),completion_judge_run=str(other.last_run),scope='Source calculations and separate original/active semantic judgments; no native replay')
