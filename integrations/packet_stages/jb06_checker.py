"""JB06 complete close evaluation; original scores remain separate."""
import csv,io,json
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from dataclasses import asdict
from .author_english_jb06 import RELEASE
from .jobbench import load_task,OfficialJudge
from .native import artifact_hashes,JobBenchAcceptance
BOOK='December_2024_Month_End_Close.xlsx'
MEMO='December_2024_Variance_Memo.txt'
SHEETS=['Reconciliation','Discrepancies','AP Reconciliation','Journal Entries','Schedule C Summary']
def rows(path):
 return list(csv.DictReader(io.StringIO('\n'.join(l for l in path.read_text(encoding='utf-8-sig').splitlines() if not l.startswith('#') and l.strip()))))
def cents(value):return int(Decimal(str(value).replace('$','').replace(',',''))*100)
def evidence(variant,world):
 import openpyxl
 p=RELEASE/'variants'/variant/'inputs';o=json.loads((RELEASE/'private/oracle.json').read_text());spec=o['variants'][variant]
 unknown=spec['missing']+spec['conflict']
 if any(k not in world for k in unknown):raise ValueError('Missing confirmed invoice field')
 invoices=rows(p/'vendor_invoices_dec2024.csv');target=next(r for r in invoices if r['Invoice_Number']=='INV-2024-0435')
 fields={'issued':'Invoice_Date','due':'Due_Date','amount':'Amount'}
 facts={k:(cents(target[f]) if k=='amount' else target[f]) if target[f] else world.get(k,a['default']) for k,a in o['atoms'].items() for f in [fields[k]]}
 issued=datetime.strptime(facts['issued'],'%m/%d/%Y');due=datetime.strptime(facts['due'],'%m/%d/%Y');close=datetime(2024,12,31)
 assert issued<=due and issued<=close
 target.update(Invoice_Date=facts['issued'],Due_Date=facts['due'],Amount=str(Decimal(facts['amount'])/100))
 b=openpyxl.load_workbook(p/'company_cashbook_dec2024.xlsx',data_only=True)
 cash=[list(r) for r in b['Cash Book'].values if isinstance(r[0],datetime)]
 bank=rows(p/'bank_statement_dec2024.csv');cleared={r['Check or Slip #'] for r in bank if r['Check or Slip #']}
 outstanding=[dict(check=r[1],payee=r[3],cents=cents(r[6])) for r in cash if str(r[1]).isdigit() and str(r[1]) not in cleared]
 ap=rows(p/'ap_aging_report_nov2024.csv');budget=rows(p/'monthly_budget_dec2024.csv')
 coa=openpyxl.load_workbook(p/'chart_of_accounts_template.xlsx',data_only=True)
 names=[r[0] for r in coa['chart of accounts'].values if isinstance(r[1],int)]
 controls=dict(bank_opening_cents=cents(bank[0]['Balance'])-cents(bank[0]['Amount']),bank_closing_cents=cents(bank[-1]['Balance']),book_ending_cents=cents(cash[-1][7]),uncleared_numbered_book_entries=outstanding,uncleared_numbered_book_entry_cents=sum(r['cents'] for r in outstanding),ap_detail_cents=sum(cents(r['Amount']) for r in ap if r['Invoice_Number']),budget_expense_detail_cents=sum(cents(r['Budgeted_Amount']) for r in budget if r['Schedule_C_Line'] not in ['Line 1','N/A']))
 return dict(confirmed_invoice=facts,invoice_controls=dict(age_days=(close-issued).days,overdue_days=max(0,(close-due).days),opening_ap_exception=issued<=datetime(2024,11,30),unpaid_cents=facts['amount']),bank_rows=bank,cashbook_columns=['date','check','description','payee','category','debit','credit','balance'],cashbook_transactions=cash,chart_of_accounts=names,invoice_rows=invoices,opening_ap=ap,budget=budget,controls=dict(controls,classification_note='Uncleared numbered book entries are candidates, not a definitive outstanding-check classification. Reconcile potentially corresponding bank ACH/card payments using payee, invoice and dates, disclose assumptions and avoid duplicate obligations. Candidate total is not an approved bank-side deduction.'),supplements={x.name:json.loads(x.read_text()) for x in p.glob('*.json')})
def structural_checks(artifacts):
 import openpyxl
 root=Path(artifacts);hashes=artifact_hashes(root);checks={BOOK:(root/BOOK).is_file(),MEMO:(root/MEMO).is_file()};details={}
 if checks[BOOK]:
  try:
   b=openpyxl.load_workbook(root/BOOK,data_only=False)
   checks['five_named_sheets']=set(b.sheetnames)==set(SHEETS) and len(b.sheetnames)==5
   checks['nonempty_sheets']=all(sum(c.value is not None for row in s for c in row)>1 for s in b)
   checks['no_excel_error_literals']=not any(c.data_type=='e' or '#REF!' in str(c.value) for s in b for row in s for c in row)
   details['sheets']=b.sheetnames
  except Exception as e:checks['readable_workbook']=False;details['error']=str(e)
 if checks[MEMO]:
  try:checks['nonempty_memo']=bool((root/MEMO).read_text().strip())
  except UnicodeError:checks['nonempty_memo']=False
 return dict(status='pass' if all(checks.values()) else 'fail',checks=checks,details=details,artifact_hashes=hashes)
CRITERIA=[
'The workbook has all five requested functional sheets and the addressed management memo. Read actual workbook evidence, not the submitting agent summary. All cross-sheet amounts and memo totals reconcile.',
'Reconciliation starts at bank closing $34,001.88 and book ending $24,318.72. Individually list and total outstanding numbered checks, other uncleared withdrawals including the EFTPS item, deposits in transit and book adjustments. Match by evidence, not amount alone. Address all four overlapping check numbers 1086-1089 and every unrecorded bank item, including fees, interest, ATM withdrawal and potential duplicate Verizon charge. Show two independently derived adjusted balances, never a balancing plug; explicit provisional assumptions and unresolved differences must not be presented as confirmed cash.',
'Discrepancies systematically covers bank versus cashbook versus invoices, incorrect payees/amounts/dates/categories, invoice partial/unpaid statuses, duplicated charges, missing items, opening-AP inconsistencies and internal total errors. Check 1086 correction is $802.50; 1087 has $350 book/$1,250 bank/$1,520 invoice, leaving $270; 1088 and 1089 also have wrong payee/category/amount. Give specific supported resolutions.',
'AP Reconciliation includes every opening vendor and every new vendor/invoice, showing November opening balance, December invoice additions, evidenced payments/credits, and December ending balance. Do not double-add the November SiteOne invoice re-listed in December; do not assume payments of equal amount discharge different invoice IDs. Retain Premier prior $890 unless evidence settles it, separately show current $270, Ace unpaid amount only if sourced or actually confirmed; otherwise show a pending or conditional obligation and Elite $1,100. Opening AP detail sums to $9,300.46 and agrees with its printed total; do not invent a total discrepancy. Preserve disputed Acme $325 pending vendor/owner/accountant resolution; no unsupported write-off. An invoice sourced or confirmed as issued before December may indicate an opening-AP omission rather than a new December expense. A sourced or confirmed December invoice may be current-period activity. An unconfirmed issue date requires appropriately conditional treatment without a fixed month expectation.',
'Journal Entries supplies complete balanced double-entry corrections with dates, amounts, narrative, and the actual chart-of-accounts names or an explicit defensible mapping. Cover all bank-only omissions, check corrections, fees $25 and $15, interest $3.21, duplicate-charge treatment, and unpaid liabilities. Clearly separate proposed conditional entries from approved entries. Do not double-count prior AP settlement as a new expense or loan principal as deductible expense. No invented transaction is allowed to force agreement.',
'Schedule C Summary covers all budget categories, corrected actuals, budget and mathematically correct signed variances, with official 2024 Schedule C line/category mapping. Distinguish bookkeeping accrual liabilities from cash-basis tax deductibility and disclose the adopted accounting basis rather than assuming it was supplied. EFTPS estimated individual income tax is not a Schedule C business expense; equipment principal/interest, ATM cash classification, and 2025 license timing need supported treatment or stated pending review. The budget expense detail sums to $42,600 and agrees with its printed total; do not invent a total discrepancy. Trace all corrected expense totals to the adjustments and transactions; no raw book totals passed off as corrected.',
'Memo is addressed to Owner, Greenfield Landscaping Services LLC, states supported adjusted cash or clearly provisional balance with unresolved issues, an explicitly defined reconciling-item count matching the worksheet, largest actual budget overruns with amounts, significant resolutions, year-end accountant items and a documented recommendation for Acme disputed invoice. Do not claim verified true cash when unresolved source matching prevents it.',
'Allow alternative transaction classifications and provisional treatments supported by the supplied records and a clearly stated consistent assumption; fixed source arithmetic is not an instruction to invent a resolution. Use invoice fields actually confirmed in the clarification audit consistently in the unpaid balance, age/overdue assessment, period decision and memo. January service/invoice is outside December; cancelled PO creates no debt; identical invoice copy is not another payable. Do not require the model to know private answer keys or hidden rubric wording.'
]
def judge_evidence(variant,world=None,clarification_records=None):
 o=json.loads((RELEASE/'private/oracle.json').read_text());spec=o['variants'][variant]
 # Default values are used only to construct invariant source tables; all
 # unresolved selected fields and derived controls are removed below.
 values={k:a['default'] for k,a in o['atoms'].items()}
 unknown=set(spec['missing']+spec['conflict'])
 for row in clarification_records or []:
  for fact in row.get('provided',[]):
   if fact.get('fact_id') in unknown:values[fact['fact_id']]=fact['value'];unknown.remove(fact['fact_id'])
 ev=evidence(variant,values)
 for key in unknown:ev['confirmed_invoice'][key]=None
 target=next(r for r in ev['invoice_rows'] if r['Invoice_Number']=='INV-2024-0435')
 fields={'issued':'Invoice_Date','due':'Due_Date','amount':'Amount'}
 for key in unknown:target[fields[key]]=None
 dependencies={'age_days':{'issued'},'overdue_days':{'due'},'opening_ap_exception':{'issued'},'unpaid_cents':{'amount'}}
 for key,deps in dependencies.items():
  if deps&unknown:ev['invoice_controls'][key]=None
 ev['clarification_audit']=dict(records=clarification_records or [],unconfirmed_keys=sorted(unknown),instruction='Null fields are not confirmed. Assess honest conditional calculations or pending treatment with explicit reconciliation effects; no hidden selected point or mandatory clarification count is required. Proposed entries are not approved postings.')
 return ev

def completion_rubrics(evidence):
    """Business modules score separately; complete acceptance still requires all."""
    names = ['Deliverables and cross-sheet reconciliation', 'Bank and cashbook reconciliation', 'Discrepancies and supported resolutions', 'Accounts payable completeness', 'Balanced journal entries', 'Schedule C and budget variance', 'Management memo', 'Evidence and conditional treatment']
    context = "Private source evidence for independent verification, not required output wording: " + json.dumps(evidence, default=str)
    return [dict(rubric=name, weight=1, criterion=[criterion, context]) for name, criterion in zip(names, CRITERIA)]


def check(artifacts,private_root,variant='full',world=None,clarification_records=None,**config):
 root=Path(private_root);root.mkdir(parents=True,exist_ok=True);structure=structural_checks(artifacts)
 if structure['status']!='pass':return dict(case='JB06',status='fail',structural=structure,original=dict(status='not_run'),completion=dict(status='not_run'),original_evaluator_runs=0)
 source,_,original=load_task('JB06');ev=judge_evidence(variant,world,clarification_records)
 unconfirmed=ev['clarification_audit']['unconfirmed_keys']
 (root/'source_evidence.json').write_text(json.dumps(ev,indent=2,default=str)+'\n')
 completion = completion_rubrics(ev)
 combined=original+completion;rp=root/'rubrics.json';rp.write_text(json.dumps(dict(rubrics=combined),indent=2)+'\n')
 judge=OfficialJudge(rp,root/'judge',**config);JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,combined,judge)({},{})
 raw=json.loads((judge.last_run/'details.json').read_text())
 native=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,original,judge)._score(raw['rubrics'][:len(original)],structure['artifact_hashes'])
 active=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,completion,judge)._score([dict(r,index=r['index']-len(original)) for r in raw['rubrics'][len(original):]],structure['artifact_hashes'])
 return dict(case='JB06',variant=variant,status='pass' if active.status=='passed' else 'fail',structural=structure,clarification_complete=not unconfirmed,unconfirmed_fields=sorted(unconfirmed),completion_note='Evaluate a complete, consistently qualified close without requiring unknown values to be invented; pending adjustments must remain explicitly pending.',original=asdict(native),completion=asdict(active),judge_run=str(judge.last_run),scope='Original rubric score is unchanged and separate; authored complete-close score is branch-aware and accepts honestly qualified unresolved source issues. Not native environment replay.')
