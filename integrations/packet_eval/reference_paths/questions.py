"""Recognise unresolved facts from this task's visible records, not variant IDs."""
def unknown_keys(case,env,d):
 if case not in {'AW01','AW04','AW08','JB03','JB11','WB02','WB14'}:
  raw=env['observe'](d);unknown=[]
  for key,value in raw.items():
   if value is not None:continue
   records=[r for r in d.get('claims',[]) if r['fact']==key]
   if records:
    top=max(r['revision'] for r in records)
    if len({r['value'] for r in records if r['revision']==top})==1:continue
   unknown.append(key)
  return sorted(unknown)
 if case=='JB03':
  raw={k:next(r for r in d[f['table']] if r['id']==f['id'])[f['field']] for k,f in env['FIELD_MAP'].items()}
 elif case=='AW08':raw=env['visible'](d)
 elif case=='AW01':
  order=lambda name:next(r for r in d['orders.csv'] if r['order']==name)
  offer=lambda name:next(r for r in d['offers.csv'] if r['quote']==name)
  raw=dict(deadline='known' if 'case_decision.md' in d else None,
           budget=None if '[unconfirmed]' in d['return_terms.md'] else 'known',
           purchased_size=order('O102')['size'],last_order_status=order('O103')['status'],
           exp_stock=offer('Q_WHITE_EXP')['stock'],standard_arrival=offer('Q_WHITE_STD')['arrival'])
 elif case=='AW04':
  product=lambda name:next(r for r in d['products.csv'] if r['sku']==name)
  raw=dict(grant_address='known' if 'case_decision.md' in d else None,
           prime_price=None if '[not loaded]' in d['membership.md'] else 'known',
           b_stock=product('POP_B')['stock'],c_gift=product('POP_C')['gift'],a_rating=product('POP_A')['rating'],
           remote_shipping=next(r['shipping_cents'] for r in d['quote_rules.csv'] if r['zone']=='R'))
 elif case=='JB11':
  emp=next(r for r in d['HR_Employee_Attrition_Data.csv'] if r['EmployeeNumber']=='1')
  app=lambda key:next(r for r in d['job_applicants.csv'] if r['ApplicantID']==key)
  raw=dict(attrition1=emp['Attrition'],overtime1=emp['OverTime'],position5=app('A005')['PositionApplied'],
           experience5=app('A005')['YearsExperience'],salary6=app('A006')['Salary_Expectation'],
           band5=next(r['Salary_Range_Min'] for r in d['jobs'] if r['JobID']=='JOB005'))
 elif case=='WB02':
  staff=lambda key:next(r for r in d['employees.csv'] if r['employee']==key)
  raw=dict(eligible_y=staff('Y')['eligible'],same_task='known' if 'case_decision.md' in d else None,c_last_lead=staff('C')['last_lead'])
 elif case=='WB14':
  raw=dict(qa='known' if 'case_decision.md' in d else None,
           busy_end=d['calendar.csv'][0]['end'],recipient=d['recipient_binding.json']['contact'],
           workspace=d['workspace_binding.json']['workspace'],
           calendar_state=next(r['status'] for r in d['calendar.csv'] if r['event']=='CAL3'),
           lead_state=next(r['deleted'] for r in d['crm.csv'] if r['id']=='NL2'))
 unknown=[]
 for key,value in raw.items():
  if value not in ['',None]:continue
  filename='inventory_copies.json' if case=='AW01' and key=='exp_stock' else 'migration_adjudications.json' if case=='WB02' and key=='same_task' else key+'_records.json'
  field='stock' if filename=='inventory_copies.json' else 'same_task' if filename=='migration_adjudications.json' else 'value'
  records=d.get(filename,[])
  if records:
   rev=max(r['revision'] for r in records)
   if len({r[field] for r in records if r['revision']==rev})==1:continue
  unknown.append(key)
 return sorted(unknown)
