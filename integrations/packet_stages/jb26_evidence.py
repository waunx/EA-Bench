"""JB26 source-linked numeric deficiencies; no fixed disposition totals."""
from pathlib import Path
from datetime import datetime,date
import csv,json,sqlite3,re
from .artifact_adapter_jb26 import PACKET,REFERENCES

def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def norm(x):return re.sub('[^a-z0-9]','',str(x).lower())
def parse(x):return datetime.strptime(x,'%m/%d/%Y').date()
def match(app,records):
 found=[]
 for raw in records:
  r={k.lower():v for k,v in raw.items()};prior=app['PriorLicenseNumber']
  if (prior and norm(r.get('contractorlicensenumber',''))==norm(prior)) or norm(r.get('businessname',''))==norm(app['ApplicantName']):found.append(raw)
 return found

def build(variant,world=None,clarification_records=None):
 p=PACKET/'variants'/variant/'inputs';apps=rows(p/'pending_applications_batch_2025Q1.csv');rules=rows(p/'regulatory_updates_2025.csv');bonds=rows(p/'wa_contractor_bond_subset.csv')
 refs={n:rows(s['path']) for n,s in REFERENCES.items()}
 c=sqlite3.connect('file:'+str(p/'wa_contractor_violations.db')+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
 tables={t:[dict(r) for r in c.execute('select * from '+t)] for t in ('violations','complaints')};c.close()
 inspection=json.loads((p/'field_inspection_notes.json').read_text());controls=[]
 rule=next(r for r in rules if r['BulletinID']=='RB-2025-001');prior,new=map(int,re.search(r'from \$(\d+) to \$(\d+)',rule['Detail']).groups());specialties=rule['AffectedSpecialties'].split(';')
 for app in apps:
  appdate=parse(app['ApplicationDate']);threshold=new if app['SpecialtyRequested'] in specialties and appdate>=parse(rule['EffectiveDate']) else prior
  violations=match(app,tables['violations']);complaints=match(app,tables['complaints']);same=[a['ApplicationID'] for a in apps if norm(a['PrincipalName'])==norm(app['PrincipalName']) and a['ApplicationID']!=app['ApplicationID']]
  controls.append(dict(application=app,bond_minimum=threshold,application_bond_shortfall=max(0,threshold-int(app['BondAmount'])),pre_update_bond_minimum=prior,insurance_expired_at_application=parse(app['InsuranceExpirationDate'])<appdate,exam_passed=app['ExamPassed']=='Yes',financial_statement_filed=app['FinancialStatementFiled']=='Yes',background_clear=app['BackgroundCheckStatus']=='CLEAR',duplicate_principal_applications=same,violations=violations,complaints=complaints,unpaid_penalties=sum(r['PenaltyAmount'] for r in violations if r['PenaltyPaid']=='No'),paid_penalties=sum(r['PenaltyAmount'] for r in violations if r['PenaltyPaid']=='Yes'),bond_subset_matches=match(app,bonds),public_subset_matches={n:match(app,r) for n,r in refs.items()}))
 hold_rule=next(r for r in rules if r['BulletinID']=='RB-2025-003');months=int(re.search(r'(\d+)-month',hold_rule['Detail'])[1]);holds=[]
 for field in inspection['inspections']:
  linked=next((r for r in tables['complaints'] if r['ComplaintID']==field['related_complaint_id'] and r['ComplaintType']=='UNLICENSED_WORK'),None)
  if linked:
   start=date.fromisoformat(field['date']);month_index=start.year*12+start.month-1+months;until=date(month_index//12,month_index%12+1,start.day)
   holds.append(dict(inspection=field['inspection_id'],complaint=linked['ComplaintID'],finding_date=start.isoformat(),hold_until_if_applied=until.isoformat(),bulletin_effective=hold_rule['EffectiveDate']))
 queue=(p/'incoming_correspondence_queue.txt').read_text();reduced=int(re.search(r'reduced the bond to \$(\d[\d,]*)',queue)[1].replace(',',''));cancel=parse(re.search(r'cancelled effective\s+(\d{2}/\d{2}/\d{4})',queue)[1])
 changes=dict(reported_reduced_bond=reduced,reduction_shortfall=prior-reduced,cancellation_effective=cancel.isoformat(),scope='Correspondence claims require recorded follow-up; no carrier contact is invented')
 return dict(correspondence_bond_controls=changes,unlicensed_hold_controls=holds,applicants=controls,bulletins=rules,inspection=inspection,correspondence=(p/'incoming_correspondence_queue.txt').read_text(),reference_coverage={n:dict(rows=len(r),sha256=REFERENCES[n]['sha256'],scope='Cached subset, not exhaustive current or Q1 historical verification. No-match is not proof of no record; carrier confirmation is separate.') for n,r in refs.items()},bond_subset_rows=len(bonds),database=tables,supplemental={f.name:json.loads(f.read_text()) for f in p.glob('*.json') if f.name!='field_inspection_notes.json'},latest_application_date=max(parse(a['ApplicationDate']) for a in apps).isoformat(),limitations='Application-row arithmetic is not final disposition. Correspondence, dated evidence, public-match limitations and management judgment must be reconciled. No fixed approval/denial/hold counts.')
