"""JB21 source-backed semantic artifact judging; original diagnostic remains separate."""
from pathlib import Path
from dataclasses import asdict
import json,zipfile,xml.etree.ElementTree as ET
import openpyxl
from .jb21_evidence import build,PACKET
from .jobbench import load_task,OfficialJudge
from .native import artifact_hashes,JobBenchAcceptance

def structural_checks(artifacts):
 root=Path(artifacts);files=list(root.rglob('*'));checks={};details={}
 for suffix in ('.xlsx','.docx','.pdf'):
  found=[p for p in files if p.suffix.lower()==suffix];checks[suffix+'_present']=bool(found)
  if not found:continue
  try:
   if suffix=='.xlsx':
    w=openpyxl.load_workbook(found[0],data_only=False);checks['readable_workbook']=True;details['sheets']=w.sheetnames
    checks['no_excel_errors']=not any(c.data_type=='e' for s in w for row in s for c in row);w.close()
   elif suffix=='.docx':
    with zipfile.ZipFile(found[0]) as z:ET.fromstring(z.read('word/document.xml'))
   else:assert found[0].read_bytes().startswith(b'%PDF')
  except Exception as exc:checks[suffix+'_readable']=False;details[suffix+'_error']=str(exc)
 return dict(status='pass' if all(checks.values()) else 'fail',checks=checks,details=details,artifact_hashes=artifact_hashes(root),scope='Formats only; no keyword or answer-ID acceptance')

CRITERIA=[
'Compute Q3 completion, satisfaction and paired pre/post gains by department, module, delivery format and module-department combination using actual nonmissing denominators. Flag all combinations below80% completion or3.5 satisfaction, not only two named aggregate modules. Distinguish enrolments, completions and missing responses.',
'Compute every raw instructor scorecard and teaching volume. Distinguish unique teaching dates from distinct module/format/date sessions; enrolments are not sessions. Reconcile names and credentials with evidence, without presuming identity or qualifications. Karen Lim and Karen Yamamoto are not a substantiated match; absent and new instructors require appropriately qualified recommendations.',
'Provide the original four named workbook sheets and October-December calendar with dates, times, durations, formats, instructors, rooms and department/cohort access sufficient to assess feasibility. Every department must access compliance-critical modules; consider all10 Q3 modules with justified mandatory scope. Respect Facilities mandatory completion before December15 and monthly compliance delivery. Preserve patient safety quality and reschedule underperforming self-paced modules as classroom/blended; extra virtual make-ups supplement that remediation.',
'Validate every scheduled session against ALL source room/instructor rules: weekdays, hours, blocked dates, caps across modules, capacities, skills, formats, overlaps, advance notice, shared hours, equipment and setup/teardown buffers. The Simulation Center Tue/Thu and required onsite Marcus Mon/Wed/Fri have no overlap: acknowledge this and propose a contingent arrangement or feasible alternative rather than inventing availability. Terrence also conflicts with Simulation Center weekdays. Preferences allow reasoned tradeoffs; hard unavailability needs confirmation.',
'Provide early feasible October Patricia virtual recovery opportunities for Facilities/Administration under confirmed weekdays, advance notice from an explicit planning date, cap and platform rules. Multiple same-day nonoverlapping sessions are allowed. No fixed date list, start time, cap exhaustion or unique calendar is imposed. A smaller justified number, robust plan or conditional alternatives can satisfy uncertain demand/policy. September30 booking permits first day October22 for Mon/Wed, October21 for Tuesday. Later booking assumptions need support. Hidden values never establish confirmed policy; conditional work can be valid without a forced question.',
]
CRITERIA += [
'Cross-reconcile every schedule row and budget: paid three-hour classroom/blended and two-hour virtual sessions times applicable hourly rates, monthly and per-instructor subtotals, overall total, internal zero, and visible external-session color coding. Patricia recovery costs flow into schedule, budget and consultant recommendation. Cancelled bookings, curriculum-review rates and another organization contract do not govern delivery. Unknown rate/cap remains conditional.',
'Word redesign opens with Evaluator Instructions, practical administration/timing, section-level Kirkpatrick mapping and accurate audit of all three source instruments versus actual Q3 columns. Cover Levels1-3 with Likert, multiple-choice, short-answer and skills self-assessment checklist items. Probe format interaction, language/literacy, pacing and job relevance. Make post-return Level3 behavior operational within staffing; self-reported confidence is not demonstrated behavior. Do not require Level4 implementation.',
'PDF memo addresses every director priority with accurate quantitative and qualitative evidence, realistic costs/tradeoffs, likelihood-by-impact risk matrix with mitigation, data-supported retain/replace/renegotiate choices for each external consultant and exactly three closing quick wins. Acknowledge missing Q3 linkage rather than invent performance. Do not demand all three recommendation labels or a fixed prose layout.',
'Assess business outcomes and feasibility, not keyword or answer-ID presence. Original requested calculations and cross-source documentation suffice; no extra reasoning transcript, fixed tool sequence, question wording or artifact structure. No numeric minimum tool-call or information count is proven.'
]
def completion_rubrics(evidence):
 return load_task('JB21')[2]+[dict(rubric='Integrated training analysis, feasible calendar, reconciled budget and practical evaluation redesign',weight=10,criterion=CRITERIA+['Actual selected-visible sources and independent numeric controls: '+json.dumps(evidence)])]

def check(artifacts,private_root,variant='full',world=None,clarification_records=None,**config):
 private_root=Path(private_root);private_root.mkdir(parents=True,exist_ok=True)
 structure=structural_checks(artifacts)
 if structure['status']!='pass':return dict(case='JB21',status='fail',structural=structure,original=dict(status='not_run'))
 evidence=build(variant,world,clarification_records);(private_root/'source_evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
 source,path,rubrics=load_task('JB21');judge=OfficialJudge(path,private_root/'original_judge',**config)
 original=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,rubrics,judge)({},{})
 active=completion_rubrics(evidence);rp=private_root/'completion_rubrics.json';rp.write_text(json.dumps(dict(rubrics=active),indent=2)+'\n')
 other=OfficialJudge(rp,private_root/'completion_judge',**config)
 completion=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,active,other)({},{})
 return dict(case='JB21',status='pass' if structure['status']=='pass' and completion.status=='passed' else 'fail',structural=structure,original=asdict(original),completion=asdict(completion),original_judge_run=str(judge.last_run),completion_judge_run=str(other.last_run),scope='All original rubrics preserved; additional narrative business coverage with selected-visible source evidence; no native replay.')
