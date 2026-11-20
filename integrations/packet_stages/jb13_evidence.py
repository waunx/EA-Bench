"""JB13 portfolio controls and original CDFI source evidence."""
import csv,json,hashlib
from decimal import Decimal
from collections import defaultdict,Counter
from .author_english_jb13 import RELEASE,REFERENCE_ROOT

def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def expected(variant,world):
 import openpyxl
 p=RELEASE/'variants'/variant/'inputs';o=json.loads((RELEASE/'private/oracle.json').read_text());spec=o['variants'][variant]
 for k in spec['missing']+spec['conflict']:
  if k not in world:raise ValueError('Missing private credit world field '+k)
 facts={k:world.get(k,a['default']) for k,a in o['atoms'].items()}
 loans=rows(p/'meridian_branch_loan_portfolio.csv');apps=rows(p/'pending_loan_applications.csv');balances={r['Loan_ID']:Decimal(r['Outstanding_Balance']) for r in loans};total=sum(balances.values())
 watch=[r for r in loans if int(r['Risk_Rating'][0])>=3];npa=[r for r in loans if r['Payment_Status'] in ['Nonaccrual','90_Plus_Days_Past_Due']]
 groups=defaultdict(list)
 for r in loans:groups[r['Loan_Type']].append(r)
 types={k:dict(balance=float(sum(balances[r['Loan_ID']] for r in v)),count=len(v),weighted_rate_pct=float(sum(balances[r['Loan_ID']]*Decimal(r['Interest_Rate']) for r in v)/sum(balances[r['Loan_ID']] for r in v))) for k,v in groups.items()}
 cross=defaultdict(lambda:dict(count=0,balance=Decimal(0)))
 for r in loans:
  k=r['Payment_Status']+' | '+r['Risk_Rating'];cross[k]['count']+=1;cross[k]['balance']+=balances[r['Loan_ID']]
 sectors=defaultdict(Decimal)
 for r in loans:sectors[r['Industry_Sector'] or 'Unassigned sector: '+r['Loan_Type']]+=balances[r['Loan_ID']]
 fdic=openpyxl.load_workbook(REFERENCE_ROOT/'fdic_qbp_loan_performance_q4_2024.xlsx',data_only=True).active
 col=next(c.column for row in fdic for c in row if c.value=='2024Q4')
 benchmark=fdic.cell(464,col).value;assert 'Noncurrent rate' in str(fdic.cell(464,2).value)
 cdfi=json.loads((RELEASE/'private/cdfi_extraction.json').read_text());assert hashlib.sha256((p/'loan_risk_rating_sheet.xls').read_bytes()).hexdigest()==cdfi['sha256']
 borrower=defaultdict(Decimal)
 for r in loans:borrower[r['Borrower_Name']]+=balances[r['Loan_ID']]
 controls=dict(rows=len(loans),active_records=sum(r['Payment_Status']!='Paid_Off' for r in loans),balance=float(total),yield_pct=float(sum(balances[r['Loan_ID']]*Decimal(r['Interest_Rate']) for r in loans)/total),npa_count=len(npa),npa_balance=float(sum(balances[r['Loan_ID']] for r in npa)),watch_count=len(watch),watch_balance=float(sum(balances[r['Loan_ID']] for r in watch)),fdic_noncurrent_fraction=benchmark,fdic_cell=fdic.cell(464,col).coordinate)
 controls['npa_pct']=controls['npa_balance']/float(total)*100;controls['adverse_variance_bp']=(controls['npa_pct']/100-benchmark)*10000
 return dict(world=facts,derek_controls=dict(fico_gate_pass=facts['fico']>=620,shortfall=max(0,620-facts['fico']),dti_pct=round(2385*12/facts['income']*100,1),bankruptcy_recent=facts['discharged']>='2019-01-01'),controls=controls,by_loan_type=types,by_sector={k:dict(balance=float(v),pct=float(v/total*100)) for k,v in sectors.items()},payment_risk_cross={k:dict(v,balance=float(v['balance'])) for k,v in cross.items()},top_loans=sorted(loans,key=lambda r:balances[r['Loan_ID']],reverse=True)[:5],top_borrowers=sorted([dict(name=k,balance=float(v),pct=float(v/total*100)) for k,v in borrower.items()],key=lambda r:-r['balance'])[:5],loans=loans,applications=apps,watch=watch,cdfi=cdfi,supplements={x.name:json.loads(x.read_text()) for x in p.glob('*.json')})
