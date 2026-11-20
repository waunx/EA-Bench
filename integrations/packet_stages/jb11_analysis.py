"""Private workforce factual audit; semantic qualification remains judge-reviewed."""
from pathlib import Path
import csv,json,openpyxl,statistics
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[2];PACKET=ROOT/'data/expanded/JB11'
def resolved(raw,key,records,world):
 if raw not in ['',None]:return raw
 claims=records.get(key+'_records.json',[])
 if claims:
  rev=max(r['revision'] for r in claims);values={r['value'] for r in claims if r['revision']==rev}
  if len(values)==1:return next(iter(values))
 if key not in world:raise ValueError('Unresolved '+key)
 return world[key]
def analyze(variant,world=None):
 folder=PACKET/'variants'/variant/'inputs';world=world or {};records={p.name:json.loads(p.read_text()) for p in folder.glob('*.json')};scope=records['analysis_scope.json']
 apps=list(csv.DictReader((folder/'job_applicants.csv').open(encoding='utf-8-sig')));employees=list(csv.DictReader((folder/'HR_Employee_Attrition_Data.csv').open(encoding='utf-8-sig')))
 w=openpyxl.load_workbook(folder/'job_requirements_matrix.xlsx',read_only=True,data_only=True);rows=list(w['Job Requirements'].values);jobs=[dict(zip(rows[0],r)) for r in rows[1:] if r[0]];w.close()
 a5=next(a for a in apps if a['ApplicantID']=='A005');a6=next(a for a in apps if a['ApplicantID']=='A006');e1=next(e for e in employees if e['EmployeeNumber']=='1');j5=next(j for j in jobs if j['JobID']=='JOB005')
 for obj,field,key in [(a5,'PositionApplied','position5'),(a5,'YearsExperience','experience5'),(a6,'Salary_Expectation','salary6'),(e1,'Attrition','attrition1'),(e1,'OverTime','overtime1'),(j5,'Salary_Range_Min','band5')]:obj[field]=resolved(obj[field],key,records,world)
 archive=records.get('application_archive.json',{})
 if archive.get('application_year')==scope['application_year']:apps+=archive['applicants']
 peer=records.get('peer_workforce.json',{})
 if peer.get('company')==scope['company']:employees+=peer['employees']
 byrole=defaultdict(list)
 for e in employees:byrole[e['JobRole']].append(e)
 jobmap={j['Position']:j for j in jobs};roles=[]
 for role,es in sorted(byrole.items()):
  departed=[e for e in es if e['Attrition']=='Yes'];income=[int(e['MonthlyIncome'])*12 for e in departed];j=jobmap.get(role)
  overtime={ot:dict(n=sum(e['OverTime']==ot for e in es),departed=sum(e['OverTime']==ot and e['Attrition']=='Yes' for e in es)) for ot in ['Yes','No']}
  row=dict(role=role,n=len(es),departed=len(departed),attrition_rate=len(departed)/len(es),overtime=overtime,departed_mean_annual=statistics.mean(income) if income else None,departed_median_annual=statistics.median(income) if income else None)
  if j:row.update(salary_min=j['Salary_Range_Min'],salary_max=j['Salary_Range_Max'],positions_open=j['Positions_Open'],priority=j['Priority_Level'],aggregate_positive_gap=sum(max(0,float(j['Salary_Range_Min'])-v) for v in income))
  roles.append(row)
 screening=[]
 for a in apps:
  j=jobmap[a['PositionApplied']];lo=float(j['Salary_Range_Min']);hi=float(j['Salary_Range_Max']);salary=float(a['Salary_Expectation']);required=j['License_Required'];status=a['LicenseStatus'];basis='applicant_reported'
  record=records.get('license_verification.json',{})
  if record.get('applicant')==a['ApplicantID'] and record.get('license_type')==a['LicenseType'] and record.get('issuer')=='State Board' and a['ApplyDate']<=record['verified_on']<=scope['as_of']:status=record['status'];basis='matched_registry_record'
  license_gate=required=='None Required' or (a['LicenseType'] in required.split(';') and status=='Active')
  screening.append(dict(applicant=a['ApplicantID'],name=a['FirstName']+' '+a['LastName'],position=a['PositionApplied'],education_level=int(a['EducationLevel']),required_education_level=int(j['MinEducationLevel']),required_education_fields=j['Required_EducationFields'],required_experience=int(j['MinYearsExperience']),education_pass=int(a['EducationLevel'])>=int(j['MinEducationLevel']),field=a['EducationField'],field_pass=a['EducationField'] in j['Required_EducationFields'].split(';'),years=int(a['YearsExperience']),experience_pass=int(a['YearsExperience'])>=int(j['MinYearsExperience']),required_skills=j['Required_Skills'],reported_skills=a['Skills'],required_license=required,reported_license=a['LicenseType'],license_status=status,license_basis=basis,license_gate=license_gate,independent_verification_pending=required!='None Required' and basis=='applicant_reported',salary=salary,salary_min=lo,salary_max=hi,salary_position='below' if salary<lo else 'above' if salary>hi else 'in',salary_excess=max(0,salary-hi)))
 return dict(employee_count=len(employees),departed=sum(e['Attrition']=='Yes' for e in employees),applicant_count=len(apps),roles=roles,screening=screening,scope=scope)
