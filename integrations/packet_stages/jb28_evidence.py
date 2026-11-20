"""Financial controls from selected visible data and actual replies only."""
from collections import defaultdict
from datetime import datetime
import csv,json,hashlib
import openpyxl
from .artifact_adapter_jb28 import PACKET,REF,REFERENCES

def tax(x):
 x=max(0,x);out=0;last=0
 for cap,rate in [(23850,.10),(96750,.12),(206700,.22),(394600,.24),(501050,.32),(751600,.35),(float('inf'),.37)]:
  out+=max(0,min(x,cap)-last)*rate;last=cap
 return out

def project(pension,qualified=True):
 ordinary=pension+36800+(0 if qualified else 18500);ss=60180;deduction=33200
 a=b=1450000.;roth=0;cum_a=cum_b=0;rows=[]
 divisors=[26.5,25.5,24.6,23.7,22.9,22,21.1,20.2,19.4,18.5,17.7,16.8]
 for year in range(2025,2041):
  ra=a/divisors[year-2029] if year>=2029 else 0;rb=b/divisors[year-2029] if year>=2029 else 0;c=100000 if year<2029 else 0
  base=max(0,ordinary+ss-deduction);ta=tax(base+ra)-tax(base);tb=tax(base+rb+c)-tax(base)
  a=a*1.06-ra;b=b*1.06-rb-c;roth=roth*1.06+c;cum_a+=ta;cum_b+=tb
  rows.append(dict(year=year,rmd_a=ra,rmd_b=rb,conversion=c,end_traditional_a=a,end_traditional_b=b,end_roth=roth,incremental_ordinary_tax_a=ta,incremental_ordinary_tax_b=tb))
 return dict(assumptions='Illustrative year-end flows, fixed 2025 MFJ ordinary brackets, $33,200 deduction (base $30,000 plus two age additions), no later-law senior deduction; constant income. Incremental ordinary tax only. Complete analysis also treats qualified/LTCG stacking, gift sale, state tax and future-law sensitivity. Other supported assumptions allowed.',rows=rows,cumulative_incremental_a=cum_a,cumulative_incremental_b=cum_b,net_saving=cum_a-cum_b)

def build(variant,world=None,clarification_records=None):
 p=PACKET/'variants'/variant/'inputs';w=openpyxl.load_workbook(p/'client_portfolio_holdings.xlsx',data_only=False);sheets={s.title:list(s.values) for s in w};w.close()
 income=sheets['Income_and_Distributions'];hold=sheets['Portfolio_Holdings'];facts=dict(pension=income[3][2],nvda_basis=hold[23][6],dividend_class=income[4][3])
 for record in clarification_records or []:
  for item in record.get('provided',[]):
   if item['fact_id'] in facts:facts[item['fact_id']]=item['value']
 selected_records=json.loads((p/'source_records.json').read_text()) if (p/'source_records.json').exists() else []
 controls=dict(social_security=70800,portfolio_income=63700,nonqualified_dividends=4200,interest=32600,capital_gain_distributions=8400,dividend_distribution_a=18500)
 if facts['pension'] is not None:
  controls.update(gross_income=facts['pension']+134500,provisional_without_conversion=facts['pension']+99100,provisional_with_conversion=facts['pension']+199100,taxable_social_security=60180)
 if facts['pension'] is not None and facts['dividend_class'] is not None:
  controls['ordinary_excluding_ss']=facts['pension']+36800+(18500 if facts['dividend_class']=='Ordinary Income' else 0)
  controls['conversion_base_excluding_ss']=controls['ordinary_excluding_ss']+100000
 taxable=[]
 for r in hold[1:]:
  if 'Taxable' not in r[0]:continue
  basis=facts['nvda_basis'] if r[1]=='NVDA' else r[6]
  taxable.append(dict(ticker=r[1],shares=r[5],price=r[7],value=r[8],basis_per_share=basis,gain=r[8]-r[5]*basis if basis is not None else None))
 totals=defaultdict(float)
 for r in hold[1:]:totals[r[0]]+=r[8]
 gift=dict(cash=82500,additional_proceeds=67500,lowest_gain_sale_ticker='VXUS',fractional_shares=67500/56.82,realized_gain=67500*(1-48/56.82),gain_tax_at_15pct=67500*(1-48/56.82)*.15,note='Gross gift excludes tax funding. Whole shares require rounding and leftover cash. Unknown NVDA basis permits provisional cash/VXUS strategy, not proof of global minimum without supported basis bounds.')
 treasury=[];groups=defaultdict(list)
 for r in csv.DictReader((REF/'treasury_yield_curve_2024.csv').open()):
  d=datetime.strptime(r['Date'],'%m/%d/%Y');row=dict(date=d.strftime('%Y-%m-%d'),slope=float(r['10 Yr'])-float(r['2 Yr']),ten=float(r['10 Yr']),two=float(r['2 Yr']));treasury.append(row);groups[d.strftime('%Y-%m')].append(row)
 treasury.sort(key=lambda r:r['date'])
 monthly={m:dict(mean_slope=sum(r['slope'] for r in rs)/len(rs),month_end=sorted(rs,key=lambda r:r['date'])[-1]) for m,rs in sorted(groups.items())}
 equities=defaultdict(list)
 for r in csv.DictReader((REF/'sp500_monthly_2024.csv').open()):
  if '2024-01'<=r['observation_date'][:7]<='2025-01' and r['SP500'] not in ['', '.']:equities[r['observation_date'][:7]].append((r['observation_date'],float(r['SP500'])))
 sp={m:dict(mean=sum(v for d,v in rs)/len(rs),month_end=sorted(rs)[-1][1],observations=len(rs)) for m,rs in sorted(equities.items())}
 macro={n:list(csv.DictReader((p/n).open())) for n in ['cpi_monthly_data.csv','federal_funds_rate_history.csv']}
 cpi={r['observation_date']:float(r['CPIAUCSL']) for r in macro['cpi_monthly_data.csv'] if r['CPIAUCSL'] not in ['', '.']}
 fed={r['observation_date']:float(r['FEDFUNDS']) for r in macro['federal_funds_rate_history.csv'] if r['FEDFUNDS'] not in ['', '.']}
 real={}
 for date,level in cpi.items():
  prior=str(int(date[:4])-1)+date[4:]
  if prior in cpi and date in fed:real[date]=dict(inflation_pct=100*(level/cpi[prior]-1),nominal=fed[date],real_approx_pct=fed[date]-100*(level/cpi[prior]-1))
 controls['real_policy_matched_dates']=real
 controls['targets_after_gift']={r[0]:(sum(totals.values())-150000)*r[3] for r in sheets['Asset_Allocation_Current'][1:-1]}
 projection=project(facts['pension'],facts['dividend_class']=='Qualified Dividend') if facts['pension'] is not None and facts['dividend_class'] is not None else None
 return dict(facts=facts,selected_sources=sheets,source_records=selected_records,income_controls=controls,taxable_holdings=taxable,account_holdings_totals=dict(totals),holdings_total=sum(totals.values()),summary_total=2800000,unreconciled=2800000-sum(totals.values()),post_gift_itemized=sum(totals.values())-150000,gift_control=gift,monthly_treasury=monthly,first_daily_nonnegative=next(r for r in treasury if r['slope']>=0),first_daily_positive=next(r for r in treasury if r['slope']>0),sp500=sp,sp500_mean_12m=sp['2025-01']['mean']/sp['2024-01']['mean']-1,sp500_monthend_12m=sp['2025-01']['month_end']/sp['2024-01']['month_end']-1,macro_raw=macro,illustrative_projection=projection,public_reference_hashes={n:r['sha256'] for n,r in REFERENCES.items()},limitation='Unconfirmed client quantities stay null. No hidden world is used. Scenarios or supported bounds are legitimate; exact selected values are not required without a reply.')
