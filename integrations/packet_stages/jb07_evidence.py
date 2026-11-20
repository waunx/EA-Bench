"""Private all-process reference calculations; never mounted in solver inputs."""
from pathlib import Path
from decimal import Decimal
import csv,json
import openpyxl
ROOT=Path(__file__).resolve().parents[2]
PACKET=ROOT/'data/expanded/JB07'
MAPPING={'DPR':'Parks & Recreation','DSNY':'Sanitation','DOT':'Transportation','DHS':'Health Services','FDNY':'Fire Department'}
def calculate(variant='full',world=None,clarification_records=None):
 oracle=json.loads((PACKET/'private/oracle.json').read_text())
 spec=oracle['variants'][variant];required=set(spec['missing']+spec['conflict'])
 supplied={item['fact_id']:item['value'] for rec in clarification_records or [] for item in rec['provided']}
 facts={k:supplied.get(k,(world or {}).get(k,a['default'])) for k,a in oracle['atoms'].items()}
 folder=PACKET/'variants'/variant/'inputs'
 book=openpyxl.load_workbook(folder/'Greenfield_Dept_Staffing_Overtime_FY2024.xlsx',data_only=True)
 processes=[]
 for department,name,cycle,target,rate,volume,error,automation in list(book['Process_Metrics'].values)[1:]:
  if name=='Environmental Complaint Investigation':
   rate=facts['on_time'] if 'on_time' in required else rate
   volume=facts['volume'] if 'volume' in required else volume
   automation=facts['automation'] if 'automation' in required else automation
  processes.append(dict(department=department,process=name,cycle_days=cycle,target_days=target,on_time_pct=rate,monthly_volume=volume,automation=automation,late_monthly=str((Decimal(str(volume))*(1-Decimal(str(rate))/100)).quantize(Decimal('.001'))),below_65=rate<65,below_70=rate<70))
 departments={}
 for name in MAPPING.values():
  staff=[r for r in list(book['Staffing_Summary'].values)[1:] if r[0]==name]
  ot=[r for r in list(book['Monthly_Overtime'].values)[1:] if r[1]==name]
  authorized=sum(r[2] for r in staff);filled=sum(r[3] for r in staff)
  departments[name]=dict(authorized=authorized,filled=filled,vacancy_pct=100*(authorized-filled)/authorized,ot_cost=sum(r[4] for r in ot),ot_pct_weighted=100*sum(r[3] for r in ot)/sum(r[2] for r in ot),ot_pct_monthly=[dict(month=r[0],reported_pct=r[5]) for r in ot],worst_on_time_pct=min(r['on_time_pct'] for r in processes if r['department']==name),salary_proxy=sum(r[3]*r[7] for r in staff),hiring_divisions=[r[1] for r in staff if r[4]>12],turnover_by_division={r[1]:r[6] for r in staff})
 book.close()
 with (folder/'Greenfield_311_Service_Requests_FY2024.csv').open() as f:requests=list(csv.DictReader(f))
 for code,name in MAPPING.items():
  rows=[r for r in requests if r['Department']==code]
  closed=[float(r['Resolution_Days']) for r in rows if r['Status'].lower()=='closed' and r['Resolution_Days'].strip()]
  departments[name]['service_requests']=len(rows)
  departments[name]['closed_resolution_observations']=len(closed)
  departments[name]['mean_closed_resolution_days']=sum(closed)/len(closed) if closed else None
 provided={r['fact_id'] for rec in clarification_records or [] for r in rec.get('provided',[])}
 spec=oracle['variants'][variant];unknown=set(spec['missing']+spec['conflict'])-provided
 return dict(processes=processes,departments=departments,greenfield_311_department_mapping=MAPPING,nyc_mmr_analog_mapping={'DPR':'Parks & Recreation','DSNY':'Sanitation','DOT':'Transportation','DOHMH':'Health Services','FDNY':'Fire Department'},clarification_records=clarification_records or [],unconfirmed_world_attributes=sorted(unknown),scope='Private reference calculations. Weighted annual OT and closed-only 311 are disclosed reference definitions; justified labeled alternatives remain assessable. World values are grading context, not proof of solver knowledge.')
