"""JB10 source-grounded compliance, incident and survey controls."""
import json,csv
from datetime import date,timedelta
from collections import Counter,defaultdict
from .author_english_jb10 import RELEASE

def expected(variant,world):
 import openpyxl
 p=RELEASE/'variants'/variant/'inputs';o=json.loads((RELEASE/'private/oracle.json').read_text());facts={k:world.get(k,a['default']) for k,a in o['atoms'].items()}
 for k in o['variants'][variant]['missing']+o['variants'][variant]['conflict']:
  if k not in world:raise ValueError('Missing private schedule-world field '+k)
 b=openpyxl.load_workbook(p/'acme_manufacturing_training_records.xlsx',data_only=True)
 def records(name):
  r=list(b[name].values);return [dict(zip(r[0],x)) for x in r[1:] if x[0]]
 training=records('Training Completion Log');incidents=records('Safety Incident Log');resources=[list(r) for r in b['Resource Availability Q2 2025'].values]
 resources[2][2]=facts['room'];resources[19][10]=facts['robert_wed'];resources[19][13]=facts['robert_cap']
 survey=list(csv.DictReader((p/'post_training_survey_responses.csv').open()))
 employees={r['Employee_ID']:dict(name=r['Employee_Name'],department=r['Department']) for r in training}
 required={r['Course_Code']:r['Course_Name'] for r in training if r['Required_By_OSHA']=='Yes'}
 groups=defaultdict(list)
 for r in training:groups[(r['Employee_ID'],r['Course_Code'])].append(r)
 asof=date(2025,4,6);matrix=[]
 for emp in sorted(employees):
  for course in sorted(required):
   rr=sorted(groups[(emp,course)],key=lambda r:r['Training_Date']);completed=[r for r in rr if r['Completion_Status']=='Completed'];last=completed[-1]['Training_Date'] if completed else None
   if not rr:status='Never Completed'
   elif rr[-1]['Completion_Status']=='Failed':status='Failed'
   elif rr[-1]['Completion_Status']=='Overdue':status='Overdue'
   elif rr[-1]['Completion_Status']=='Incomplete':status='Never Completed'
   else:
    raw=rr[-1]['Refresher_Due_Date']
    due=date.fromisoformat(raw) if raw and raw!='N/A' else None
    status='Overdue' if due and due<asof else ('Expiring within 60 days' if due and due<=asof+timedelta(days=60) else 'Current')
   matrix.append(dict(employee=emp,course=course,status=status,last_completed=last))
 def survey_groups(key):
  g=defaultdict(list)
  for r in survey:g[r[key]].append(r)
  return {k:dict(responses=len(v),satisfaction=sum(float(r['Overall_Satisfaction_1to5']) for r in v)/len(v)) for k,v in sorted(g.items())}
 training_incidents=Counter(r['Relevant_Course_Code'] for r in incidents if r['Training_Related']=='Yes')
 controls=dict(employee_count=len(employees),required_courses=len(required),training_records=len(training),incidents=len(incidents),recordables=sum(r['OSHA_Recordable']=='Yes' for r in incidents),lost_days=sum(r['Lost_Work_Days'] for r in incidents),training_related_by_course=dict(training_incidents),surveys=len(survey))
 cols=['Employee_ID','Department','Course_Code','Required_By_OSHA','Training_Date','Completion_Status','Refresher_Due_Date','Training_Hours']
 return dict(world=facts,controls=controls,employees=employees,required_courses=required,training_columns=cols,training_rows=[[r[k] for k in cols] for r in training],incidents=incidents,resource_sheet=resources,survey_by_course=survey_groups('Course_Name'),survey_by_department=survey_groups('Department'),survey_by_format=survey_groups('Training_Format'),feedback_counts=dict(Counter(r['Open_Feedback'] for r in survey)),reference_matrix=dict(as_of=str(asof),interpretation='Illustrative pre-Q2 date, not an authored requirement. Accept another explicitly declared defensible pre-Q2 assessment date and consistently recomputed status; a successful last completion date is not a failed/incomplete attempt date.',cells=matrix),supplements={x.name:json.loads(x.read_text()) for x in p.glob('*.json')})
