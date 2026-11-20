"""JB26 source-backed eligibility review; no predetermined count gate."""
from pathlib import Path
from dataclasses import asdict
import json,copy,importlib,sys
import openpyxl
from .jb26_evidence import build,PACKET
from .jobbench import load_task,OfficialJudge
from .native import artifact_hashes,JobBenchAcceptance

def structural_checks(artifacts):
 p=Path(artifacts);files=list(p.rglob('*'));wbs=[f for f in files if f.suffix=='.xlsx'];pdfs=[f for f in files if f.suffix=='.pdf'];checks=dict(workbook=bool(wbs),pdf=bool(pdfs));details={}
 if all(checks.values()):
  try:
   w=openpyxl.load_workbook(wbs[0],data_only=False);details['sheets']=w.sheetnames;checks['no_excel_errors']=not any(c.data_type=='e' for s in w for row in s for c in row);w.close()
   try:pdf=importlib.import_module('pymupdf')
   except ModuleNotFoundError:
    sys.path.append('/tmp/ea-bench-analysis-deps');pdf=importlib.import_module('pymupdf')
   with pdf.open(pdfs[0]) as d:details['pages']=len(d);checks['three_to_four_pages']=3<=len(d)<=4
  except Exception as exc:checks['readable']=False;details['error']=str(exc)
 return dict(status='pass' if all(checks.values()) else 'fail',checks=checks,details=details,artifact_hashes=artifact_hashes(p),scope='Formats and original page limit; substantive correctness separate')

CRITERIA=[
'Assess all 15 applications using supplied case rules and all source records. Workbook has three named sheets, determination-specific reasons, every nonapproval deficiency with RCW/WAC/Bulletin citation and correction, and a four-bulletin impact map comparing prior and current rules. PDF has the original title, 3-4 pages, category counts summing to 15 and matching workbook, one sentence for every HOLD, integrated high-risk profiles, every correspondence item and at least two case-grounded process improvements. No fixed APPROVE/DENY/HOLD totals apply.',
'Calculate bond gaps by specialty and effective date: RB001 increases Electrical/Plumbing/HVAC from12000 to20000; other trades remain12000. Summit6000 is deficient by6000, not approvable without correction. Review Emerald, Cascade Plumbing, Puget HVAC and NextGen for8000 application-row gaps. Sound Fencing correspondence changes filed12000 to6000 from February1; Lakewood cancellation January15 supersedes its old filing date. Verify effective and cancellation dates, do not assume unrelated bond-subset records belong to applicants.',
'Evaluate exam failure, missing financial statement, expired insurance at application, pending or flagged backgrounds and duplicate-principal identity separately. Cascade Plumbing must be denied for failed WA exam; Oregon credentials can evidence experience but neither transfer examination nor authorize provisional licensing. Rainier insurance expired October31 before January20 application. Olympic lacks financial statement; Evergreen background is pending. Henderson is a potential same-person/entity issue requiring verification or management review, not proof that two licenses are prohibited.',
'Apply RB002 independent carrier verification to relevant adverse-history files with attention to January15 effective date and pending applications. Field review of documents is not direct carrier confirmation. RB004 requires third-party experience evidence for Electrical/Plumbing/HVAC; NextGen has2 versus4 years and missing verification, while Oregon journeyman documentation for Cascade is relevant. Do not claim HVAC otherwise fully compliant without resolving experience evidence. Unknown insurance minimum must not be invented from unrelated public rows.',
]
CRITERIA += [
'Reconcile all violations/complaints and field findings: Emerald2500+5000 penalties are paid, so no continuing unpaid-violation hold; background and missing crew credential remain. Westside has20500 unpaid including10000 AG referral, plus4000 resolved; distinguish two OPEN-UNPAID cases from third AG-referred unpaid case. Complaint5006 investigation is CLOSED/referred, while5007 is OPEN: continuing enforcement/consumer harm is not identical to all complaints being open. Maintain justified Westside denial.',
'NextGen unlicensed finding November2,2024 falls within12 months of February1 application. RB003 starts February1 and imposes six calendar months from finding, ordinarily until May2,2025, subject only to manager written remediation waiver; do not start six months from application or silently waive. Analyze effective-date/retroactivity and filing-versus-review timing explicitly where uncertain. Correspondence printedJanuary30 contains February items and application batch extendsFebruary5: avoid declaring unseen attachments verified or using a pre-event review date without qualification.',
'Address all four correspondence items with actual disposition/follow-up. Olsen receipts/photos are absent; claimant name differs from Petrov at same property and aliases Tony/Anthony require linkage, so corroboration is not identity proof. Sound needs compliant replacement bond, Tanaka evidence ties complaint5008/inspection, and Lakewood cancellation needs replacement confirmation. Findings of photos_on_file do not mean the photos were supplied.',
'Cross-check public registration and insurance reference records using stable license IDs and carefully qualified identity matching. Cached subsets of1000 rows and no-match are not exhaustive verification or proof of absence. Current/future reference dates cannot establish Q1 historical coverage, nor substitute for direct carrier contact. Where checks cannot be completed, explicitly documented HOLD or provisional analysis is preferable to fabricated verification. Do not invent completed calls, registrations or insurance thresholds.',
'Redundant archive for prior-year application2024001 does not withdraw current2025001. Duplicate exam and bulletin extracts do not add events or supersede original policy. Compare identifiers, dates, disposition and authoritative values. Counterfactual discrepancies should be flagged, not silently change truth. No M/C worlds, mandatory questions, exact action sequence or extra reasoning transcript is required; tool/information minima are unproven.'
]

def completion_rubrics(evidence):
 original=copy.deepcopy(load_task('JB26')[2])
 original[1]['rubric']='Does Westside denial synthesize violations, unpaid/AG penalties, complaint statuses, correspondence, inspection and background?'
 original[1]['criterion'][2]='Reference complaint5006 (closed investigation with violation/AG referral) and5007 (open investigation), correspondenceItem1 and inspectionFI-2024-0887; distinguish unresolved enforcement from investigation status.'
 original[3]['criterion'][2]='Place one or both applications on HOLD pending verification, or flag the dual application for management review. Shared principal name is a possible identity link, not proof of identity or an automatic prohibition on separate business entities.'
 original[8]['rubric']='Does the response deny or hold Puget Sound HVAC for its RB001 bond gap while evaluating other applicable verification?'
 original[8]['criterion'][0]='Identify passed exam91, claimed18 years, clear background and filed financial statement, while assessing whether RB004 third-party experience verification is supplied.'
 original[8]['criterion'][2]='Do not approve until the20000 bond requirement is met; identify separately unresolved verification rather than assuming bond is the sole issue.'
 original[9]['criterion'][2]='Applications2025003,2025005,2025006,2025007,2025011 and2025012 require DENY or HOLD for unresolved deficiencies; handle2025015 consistently with the original duplicate-principal verification/management review alternatives.'
 original[9]['criterion'][3]='Every HOLD has a sentence rationale. Summit2025002 has6000 bond versus supplied12000 minimum, so cannot be approved absent correction. Green Valley/Cascade Earthworks and Pacific Northwest may be approved with adequate due diligence, or held for specific verification gaps. Henderson decisions must be consistent and explained.'
 import re
 extra=[re.sub(r'(?<=[a-z])(?=\d)|(?<=\d)(?=[a-zA-Z])',' ',x) for x in CRITERIA]
 return original+[dict(rubric='Complete source-based batch review and regulatory impact',weight=10,criterion=extra+['Actual sources and numeric controls: '+json.dumps(evidence)])]

def check(artifacts,private_root,variant='full',world=None,**config):
 private_root=Path(private_root);private_root.mkdir(parents=True,exist_ok=True);structure=structural_checks(artifacts)
 if structure['status']!='pass':return dict(case='JB26',status='fail',structural=structure,original=dict(status='not_run'))
 evidence=build(variant,world);(private_root/'source_evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
 source,path,rubrics=load_task('JB26');judge=OfficialJudge(path,private_root/'original_judge',**config)
 original=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,rubrics,judge)({},{})
 active=completion_rubrics(evidence);rp=private_root/'completion_rubrics.json';rp.write_text(json.dumps(dict(rubrics=active),indent=2)+'\n');other=OfficialJudge(rp,private_root/'completion_judge',**config)
 completion=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,active,other)({},{})
 return dict(case='JB26',status='pass' if completion.status=='passed' else 'fail',structural=structure,original=asdict(original),completion=asdict(completion),original_judge_run=str(judge.last_run),completion_judge_run=str(other.last_run),scope='Original diagnostic separate from active source-based eligibility judgment; no live public API/carrier verification claimed')
