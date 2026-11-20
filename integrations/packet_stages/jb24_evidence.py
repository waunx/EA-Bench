"""JB24 numeric controls and selected-visible source evidence."""
import csv,json,re,sqlite3,hashlib
from pathlib import Path
from datetime import date,timedelta
ROOT=Path(__file__).resolve().parents[2];PACKET=ROOT/'data/expanded/JB24'
def csvrows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def build(variant,world=None,clarification_records=None):
 p=PACKET/'variants'/variant/'inputs';quote=csvrows(p/'vendor_quote_update.csv');q={r['Component']:r for r in quote};memo=(p/'provost_budget_memo.md').read_text()
 m=re.search(r'\*\*(\d+|\[unrecorded\])% of GPU capacity\*\*',memo);s=m[1]
 facts=dict(reserve_pct=int(s) if s.isdigit() else None,h100_max=int(q['H100 SXM 80GB']['Max_Quantity']) if q['H100 SXM 80GB']['Max_Quantity'] else None,lead_weeks=int(q['H100 SXM 80GB']['Availability_Weeks']) if q['H100 SXM 80GB']['Availability_Weeks'] else None)
 for record in clarification_records or []:
  for item in record.get('provided',[]):
   if item['fact_id'] in facts:facts[item['fact_id']]=item['value']
 c=sqlite3.connect('file:'+str(p/'workload_requirements.db')+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
 tables={t:[dict(r) for r in c.execute('select * from '+t)] for t in ['projects','workload_specs','scheduling_constraints','current_resources','historical_utilization']};c.close()
 hardware=[r for r in csvrows(p/'ml_hardware.csv') if r['Hardware name'] in ['NVIDIA H100 SXM5 80GB','NVIDIA A100 SXM4 80 GB']]
 spec={r['project_id']:r for r in tables['workload_specs']};constraints={r['project_id']:r for r in tables['scheduling_constraints']};demand=[]
 for project in tables['projects']:
  w=spec[project['project_id']];sc=constraints[project['project_id']];minimum=w['training_runs_per_month']*w['training_hours_per_run']*w['min_gpus_required']
  demand.append(dict(project=project,workload=w,scheduling=sc,monthly_gpu_hours_at_minimum=minimum,monthly_gpu_hours_at_desired=w['training_runs_per_month']*w['training_hours_per_run']*w['max_gpus_desired'],urgency_factor_before_priority_weight=minimum/sc['deadline_flexibility_days'] if sc['deadline_flexibility_days'] else None))
 base=csvrows(p/'budget_constraints.csv');b={r['Item']:r for r in base};options={}
 for label,column,h,a,n,power in [('A','Option_A_H100x64',64,0,8,350),('B','Option_B_A100x128',0,128,16,380),('C','Option_C_Hybrid',32,64,12,365)]:
  gpu=h*float(q['H100 SXM 80GB']['Updated_Unit_Price_USD'])+a*float(q['A100 SXM 80GB']['Updated_Unit_Price_USD'])
  annual_it=float(b['Power Consumption'][column])*8760*float(b['Electricity Cost'][column]);pue=float(b['Cooling Power Overhead'][column])
  options[label]=dict(h100=h,a100=a,total_gpus=h+a,nodes=n,gpu_only_cost=gpu,dense_fp16_pflops=(h*989.4+a*312)/1000,proposal_power_kw=power,proposal_basis_summer_capacity_fraction=min(1,280/power),baseline_it_power_kw=float(b['Power Consumption'][column]),baseline_pue_total_kw=float(b['Power Consumption'][column])*(1+pue),annual_electricity_without_pue=annual_it,annual_electricity_with_pue=annual_it*(1+pue),reservation_gpu_equivalent=(h+a)*facts['reserve_pct']/100 if facts['reserve_pct'] is not None else None,h100_supply_ok=h<=facts['h100_max'] if facts['h100_max'] is not None else None)
  options[label]['turnkey_node_quote_subtotal']=h/8*float(q['SYS-821GE-TNHR (H100 Node)']['Updated_Unit_Price_USD'])+a/8*float(q['AS-4125GS-TNRT (A100 Node)']['Updated_Unit_Price_USD'])
  def value(item):return float(b[item][column])
  components=dict(gpus=gpu,cpu_nodes=value('CPU Server Nodes')*value('CPU Node Cost'),ndr_switches=value('InfiniBand Network Switches')*float(q['QM9700 NDR Switch']['Updated_Unit_Price_USD']),hcas=value('InfiniBand HCAs')*float(q['ConnectX-7 HCA']['Updated_Unit_Price_USD']),nvlink=value('NVLink Interconnect (H100 only)')*value('NVLink Cost'),storage=value('Storage (Lustre)')*float(q['EXAScaler ES400NVX2 (Lustre)']['Updated_Unit_Price_USD']),ram=value('RAM Cost'),racks=value('Rack Space')*value('Rack Cost'),pdus=value('Power Distribution Units')*value('PDU Cost'),ups=value('UPS Backup')*float(q['9PXM UPS 250kVA']['Updated_Unit_Price_USD']),site=value('Site Preparation'))
  recurring=value('System Admin Staff')*value('Staff Cost per FTE')+value('Software Licenses')+value('Maintenance Contract')+12*value('Bandwidth Cost')
  options[label]['component_bom_control']=dict(components=components,capex_excluding_cooling=sum(components.values()),annual_nonenergy_opex=recurring,three_year_base_excluding_cooling_recs_contingency=sum(components.values())+3*(recurring+annual_it*(1+pue)),assumptions='Component BOM, NDR selection, separate CPU/RAM per baseline; excludes cooling because system/rack scope needs reconciliation; excludes REC/contingency. Not a mandated route.')
 from .artifact_adapter_jb24 import REFERENCES
 ref=REFERENCES['gpu_clusters.csv'];peers=csvrows(ref['path']);cols=['Name','Status','Sector','Owner','Chip type (primary)','Chip quantity (primary)','Chip type (secondary)','Chip quantity (secondary)','Total number of AI chips','16-bit OP/s','Hardware Cost','Reported Cost','Calculated Cost','Power Capacity (MW)','First Operational Date','Source 1']
 peerdata=[{k:r[k] for k in cols} for r in peers if r['Sector']=='Public']
 return dict(confirmed_policy=facts,clarifications=clarification_records or [],proposal=(p/'cluster_proposal.md').read_text(),memo=memo,budget_rows=base,quotes=quote,hardware=hardware,database=tables,workload_controls=demand,options=options,epoch=dict(sha256=ref['sha256'],rows_total=len(peers),public_sector_rows=peerdata),supplemental={f.name:json.loads(f.read_text()) for f in p.glob('*.json')},h100_arrival_jan5_example=(date(2026,1,5)+timedelta(weeks=facts['lead_weeks'])).isoformat() if facts['lead_weeks'] is not None else None,interpretation='Controls are source arithmetic. BOM versus turnkey scope, priority weights, allocation policy, deployment baseline and power/PUE interpretations must be explicit; no fixed Option D is imposed.')
