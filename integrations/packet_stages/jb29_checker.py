"""Source/state-backed simulated dispatch grading and original diagnostic."""
from pathlib import Path
from dataclasses import asdict
import json,copy,csv,openpyxl
from .jb29_evidence import build,PACKET
from .jb29_state import check_state
from .jobbench import load_task,OfficialJudge
from .native import artifact_hashes,JobBenchAcceptance

def structural_checks(artifacts,variant):
 p=Path(artifacts);checks={};details={}
 for name in ['dispatch_decisions.xlsx','shift_handover.xlsx']:
  try:
   w=openpyxl.load_workbook(p/name,data_only=False);checks[name]=True;checks[name+'_no_excel_errors']=not any(c.data_type=='e' for s in w for row in s for c in row);details[name]=w.sheetnames;w.close()
  except Exception as e:checks[name]=False;details[name]=str(e)
 try:checks['conflict_report']=bool(list(csv.DictReader((p/'conflict_report.csv').open(encoding='utf-8-sig'))))
 except Exception:checks['conflict_report']=False
 state=check_state(p/'dispatch_cad.db',variant);checks['actual_cad_state']=state['status']=='pass'
 return dict(status='pass' if all(checks.values()) else 'fail',checks=checks,details=details,state=state,artifact_hashes=artifact_hashes(p),scope='Readable artifacts and actual persisted SQLite synchronization; no SQL-text substitute.')

CRITERIA=[
'Triage every15 incoming call from caller details, with adjusted priority, assigned/requested units and reasoning. Cardiac001,fire002,entrappedMVA003,symptomaticgas004,chestpain005,unresponsive008,severeCOPD010,water013,stroke014 demand urgentP1 handling. Fall006 generallyP2; kitchen007 and carfire011 need engine/scene assessment; smoke009 and alarm015 lower priority with investigation rather than certainty of false alarm. Laceration012 heavybleeding requires prompt bleeding control and escalation if uncontrolled; justifiedP1/P2 based on stated uncertainty allowed. No fixed unique matching or unjustified global ordering among equally urgent calls.',
'Use units and roles coherently: ALS requires actualALS capability; engines/BLS ambulances can provide support but not substitute forALS. M1/M3/M4/M6/M8 are initially freeALS. More concurrent urgent needs exist than these5 units, so show explicit staged/escalated aid, readiness and resource prerequisites. Do not blindly assign the same medic to multiple independent incidents or pretend EMS supervisors conferALS.',
]
CRITERIA += [
'Water013 requiresSwiftWater:E2 has it but is committedA06. Either document simulated release/redirection with A06coverage and consistent old/new assignments or mark specialty pending/escalated. Other rescue/engine units may provide shore support but do not fulfill waterentry specialty. Gas004 needs evacuation/scene safety,HazMat and medical assessment; HAZMAT1 is free while E12 is committed. Fire002 needs a justified engine/truck/command response; MVA003 needs extrication-capable response and medical care, with tool/capability assumptions explicit.',
'Reconcile CSV and CAD: E4,E11,T6,BC4,EMS4 are committedA02; E11CSVAVAILABLE08:00 is superseded by later CADON_SCENE08:33 withoutclear. Other busy assignments persist until documented simulated release. E1 has no CADassignment, which does not establish readiness. Station coordinates do not establish its liveposition. Missingstatus orposition permits conditional capability/distance or alternative freeunits; no private selected point is required.',
'Matching matrix must distinguish capability eligibility from actual availability and proximity. Compute explicit straight-line distances with a stated geodesic method; station-based proxy is not liveETA. Globally deconflict units and account for travel/readiness/coverage, allowing justified nonclosest allocation. M4 is a close strokeALS candidate but not a mandatory unit if committed to a competing need. No shift roster/end times are supplied, so flag relief uncertainty without inventing shiftend facts.',
'Compare all incoming/existing reports by address,coordinates,time and event. No exact overlapping address appears in source; call001 vsA07 are near0.223km but distinctaddresses,008 vscompletedA01 near0.189km are MStreet versusKStreet. These are review candidates, not establishedduplicates. Preserve all 15 reports. If a supported repeated-report case is linked, a shared physical response may link one unit to multiple reports without duplicating resource consumption; independent calls must not be conflated.',
'Output an actual updatedCADcopy with15 insertedcallrecords preserving source fields, existing8records and18assignment histories. Proposed reassignment must retain provenance and reconcile priorassignment release/newcommitment. Log synchronization anomalies and pendingresources; database assignment/status/priority must agree with dispatchworkbook and handover. SQLtext, comments claiminginsertion or a rebuilt emptyDB are insufficient. InputDB stays unchanged.',
]
CRITERIA += [
'GIS handover includes all 15 incoming coordinates and all still-active prior incidents with assignment/status; exclude completed A01 from active-only view or label clearly. Handle lat/lng versusGeoJSON lng/lat. Unassigned emergencies remain visible with unmet resources.',
'Depletion uses actual battalion membership and reconciled baseline/post-assignment freeunits, counting distinct physical units once. Battalion2 is E7,E8,T7,A18,M7,M8,BC2:7total,2maintenance,5initiallyfree=71.4286%;A19belongsBattalion3. Across58units CSV37free assumesE1confirmedavailable; E11CADcommitment removes1. E1unknown gives35-36effectivefree, not a forced privatecount. Identify zero freeSwiftWater and postdispatchHazMat/ALS gaps. Staged/requested resources are not free; linkedreports do not consume the sameunit twice.',
'Historical analysis uses full Kaggle Montgomery County PA dataset with 663,522rows,2015-12-10 through2020-07-29. Categories EMS332,692,Traffic230,208,Fire100,622; toprawtitle Traffic: VEHICLE ACCIDENT - has148,372. Report category / type rankings, peak hours/months and townshipclusters from actual counts, with missing townships/coordinate outliers. Strip trailing dash only as disclosed normalization. Counts/centroids are descriptive, not exposure-adjusted risk, and Pennsylvania patterns are not current DC geography or proof of optimal DC positioning.',
'Operational notes connect deviations, triage, scarcity, sharedresponses and release/reliefprerequisites to calls/resources. Conditionalplans and escalation are legitimate; no fabricated confirmations, hiddenpoint, mandatoryquestion, toolminimum or universal one unit per call rule. Allwork is simulated.'
]

def completion_rubrics(evidence):
 original=copy.deepcopy(load_task('JB29')[2])
 changes={
 (0,2):'Do not represent non-Swift Water units as fulfilling water-entry rescue. Shore/support while specialty is requested or safely redirected is legitimate with explicit limitations.',
 (2,0):'Actual Battalion2 membership:E7,E8,T7,A18,M7,M8,BC2. A19belongsBattalion3.',
 (2,1):'Two of seven Battalion2 units are maintenance-out, includingM7; baseline fivefree=71.4286%. Recompute post-assignment coverage from distinctunits;M8 is sole initiallyavailable localMedic.',
 (2,2):'Explain reduced coverage and actual postdispatch ALS/other depletion from source and assignmentstate.',
 (3,2):'Assign ALS for stroke or document scarcity/escalation/interim support. M4 is initially closest but a globally feasible alternative is valid ifM4 serves a competing urgent need.',
 (3,3):'A11 is BLS-only, notALS. BLSsupport/transport with explicit ALSrequest/escalation is distinct from pretending equivalent capability.',
 (4,0):'Analyze title frequencies from complete retrieved montcoalertCSV, with source scope/normalization.',
 (4,1):'Traffic: VEHICLE ACCIDENT - is raw most common148,372 of663,522; stripping trailing dash for display is acceptable.',
 (4,2):'Use historical findings as qualified retrospective context; MontgomeryCountyPA patterns are not directDC demand forecasts.',
 (5,1):'Treat unresponsive diabetic P1; assign available ALS or show scarcity, urgent aid request and interim support without double-booking medics.',
 (6,1):'Singleengine investigation whenavailable, or documented pending lowerpriorityresponse ifurgent callsconsume resources. E11needs release from laterCADcommitment;E1requires supported status.',
 (9,1):'Treat severeCOPD asP1 and assign ALS or explicitly document scarcity/escalation and interim response, never fictitious simultaneous availability.',
 (9,2):'A14 is BLS-only and cannotfulfillALS; interimBLS support while ALSrequested is allowed with limitations.'}
 for (r,c),s in changes.items():original[r]['criterion'][c]=s
 original[2]['rubric']='Does depletion use actual Battalion2 membership and postdispatch coverage?'
 original[4]['rubric']='Does full historical title analysis identify the most frequent type?'
 import re
 clean=lambda s:re.sub(r'(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])',' ',s)
 for row in original:row['criterion']=[clean(s) for s in row['criterion']]
 return original+[dict(rubric='Complete simulated dispatch, persisted state and historical analysis',weight=10,criterion=[clean(s) for s in CRITERIA]+['Selected source and submitted-state evidence: '+json.dumps(evidence)])]

def check(artifacts,private_root,variant='full',world=None,clarification_records=None,**config):
 private_root=Path(private_root);private_root.mkdir(parents=True,exist_ok=True);structure=structural_checks(artifacts,variant)
 if structure['status']!='pass':return dict(case='JB29',status='fail',structural=structure,original=dict(status='not_run'))
 evidence=build(variant,world,clarification_records);evidence['submitted_database']=structure['state'];(private_root/'source_evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
 source,path,rubrics=load_task('JB29');judge=OfficialJudge(path,private_root/'original_judge',**config)
 original=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,rubrics,judge)({},{})
 active=completion_rubrics(evidence);rp=private_root/'completion_rubrics.json';rp.write_text(json.dumps(dict(rubrics=active),indent=2)+'\n');other=OfficialJudge(rp,private_root/'completion_judge',**config)
 completion=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,active,other)({},{})
 return dict(case='JB29',status='pass' if completion.status=='passed' else 'fail',structural=structure,original=asdict(original),completion=asdict(completion),original_judge_run=str(judge.last_run),completion_judge_run=str(other.last_run),scope='Source calculations and separate original/active semantic judgments; no native replay')
