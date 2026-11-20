"""Complete private source controls for the six LEEC disputes."""
import csv,json,hashlib,sys
from pathlib import Path
from decimal import Decimal
from datetime import date,timedelta
import openpyxl
ROOT=Path(__file__).resolve().parents[2]
PACKET=ROOT/'data/expanded/JB25'
EXTERNAL=ROOT/'data/source/dataset/customer_service_representatives/task1/files_required_to_search'

def records(sheet):
 rows=list(sheet.values)
 return [dict(zip(rows[0],r)) for r in rows[1:] if r[0] is not None]

def business_days(as_of,deadline,holidays=()):
 start=date.fromisoformat(as_of);end=date.fromisoformat(deadline)
 if end<start:return -business_days(deadline,as_of,holidays)
 return sum((start+timedelta(days=n)).weekday()<5 and (start+timedelta(days=n)).isoformat() not in holidays for n in range(1,(end-start).days+1))

def evidence(variant):
 p=PACKET/'variants'/variant/'inputs'
 w=openpyxl.load_workbook(p/'Customer_Billing_Disputes_Jan2025.xlsx',data_only=True)
 tables={s.title:records(s) for s in w};w.close()
 with (p/'Erie_PA_Weather_Oct2024_Jan2025.csv').open(encoding='utf-8-sig') as f:weather=list(csv.DictReader(f))
 jan=[r for r in weather if r['Station']=='KERI' and r['Date'].startswith('2025-01')]
 base=[r for r in weather if r['Station']=='KERI' and '2024-10-01'<=r['Date']<'2025-01-01']
 jh=sum(int(r['Heating_Degree_Days']) for r in jan);bh=sum(int(r['Heating_Degree_Days']) for r in base)
 benchmarks={}
 for f in EXTERNAL.glob('*.xlsx'):
  b=openpyxl.load_workbook(f,data_only=True);s=b.active;rows=list(s.values)
  assert '2024' in str(rows[0][0]);pa=[r for r in rows if r[0]=='Pennsylvania'];assert len(pa)==1
  benchmarks[f.name]=dict(title=rows[0][0],headers=rows[2],pennsylvania=pa[0],sha256=hashlib.sha256(f.read_bytes()).hexdigest());b.close()
 price=Decimal(str(benchmarks['EIA_Residential_Avg_Price_By_State.xlsx']['pennsylvania'][1]));bill=Decimal(str(benchmarks['EIA_Residential_Avg_Monthly_Bill.xlsx']['pennsylvania'][4]))
 controls=[]
 for dispute in tables['Dispute Records']:
  account=next(r for r in tables['Customer Accounts'] if r['Account_ID']==dispute['Account_ID'])
  history=[r for r in tables['Billing History'] if r['Account_ID']==dispute['Account_ID']]
  current=next(r for r in history if r['Billing_Period']=='2025-01')
  previous=next(r for r in history if r['Billing_Period']=='2024-12')
  baseline=[r for r in history if r['Billing_Period'] in ['2024-10','2024-11','2024-12']];assert len(baseline)==3
  annual=[r for r in history if r['Billing_Period'].startswith('2024-')];assert len(annual)==12
  jr=Decimal(str(current['kWh_Used']))/jh;br=sum(Decimal(str(r['kWh_Used'])) for r in baseline)/bh
  controls.append(dict(dispute=dispute,account=account,january=current,december=previous,jan_dec_2024_mean_kwh=str(sum(Decimal(str(r['kWh_Used'])) for r in annual)/12),baseline_kwh=sum(r['kWh_Used'] for r in baseline),january_kwh_per_hdd=str(jr),baseline_kwh_per_hdd=str(br),normalized_change_pct=str((jr/br-1)*100),energy_rate_cents=str(Decimal(str(current['Rate_per_kWh']))*100),effective_bill_cents_per_kwh=str(Decimal(str(current['Total_Bill']))/Decimal(str(current['kWh_Used']))*100),bill_vs_pa_pct=str((Decimal(str(current['Total_Bill']))/bill-1)*100),energy_rate_vs_pa_pct=str((Decimal(str(current['Rate_per_kWh']))*100/price-1)*100)))
  controls[-1]['claimed_minus_recorded_january_bill']=str(Decimal(str(dispute['Disputed_Amount']))-Decimal(str(current['Total_Bill'])))
  controls[-1]['business_day_examples']={anchor:dict(weekdays_only=business_days(anchor,dispute['Resolution_Deadline']),excluding_feb17=business_days(anchor,dispute['Resolution_Deadline'],['2025-02-17'])) for anchor in ['2025-01-31','2025-02-03']}
 if '/tmp/ea-bench-analysis-deps' not in sys.path:sys.path.append('/tmp/ea-bench-analysis-deps')
 import pymupdf
 with pymupdf.open(p/'PA_Utility_Consumer_Rights.pdf') as doc:guide=[dict(page=i+1,text=page.get_text()) for i,page in enumerate(doc)]
 legal=json.loads((PACKET/'private/public_refs/sections.json').read_text())
 selected={k:legal[k] for k in ['56.2','56.12','56.15','56.100','56.141','56.151','56.152','56.153','56.156','56.161','56.181'] if k in legal}
 with (p/'Supervisor_Preliminary_Notes.csv').open(encoding='utf-8-sig') as f:notes=list(csv.DictReader(f))
 return dict(tables=tables,dispute_controls=controls,supervisor_notes=notes,benchmarks=benchmarks,guide=guide,governing_provisions=selected,code_provenance=json.loads((PACKET/'private/public_refs/provenance.json').read_text()),
  weather=dict(january_days=len(jan),baseline_days=len(base),january_hdd=jh,baseline_hdd=bh,below_zero_low_days=sum(float(r['Low_Temp_F'])<0 for r in jan),mean_departure=sum(float(r['Departure_From_Normal_F']) for r in jan)/len(jan),extreme_warning_dates=[r['Date'] for r in jan if 'extreme cold' in r['Weather_Event'].lower()]),
  source_weather=weather,supplements={f.name:json.loads(f.read_text()) for f in p.glob('*.json')},
  assumptions='Deadline examples are scenarios, not an assigned date. Require declared as-of/counting convention and holiday choices. Aggregate kWh/HDD does not prove causation. Statewide price scope differs from energy-only rate. Total charges alone do not prove level-payment, true-up or discount eligibility.')
