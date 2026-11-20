"""Meridian source accounting controls without hidden-world defaults."""
from datetime import datetime
from collections import defaultdict
from decimal import Decimal
import csv,json,openpyxl
from .artifact_adapter_jb23 import PACKET

def plain(x):return x.strftime('%Y-%m-%d') if isinstance(x,datetime) else x
def q1(x):return x is not None and '2024-01-01'<=plain(x)<='2024-03-31'
def readbook(p):
 w=openpyxl.load_workbook(p,data_only=False);rows=list(w.active.values);w.close();return [dict(zip(rows[0],[plain(x) for x in r])) for r in rows[1:]]
def build(variant,world=None,clarification_records=None):
 p=PACKET/'variants'/variant/'inputs';ledger=readbook(p/'General_Ledger_Sample.xlsx');ap=readbook(p/'Accounts_Payable_Sample.xlsx');bank=list(csv.DictReader((p/'Bank_Statement_Q1_2024.csv').open()));coa=list(csv.DictReader((p/'Chart_of_Accounts.csv').open()))
 target=next(r for r in ledger if r['GLID']=='GL000072');facts=dict(date=target['TxnDate'],debit=target['Debit'],account=target['AccountNumber'])
 for record in clarification_records or []:
  for item in record.get('provided',[]):
   if item['fact_id'] in facts:facts[item['fact_id']]=item['value']
 target.update(TxnDate=facts['date'],Debit=facts['debit'],AccountNumber=facts['account'])
 if facts['account'] is not None:target['AccountName']=next(r['AccountName'] for r in coa if r['AccountNumber']==facts['account'])
 complete=facts['date'] is not None and (not q1(facts['date']) or (facts['debit'] is not None and facts['account'] is not None))
 rows=[r for r in ledger if q1(r['TxnDate']) and r['Currency']=='USD' and (r['GLID']!='GL000072' or complete)]
 totals=defaultdict(lambda:Decimal(0));counts=defaultdict(int)
 for r in rows:totals[r['AccountNumber']]+=Decimal(str(r['Debit']))-Decimal(str(r['Credit']));counts[r['AccountNumber']]+=1
 totals={k:float(v) for k,v in totals.items()};expense=sum(v for k,v in totals.items() if int(k)>=5000);revenue=-sum(v for k,v in totals.items() if k in ['4000','4010'])
 running=95000.;audit=[];deposits=withdrawals=0
 for r in bank:
  dep=float(r['Deposits'] or 0);out=float(r['Withdrawals'] or 0);running+=dep-out;deposits+=dep;withdrawals+=out
  audit.append(dict(reference=r['Reference'],calculated=round(running,2),reported=float(r['Balance']),difference=round(running-float(r['Balance']),2)))
 aps=[r for r in ap if q1(r['InvoiceDate']) and r['Currency']=='USD'];vendor=[]
 for r in bank:
  if not (r['Reference'].startswith('CHK-') or r['Reference']=='EFT-2210'):continue
  matched=[a for a in aps if abs(a['Amount']-float(r['Withdrawals']))<.005 and a['Vendor'].split()[0].lower() in r['Description'].lower()]
  vendor.append(dict(bank=r,amount_vendor_candidates=matched,limitation='Matching amount/vendor supports reconciliation but remittance evidence is needed where dates/status conflict.'))
 aging=[]
 for r in [a for a in ap if a['InvoiceDate']<='2024-03-31' and a['Currency']=='USD']:
  corrected_paid=r['APID']=='AP10274'
  if corrected_paid:continue
  if r['Status']=='Paid' and r['PaidDate'] and r['PaidDate']<='2024-03-31':continue
  days=(datetime(2024,3,31)-datetime.fromisoformat(r['DueDate'])).days
  bucket='Not due' if days<0 else '0-30' if days<=30 else '31-60' if days<=60 else '61-90' if days<=90 else '90+'
  aging.append(dict(invoice=r,days_past_due=days,bucket=bucket,balance=r['Amount'] if r['Status']!='Partial' else None,partial_face_value_upper_bound=r['Amount'] if r['Status']=='Partial' else None,conditional_remaining_after_chk1402=r['Amount']-1847.5 if r['APID']=='AP10003' else None))
 claims=json.loads((p/'source_records.json').read_text()) if (p/'source_records.json').exists() else []
 currencies=defaultdict(int)
 for r in ledger:
  if q1(r['TxnDate']) and r['Currency']!='USD':currencies[r['Currency']]+=1
 return dict(supplemental_records={f.name:json.loads(f.read_text()) for f in p.glob('*.json')},facts=facts,target_row=target,target_resolved_for_q1=complete,selected_usd_q1_rows=rows,account_totals_signed=totals,account_counts=dict(counts),expense_total_if_complete=expense if complete else None,known_expense_subtotal=expense,revenue=revenue,bank=bank,bank_running_audit=audit,bank_deposits=round(deposits,2),bank_withdrawals=round(withdrawals,2),bank_ending=round(running,2),coa=coa,usd_q1_ap=aps,vendor_matches=vendor,aging_after_supported_fast_travel_correction=aging,source_records=claims,unconverted_q1_foreign_currency_rows=dict(currencies),cash_control=dict(gl_cash_rows=sum(r['AccountNumber']=='1000' for r in ledger),actual_gl_cash_balance=None,note='Supplied GL has revenue/expense single-sided sample rows, no cash/control balances or complete double entries. An expense/revenue cash proxy is not the actual accrual GL cash balance. Quantify unresolved reconciling amount without plugging entries.'),payroll_gap=51000-totals.get('6000',0),source_limitations='Populated AP original dataset working sample is not a blank external template. Partial statuses have no paid amount. Match hypotheses do not authorize postings. Foreign currency rows require FX/scope support. Unknown target facts stay null; hidden world ignored.')
