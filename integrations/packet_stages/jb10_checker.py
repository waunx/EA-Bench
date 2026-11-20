"""JB10 complete compliance, constrained plan and evaluation framework."""
import json
from pathlib import Path
from dataclasses import asdict
from .author_english_jb10 import RELEASE
from .jb10_evidence import expected
from .jobbench import load_task,OfficialJudge
from .native import artifact_hashes,JobBenchAcceptance

def structural_checks(artifacts):
 import openpyxl,fitz
 root=Path(artifacts);hashes=artifact_hashes(root);books=list(root.glob('*.xlsx'));pdfs=list(root.glob('*.pdf'));checks=dict(two_workbooks=len(books)==2,pdf=len(pdfs)==1);details={};matrices=[]
 for p in books:
  try:
   b=openpyxl.load_workbook(p,data_only=False);matrices.append({'Compliance Matrix','Department Risk Dashboard'}<=set(b.sheetnames));details[p.name]=b.sheetnames
   checks[p.name+'_nonempty']=any(sum(c.value is not None for row in s for c in row)>1 for s in b)
   checks[p.name+'_no_errors']=not any(c.data_type=='e' or '#REF!' in str(c.value) for s in b for row in s for c in row)
  except Exception as e:checks[p.name+'_readable']=False;details[p.name]=str(e)
 checks['matrix_named_sheets']=any(matrices)
 if len(pdfs)==1:
  try:
   doc=fitz.open(pdfs[0]);checks['six_to_ten_pages']=6<=len(doc)<=10;checks['pages_have_content']=all(bool(p.get_text().strip() or p.get_images() or p.get_drawings()) for p in doc);details['pdf_pages']=len(doc)
  except Exception as e:checks['readable_pdf']=False;details['pdf_error']=str(e)
 return dict(status='pass' if all(checks.values()) else 'fail',checks=checks,details=details,artifact_hashes=hashes)
CRITERIA=[
'The two Excel deliverables and 6-10-page readable PDF form a consistent integrated response. Do not accept an executive narrative in place of the actual employee matrix, attendee remediation plan, dated schedule, instruments and calculations.',
'Compliance Matrix covers every one of 45 employees by all nine OSHA-required courses (405 combinations) with compliance status and actual last successful completion date, or an explicit absent-success marker. Distinguish current, expiring, overdue, failed and never-completed/incomplete states with a declared assessment date, refresher window and source-status mapping. A failed attempt date is not a successful completion. The private April 6 reference calculation is illustrative; accept another defensible pre-Q2 date with consistently recomputed statuses. Cite applicable OSHA training standards and distinguish the generic needs template from Acme records and US legal authority.',
'Compute and document a composite risk method including compliance gaps/failures, department incident exposure and training recency for incident-correlated courses. Reproducibly score and highlight the ten highest-risk employees, and rank courses so the two assessed courses follow that same approach. Ties or alternative defensible weights are acceptable; do not demand a hidden fixed top-ten list or assume incident counts alone define risk.',
'Department Risk Dashboard covers all eight departments with explicit compliance denominators, overdue OSHA item counts, training-related incidents, mean survey satisfaction, risk priorities and explanatory notes. Use employee IDs rather than nonunique employee names. State the represented employee sample; no invented full-company headcounts, work-hour denominators or causal inference. Distinguish recordable counts/proportions from a true OSHA incidence rate requiring hours worked.',
'Training plan enumerates all 13 weeks April 7-July 4, 2025 with actual sessions: date, start/end or clearly defined slot, course, instructor(s), format, location, target attendees/cohorts and costs. Every employee/course overdue or failed under the declared matrix method must be assigned sufficient remediation finishing by May 2 (the first four training weeks). A generic promise to remediate is insufficient; never-attempted and soon-expiring gaps must also have a defensible priority plan.',
'Enforce resource calendars, instructor weekday/AM/PM availability, weekly session caps, no instructor/venue/attendee overlaps, and qualified course assignment. Preserve course-duration requirements or justify defensible split sessions without counting incomplete hours as completed remediation. Do not book a room in Maintenance/Booked state. Blank Warehouse Training Bay cells are unconfirmed rather than verified availability. Additional venues/instructors, credentials, capacity or release-time assumptions must be labeled and supported, not invented as confirmed resources. Hands-on competencies such as forklift/LOTO/confined-space tasks cannot be declared achieved by virtual lecture alone.',
'For each of the six OSHA courses with training-related incidents, schedule at least one actual session in each of April, May and the June/early-July closing period. State period boundaries explicitly; the last June-30-to-July-4 week may count in that closing period, but cannot hide a missing monthly cycle. Use training-related incidents and course-level survey signals to prioritize topics, explaining disagreements rather than equating satisfaction with safety effectiveness.',
'Cost every in-person session at $650 plus $200 for each instructor and every virtual session at $250 plus $200 for each instructor. Show weekly incremental/cumulative spend for all 13 weeks and a total no higher than $38,000, charging split sessions consistently. Include explicitly priced additional resources when proposed. Do not treat the ceiling as mandatory expenditure or omit costs to manufacture feasibility.',
'PDF begins with a retrospective comparison identifying three courses where Level 1 satisfaction diverges most from actual safety outcomes using a documented comparison method and actual course-level figures. Analyze open-feedback weaknesses and redesign a usable survey, including virtual-delivery questions and a retrospective before/after self-assessment informed by the Kirkpatrick/NC State reference. Distinguish observed outcomes, exposure/selection limits and causal hypotheses.',
'For the two highest course risks from the declared composite model, provide 8-10 specific knowledge-assessment items each usable pre/post; the same paired items may be administered before and after. Ground content in applicable OSHA provisions rather than generic awareness. Provide a 90-day supervisor observation checklist of specific observable behaviors tied to appropriate subsections. Set three measurable KPIs with numerically grounded baselines and end-Q3 2025 targets, defining timing, numerator/denominator and responsibility.',
'ROI uses actual baseline incident data (52 incidents, 23 recordables, 129 lost work days) and the actual priced plan total; $38,000 is a ceiling, not necessarily spending. Distinguish observed metrics from assumed unit costs and reduction scenarios, avoid double-counting direct/indirect losses, state time horizons and show transparent savings/ROI arithmetic and sensitivity. Do not invent a sourced industry cost benchmark if none was supplied or consulted.',
'Apply booking-week, instructor identity and confirmation status to scoped supplements. For an unresolved room or instructor constraint, a plan valid under every feasible interpretation can succeed without a clarification. A plan relying on the less restrictive interpretation needs actual source/clarification support, not a private-world lucky guess. Honest conditional contingencies are evaluated as such; a tentative resource cannot be described as an already confirmed booking.'
]
def check(artifacts,private_root,variant='full',world=None,clarification_records=None,**config):
 root=Path(private_root);root.mkdir(parents=True,exist_ok=True);structure=structural_checks(artifacts)
 if structure['status']!='pass':return dict(case='JB10',status='fail',structural=structure,original=dict(status='not_run'),completion=dict(status='not_run'))
 source,_,original=load_task('JB10');ev=expected(variant,world or {});o=json.loads((RELEASE/'private/oracle.json').read_text());spec=o['variants'][variant]
 provided={x['fact_id'] for r in (clarification_records or []) for x in r.get('provided',[])};unconfirmed=set(spec['missing']+spec['conflict'])-provided
 ev['clarification_audit']=dict(records=clarification_records or [],unconfirmed_alternatives={k:[o['atoms'][k]['default'],o['atoms'][k]['alternative']] for k in unconfirmed},instruction='Accept any source-supported schedule valid across all remaining interpretations. Do not force questions for unused resources, or score a lucky unsupported assumption as confirmed.')
 (root/'source_evidence.json').write_text(json.dumps(ev,indent=2,default=str)+'\n')
 completion=[dict(rubric='Complete compliance, feasible training plan and integrated evaluation framework',weight=1,criterion=CRITERIA+['Independent source-grounded evidence. Use a declared assessment-date method; do not treat the illustrative reference matrix as an immutable hidden answer: '+json.dumps(ev,default=str)])]
 combined=original+completion;rp=root/'rubrics.json';rp.write_text(json.dumps(dict(rubrics=combined),indent=2)+'\n');judge=OfficialJudge(rp,root/'judge',**config)
 JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,combined,judge)({},{})
 raw=json.loads((judge.last_run/'details.json').read_text());score=lambda rubrics,data:asdict(JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,rubrics,judge)._score(data,structure['artifact_hashes']))
 native=score(original,raw['rubrics'][:len(original)]);active=score(completion,[dict(r,index=r['index']-len(original)) for r in raw['rubrics'][len(original):]])
 return dict(case='JB10',variant=variant,status='pass' if active['status']=='passed' else 'fail',structural=structure,original=native,completion=active,unconfirmed_resource_fields=sorted(unconfirmed),judge_run=str(judge.last_run),scope='Full artifact scoring with source/clarification-aware resource alternatives. Original rubric score separate; no native replay.')
