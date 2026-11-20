"""Selected-visible JB21 sources and Q3 numeric controls."""
import csv,json,hashlib,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict
from datetime import date,timedelta
ROOT=Path(__file__).resolve().parents[2]
PACKET=ROOT/'data/expanded/JB21'
def docx(p):
 with zipfile.ZipFile(p) as z:return ' '.join(ET.fromstring(z.read('word/document.xml')).itertext())
def aggregates(rows,keys):
 groups=defaultdict(list)
 for r in rows:groups[tuple(r[k] for k in keys)].append(r)
 out=[]
 for labels,group in sorted(groups.items()):
  sats=[float(r['Satisfaction_Rating']) for r in group if r['Satisfaction_Rating'].strip()]
  gains=[float(r['Post_Test_Score'])-float(r['Pre_Test_Score']) for r in group if r['Post_Test_Score'].strip() and r['Pre_Test_Score'].strip()]
  completed=sum(r['Completion_Status']=='Completed' for r in group)
  out.append(dict(group=dict(zip(keys,labels)),enrollments=len(group),completed=completed,completion_pct=100*completed/len(group),satisfaction_n=len(sats),satisfaction_mean=sum(sats)/len(sats) if sats else None,paired_gain_n=len(gains),paired_gain_mean=sum(gains)/len(gains) if gains else None,unique_session_dates=len({r['Session_Date'] for r in group}),distinct_module_format_date_sessions=len({(r['Session_Date'],r['Training_Module'],r['Training_Format']) for r in group})))
 return out
def earliest_date(days):
 allowed={dict(Mon=0,Tue=1,Wed=2,Thu=3,Fri=4)[v.strip()] for v in days.split(',')}
 for n in range(31):
  d=date(2025,10,1)+timedelta(days=n)
  if d.weekday() in allowed and d>=date(2025,9,30)+timedelta(days=21) and not 14<=d.day<=18:return d.isoformat()
def build(variant,world=None,clarification_records=None):
 p=PACKET/'variants'/variant/'inputs';rows=list(csv.DictReader((p/'q3_training_evaluation_data.csv').open(encoding='utf-8-sig')))
 availability=list(csv.reader((p/'q4_classroom_instructor_availability.csv').open(encoding='utf-8-sig')))
 pat=next(r for r in availability if r and r[0]=='Patricia Okafor')
 facts=dict(hourly_rate=None if '[unrecorded]' in pat[7] else int(pat[7].replace('$','').replace('/hr','')),session_cap=None if '[unrecorded]' in pat[3] else int(pat[3]),days=None if '[unrecorded]' in pat[4] else pat[4])
 provided={x['fact_id']:x['value'] for r in clarification_records or [] for x in r.get('provided',[])}
 for k in facts:
  if k in provided:facts[k]=provided[k]
 reference=json.loads((PACKET/'private/external_reference_evidence.json').read_text())
 for r in reference.values():assert hashlib.sha256((ROOT/r['source']).read_bytes()).hexdigest()==r['sha256']
 metrics={label:aggregates(rows,keys) for label,keys in [('departments',['Department']),('modules',['Training_Module']),('formats',['Training_Format']),('department_module',['Department','Training_Module']),('module_format',['Training_Module','Training_Format']),('instructors',['Instructor'])]}
 return dict(q3_rows=len(rows),metrics=metrics,comment_records=[{k:r[k] for k in ('Department','Training_Module','Training_Format','Instructor','Comments')} for r in rows if r['Comments'].strip()],availability_csv=availability,director_memo=docx(p/'director_q4_memo.docx'),eif_instrument=docx(p/'eif_training_eval_survey_template.docx'),external_instruments=reference,supplemental={q.name:json.loads(q.read_text()) for q in p.glob('*.json')},confirmed_patricia_policy=facts,clarifications=clarification_records or [],earliest_patricia_day_if_booked_on_memo_date=earliest_date(facts['days']) if facts['days'] else None,patricia_two_hour_session_cost=2*facts['hourly_rate'] if facts['hourly_rate'] is not None else None)
