"""JB19 full business-artifact judging, without keyword or row-count gates."""
from pathlib import Path
from dataclasses import asdict
import json,zipfile,xml.etree.ElementTree as ET
import openpyxl
from .author_english_jb19 import RELEASE as PACKET
from .jb19_evidence import expected
from .jobbench import load_task,OfficialJudge
from .native import artifact_hashes,JobBenchAcceptance

def structural_checks(artifacts):
 root=Path(artifacts);checks={};details={}
 try:
  w=openpyxl.load_workbook(root/'SOCI201_EarlyAlert_Week10.xlsx',data_only=False)
  checks['readable_named_workbook']=True
  checks['no_excel_error_cells']=not any(c.data_type=='e' for s in w for row in s for c in row)
  details['sheets']=w.sheetnames;w.close()
 except Exception as e:checks['readable_named_workbook']=False;details['workbook_error']=str(e)
 try:
  with zipfile.ZipFile(root/'Holistic_Intervention_Plan.docx') as z:ET.fromstring(z.read('word/document.xml'))
  checks['readable_named_intervention_plan']=True
 except Exception as e:checks['readable_named_intervention_plan']=False;details['docx_error']=str(e)
 return dict(status='pass' if all(checks.values()) else 'fail',checks=checks,details=details,artifact_hashes=artifact_hashes(root),scope='Original filenames and readable formats; no keyword, sheet-count or row-count acceptance')

CRITERIA=[
 'Validate every roster student as of October 21, 2024. Future attendance, future exam scores and future-due assignments are not observed Week-10 performance. Submission after cutoff is not received as of cutoff. Participation uses through Week10. Audit the whole database including Thanksgiving, separating future anomalies from current denominators.',
 'Calculate each assignment/exam percentage using its actual database max_score, then apply the matching rubric component weight. Do not merge all assignments into one weight or use total raw points as the weighted grade. Treat the Midterm Paper as graded only when supported as of cutoff; distinguish future and genuinely ungraded components, and show the normalization/earned-weight basis. Attendance & Participation has one combined15% weight; no internal split or late-credit rule is supplied. Accept justified explicit interpretations and recompute accordingly, rather than silently imposing one reference scenario.',
 'Evaluate all eight risk indicators for every student against applicable course rules: attendance, assignment completion, current grade, midterm, participation, missing assignments, late submissions and no post-midterm office visits. The private policy values govern changed thresholds only if confirmed by actual visible/clarified evidence. Strict less-than versus greater-or-equal boundaries, completed assignment denominator and visits strictly after October15 through cutoff must be correct. A roster containing correct IDs without correct indicator values is insufficient.',
 'Adapt the original monitoring ranges to the selected thresholds: attendance/current-grade/assignment-completion/midterm percentages run from their at-risk threshold through five percentage points above it; participation runs from its threshold through0.5 on the10-point scale. Monitoring is preventive and distinct from at-risk flags.',
 'Use a transparent priority-weighted composite for all students with High greater than Medium greater than Low and justify weights/aggregation. Keep preventive monitoring separate from at-risk status using applicable threshold buffers; the count indicators may have justified monitoring rules but none is mandated. No fixed weights, risk tiers or printed calculation sequence is required beyond the original visible calculation methodology.',
 'Individual student risk summaries must reflect actual indicators and appropriate academic/nonacademic support. Tier intensity follows demonstrated needs rather than names or broad keyword matches. Include differentiated actionable outreach templates with respectful language, clear next steps and implementation constraints, responsibilities, resources and follow-up.',
 'Use specific accurate What Works Clearinghouse advising-guide recommendations and citations to support interventions. Distinguish academic advising/tutoring/study strategies from financial/basic-needs/counseling or other appropriate supports; avoid diagnosing personal problems from grades alone. Explain feasibility, privacy and referrals in the academic setting.',
 'Perform actual source-backed UCI family-background/outcome analysis with defined Medu/Fedu groupings, group denominators and numeric outcomes such as G3. Coding, labels and interpretation must agree; neither parent higher education is different from both at most primary education. Other defensible coded constructs are allowed. Explain secondary versus postsecondary and Portuguese versus US context, observational associations and lack of individual SOCI201 prediction.',
 'Private selected-world values are grading context, not proof of solver knowledge. Actual file evidence and clarification determine confirmed thresholds. Supported unresolved/provisional analyses receive appropriate partial criterion credit; unsupported correct guesses do not establish confirmed policy. No prescribed tool sequence, question wording, exact sheet layout or arbitrary formula/ID/token quota is required.'
]

def judge_evidence(variant,world=None,clarification_records=None):
 o=json.loads((PACKET/'private/oracle.json').read_text());spec=o['variants'][variant]
 # Actual delivered clarification values, never hidden selected world values.
 provided={x['fact_id']:x.get('value') for r in clarification_records or [] for x in r.get('provided',[])}
 unresolved=set(spec['missing']+spec['conflict'])-provided.keys()
 facts={k:provided.get(k,a['default']) for k,a in o['atoms'].items()}
 evidence=expected(variant,facts)
 for k in unresolved:evidence['selected_policy'][k]=None
 keymap={'exam_limit':'exam','missing_limit':'missing','participation_limit':'participation'}
 for row in evidence['students']:
  for k in unresolved:
   row['controlled_flags'][keymap[k]]=None
   for scenario in row['reference_scenarios'].values():scenario['flags'][keymap[k]]=None
 evidence['clarification_audit']=dict(records=clarification_records or [],unconfirmed_policy_attributes=sorted(unresolved))
 import openpyxl,hashlib
 guide=json.loads((PACKET/'private/advising_guide_evidence.json').read_text())
 assert guide['source_sha256']==hashlib.sha256((PACKET/'variants'/variant/'inputs/Effective_Advising_Practice_Guide.pdf').read_bytes()).hexdigest()
 evidence['advising_guide']=guide
 w=openpyxl.load_workbook(PACKET/'variants'/variant/'inputs/SOCI201_Grading_Rubric.xlsx',data_only=True)
 evidence['visible_rubric']={s.title:list(s.values) for s in w};w.close()
 evidence['supplemental_records']={p.name:json.loads(p.read_text()) for p in (PACKET/'variants'/variant/'inputs').glob('*.json')}
 return evidence

def completion_rubrics(evidence):
 import copy
 original=copy.deepcopy(load_task('JB19')[2])
 original[0]['rubric']='Does the grade calculation correctly apply all eight original component weights, include Midterm Paper only when graded as of October 21, and mark genuinely ungraded/future components pending?'
 # Preserve every original rubric, weight and compatible criterion. Only fixed
 # policy numbers in the two affected rubrics become evidence-relative.
 replacements={'Each indicator uses the exact threshold value specified in the At_Risk_Criteria sheet without modification.':'Each indicator uses the applicable confirmed course threshold, preserving all non-varied criteria; unresolved thresholds remain conditional.', 'Midterm Exam Score <60%':'Midterm Exam Score below the applicable confirmed threshold','Participation Score <5/10 average':'Participation Score below the applicable confirmed threshold','Missing Assignments >=2':'Missing Assignments at or above the applicable confirmed threshold','midterm exam score 60-65%':'midterm exam score from its applicable confirmed threshold through five percentage points above','participation score 5.0-5.5 out of 10':'participation score from its applicable confirmed threshold through 0.5 above on the 10-point scale'}
 for i in (2,3):
  for field in ('rubric','criterion'):
   items=original[i][field] if isinstance(original[i][field],list) else [original[i][field]]
   for old,new in replacements.items():items=[x.replace(old,new) for x in items]
   original[i][field]=items if field=='criterion' else items[0]
  original[i]['criterion'].append('For unresolved policy, evaluate accurate conditional/provisional work without selecting a hidden threshold. Confirmation must come from visible applicable files or actual delivered clarification.')
 return original+[dict(rubric='Complete dated early-alert computations and evidence-based holistic intervention',weight=10,criterion=CRITERIA+['Source reference; scenario assumptions are illustrative, not authoritative course policy: '+json.dumps(evidence)])]

def check(artifacts,private_root,variant='full',world=None,clarification_records=None,**config):
 private_root=Path(private_root);private_root.mkdir(parents=True,exist_ok=True)
 structure=structural_checks(artifacts)
 if not structure['artifact_hashes']:return dict(case='JB19',status='fail',structural=structure,original=dict(status='not_run'))
 evidence=judge_evidence(variant,world,clarification_records)
 (private_root/'source_evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
 source,path,rubrics=load_task('JB19');judge=OfficialJudge(path,private_root/'original_judge',**config)
 original=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,rubrics,judge)({},{})
 active=completion_rubrics(evidence);rp=private_root/'completion_rubrics.json';rp.write_text(json.dumps(dict(rubrics=active),indent=2)+'\n')
 other=OfficialJudge(rp,private_root/'completion_judge',**config)
 completion=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,active,other)({},{})
 return dict(case='JB19',status='pass' if structure['status']=='pass' and completion.status=='passed' else 'fail',structural=structure,original=asdict(original),completion=asdict(completion),original_judge_run=str(judge.last_run),completion_judge_run=str(other.last_run),scope='Active business completion with adapted selected-policy thresholds; unchanged original default score separate. Source scenarios are not fixed grading assumptions.')
