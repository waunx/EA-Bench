"""Case-specific sufficient statistics; calculated only from visible input data."""
from copy import deepcopy
from collections import Counter, defaultdict
from decimal import Decimal
from datetime import datetime, date

def reduce_data(case, raw):
 d=deepcopy(raw)
 if case=='JB01':
  d['life']=[{k:r[k] for k in ['State','County','Census Tract Number','Life Expectancy']} for r in d['life']]
  d['obesity']=[{k:r[k] for k in ['LocationDesc','YearStart','Stratification1','Data_Value']} for r in d['obesity'] if r['YearStart']=='2023' and r['Stratification1']=='Total']
  d['demographics']=[{k:r[k] for k in ['State',"Education.Bachelor's Degree or Higher"]} for r in d['demographics']]
 elif case=='JB03':
  d['researchers']=[{'id':r['id']} for r in d['researchers']]
  d['computing_needs']=[{k:r[k] for k in ['id','researcher_id','gpu_hours_monthly','memory_gb_required','current_wait_time_hours','workload_type']} for r in d['computing_needs']]
  d['current_infrastructure']=[{k:r[k] for k in ['id','status','num_gpus']} for r in d['current_infrastructure']]
  d.pop('software_requirements',None)
 elif case=='JB08':
  target=next(r for r in d['sales'] if r['Order ID']=='CA-2016-152156' and r['Product ID']=='FUR-BO-10001798')
  others=sum(Decimal(r['Profit']) for r in d['sales'] if r is not target and r['Sub-Category']=='Bookcases')
  keys=['Order ID','Product ID','Sub-Category','Profit','Sales']
  d['sales']=[{k:target[k] for k in keys},{'Order ID':'__other_bookcases_total__','Product ID':'aggregate','Sub-Category':'Bookcases','Profit':str(others),'Sales':'0'}]
  d['tickets']={'TK-2024-0910':d['tickets']['TK-2024-0910']}
 elif case=='JB11':
  d['_applicant_count']=len(d['job_applicants.csv'])
  d['job_applicants.csv']=[r for r in d['job_applicants.csv'] if r['ApplicantID'] in ['A001','A005','A006','A015']]
  groups=Counter()
  for r in d.pop('HR_Employee_Attrition_Data.csv'):
   target=r['EmployeeNumber']=='1'
   relevant=target or r['JobRole']=='Research Scientist' and r['Attrition']=='Yes'
   fields=(r['EmployeeNumber'] if target else 'other',r['Attrition'],r['OverTime'],r['JobRole'] if relevant else 'other',r['MonthlyIncome'] if relevant else '0')
   groups[fields]+=1
  d['_employee_groups']=[[list(k),v] for k,v in groups.items()]
 elif case=='JB15':
  countries={};personal=defaultdict(set)
  for r in d.pop('people'):
   countries[r[0]]=r[1];personal[r[0]].add(tuple(r))
  grouped=defaultdict(list)
  for key,value in countries.items():grouped[value].append(key)
  d['_people_groups']=[[k,v] for k,v in grouped.items()]
  d['_personal_conflicts']=[k for k,v in personal.items() if len(v)>1]
 elif case=='JB18':
  orders=d.pop('orders');copy=d.get('shipment_copy');target=None
  if copy:target=next(r for r in orders if (r['Order_ID'],r['Product_ID'],r['Plant_Code'])==(copy['order'],copy['product'],copy['plant']))
  d['_orders_summary']={'count':len(orders),'units':sum(int(r['Unit_Quant']) for r in orders),'target':{k:target[k] for k in ['Order_ID','Product_ID','Plant_Code','Unit_Quant']} if target else None}
 elif case=='JB23':
  totals={k:Decimal(0) for k in ['5000','5010','6000']};target=None
  for r in d['ledger']:
   if r[0]=='GL000072':target=r;continue
   if datetime(2024,1,1)<=r[1]<datetime(2024,4,1) and r[9]=='USD' and r[2] in totals:
    totals[r[2]]+=Decimal(str(r[4]))-Decimal(str(r[5]))
  d['ledger']=[target];d['_ledger_totals']={k:str(v) for k,v in totals.items()}
  e=d.get('statement_export')
  d['bank']=[r for r in d['bank'] if e and r['Reference']==e['reference'] and r['Date']==e['date']]
 elif case=='JB24':d.pop('proposal',None)
 elif case=='JB29':
  d['units']=[{k:r[k] for k in ['unit_id','current_status','current_location_lat','current_location_lng']} for r in d['units']]
  d['queue']=[{k:r[k] for k in ['call_id','location_lat','location_lng']} for r in d['queue']]
  d.pop('e1_assignments',None)
 return d

def restore_data(case, raw):
 d=deepcopy(raw)
 if case=='JB11':
  d['job_applicants.csv'] += [{'ApplicantID':'__other_applicant__'}]*(d.pop('_applicant_count')-len(d['job_applicants.csv']))
  keys=['EmployeeNumber','Attrition','OverTime','JobRole','MonthlyIncome']
  d['HR_Employee_Attrition_Data.csv']=[dict(zip(keys,row)) for row,n in d.pop('_employee_groups') for _ in range(n)]
 elif case=='JB15':
  conflicts=set(d.pop('_personal_conflicts'))
  d['people']=[(key,country,marker) for country,keys in d.pop('_people_groups') for key in keys for marker in range(2 if key in conflicts else 1)]
 elif case=='JB18':
  stats=d.pop('_orders_summary');target=stats['target']
  empty={'Order_ID':'__aggregate__','Product_ID':'__aggregate__','Plant_Code':'__aggregate__','Unit_Quant':'0'}
  total=dict(empty,Unit_Quant=str(stats['units']-(int(target['Unit_Quant']) if target else 0)))
  d['orders']=[total]+([target] if target else [])+[empty]*(stats['count']-1-int(target is not None))
 elif case=='JB23':
  for account,amount in d.pop('_ledger_totals').items():
   d['ledger'].append(['__other_Q1_USD__',datetime(2024,1,1),account,None,amount,0,None,None,None,'USD'])
 return d

def json_default(value):
 if isinstance(value,datetime):return {'__datetime__':value.isoformat()}
 if isinstance(value,date):return {'__date__':value.isoformat()}
 raise TypeError(type(value).__name__)

def json_hook(value):
 if set(value)=={'__datetime__'}:return datetime.fromisoformat(value['__datetime__'])
 if set(value)=={'__date__'}:return date.fromisoformat(value['__date__'])
 return value
