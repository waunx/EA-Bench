"""JB19 as-of student primitives and UCI family-background controls."""
import sqlite3,csv,json
from collections import Counter,defaultdict
from decimal import Decimal
from .author_english_jb19 import RELEASE
CUTOFF='2024-10-21'
def expected(variant,world):
 import openpyxl
 p=RELEASE/'variants'/variant/'inputs';o=json.loads((RELEASE/'private/oracle.json').read_text());spec=o['variants'][variant]
 for k in spec['missing']+spec['conflict']:
  if k not in world:raise ValueError('Missing private course-policy field '+k)
 facts={k:world.get(k,a['default']) for k,a in o['atoms'].items()}
 c=sqlite3.connect('file:'+str(p/'SOCI201_Fall2024.db')+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
 tables={t:[dict(r) for r in c.execute('select * from '+t)] for t in ['students','attendance','assignments','exams','participation','office_hours_visits']};c.close()
 dates=sorted({r['class_date'] for r in tables['attendance'] if r['class_date']<=CUTOFF});students=[]
 for student in tables['students']:
  sid=student['student_id'];att=[r for r in tables['attendance'] if r['student_id']==sid and r['class_date']<=CUTOFF]
  ass=[r for r in tables['assignments'] if r['student_id']==sid and r['due_date']<=CUTOFF];submitted=[r for r in ass if r['submitted_date'] and r['submitted_date']<=CUTOFF]
  part=[Decimal(str(r['participation_score'])) for r in tables['participation'] if r['student_id']==sid and r['week_number']<=10]
  exam=next(r for r in tables['exams'] if r['student_id']==sid and r['exam_name']=='Midterm Exam' and r['exam_date']<=CUTOFF)
  visits=[r for r in tables['office_hours_visits'] if r['student_id']==sid and '2024-10-15'<r['visit_date']<=CUTOFF]
  avg=sum(part)/len(part);missing=len(ass)-len(submitted);exam_pct=Decimal(str(exam['score']))/Decimal(str(exam['max_score']))*100
  students.append(dict(student=student,attendance_counts=dict(Counter(r['status'] for r in att)),attendance_dates=len({r['class_date'] for r in att}),due_assignments=ass,submitted_by_cutoff=len(submitted),assignment_completion_pct=len(submitted)/len(ass)*100,missing_assignments=missing,late_submissions=sum(r['submitted_date']>r['due_date'] for r in submitted),participation_average=float(avg),midterm_pct=float(exam_pct),office_visits_after_midterm=len(visits),controlled_flags=dict(exam=exam_pct<facts['exam_limit'],missing=missing>=facts['missing_limit'],participation=avg<facts['participation_limit'])))
 por=list(csv.DictReader((p/'student-por.csv').open(),delimiter=';'))
 def aggregate(label):
  groups=defaultdict(list)
  for r in por:groups[label(r)].append(r)
  return {k:dict(count=len(v),mean_G3=sum(int(r['G3']) for r in v)/len(v),G3_below10_pct=sum(int(r['G3'])<10 for r in v)/len(v)*100) for k,v in sorted(groups.items())}
 family=dict(neither_parent_higher=aggregate(lambda r:'neither parent higher education' if int(r['Medu'])<4 and int(r['Fedu'])<4 else 'at least one parent higher education'),both_at_most_primary=aggregate(lambda r:'both at most primary' if int(r['Medu'])<=1 and int(r['Fedu'])<=1 else 'other'),parent_cohabitation=aggregate(lambda r:r['Pstatus']),family_size=aggregate(lambda r:r['famsize']))
 wb=openpyxl.load_workbook(p/'SOCI201_Grading_Rubric.xlsx',data_only=True)
 weights={r[0]:r[1] for r in list(wb['Grading_Criteria'].values)[4:12]};wb.close();assert sum(weights.values())==100
 for row in students:
  row['reference_scenarios']={}
  for late_credit in [0,1]:
   row['reference_scenarios']['equal_blend_late_credit_'+str(late_credit)]=grade_scenario(row,weights,late_credit,0.5)
 return dict(cutoff=CUTOFF,attendance_dates=dates,students=students,weights=weights,selected_policy=facts,uci_rows=len(por),uci_family=family,thanksgiving_records=sum(r['class_date']=='2024-11-28' for r in tables['attendance']),future_exam_records=sum(r['exam_date']>CUTOFF for r in tables['exams']),scope='Source primitives for every roster student. Grade scenarios illustrate declared choices, not mandatory attendance/participation split or late-credit policy. Future records cannot be silently used as observed Week-10 performance.')

def grade_scenario(row,weights,late_credit,attendance_share):
 """One auditable scenario; alternatives may use justified explicit policies."""
 counts=row['attendance_counts'];n=sum(counts.values())
 attendance=100*(counts.get('present',0)+late_credit*counts.get('late',0))/n
 participation=row['participation_average']*10
 components={'Attendance & Participation':attendance_share*attendance+(1-attendance_share)*participation,'Midterm Exam':row['midterm_pct']}
 for name,prefix in [('Reading Response 1','Reading Response 1'),('Research Proposal','Research Proposal'),('Midterm Paper','Midterm Paper')]:
  r=next(x for x in row['due_assignments'] if x['assignment_name'].startswith(prefix))
  submitted=r['submitted_date'] and r['submitted_date']<=CUTOFF
  if name=='Midterm Paper' and (not submitted or r['score'] is None):continue
  components[name]=100*r['score']/r['max_score'] if submitted and r['score'] is not None else 0
 active_weight=sum(weights[k] for k in components)
 projected=sum(components[k]*weights[k] for k in components)/active_weight
 flags=dict(row['controlled_flags'],attendance=attendance<70,assignment_completion=row['assignment_completion_pct']<75,current_grade=projected<70,late_submissions=row['late_submissions']>=3,office_hours=row['office_visits_after_midterm']==0)
 return dict(attendance_pct=attendance,components=components,active_weight=active_weight,projected_pct=projected,flags=flags,pending=[k for k in weights if k not in components],assumptions='Equal attendance/participation blend; stated late credit; overdue RR1/proposal non-submissions zero; ungraded/as-of-unavailable paper pending. Other justified policies require recomputation.')
