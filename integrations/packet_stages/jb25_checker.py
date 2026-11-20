"""Complete LEEC dispute grading; unchanged original diagnostic is separate."""
import copy,json,zipfile
from pathlib import Path
from dataclasses import asdict
import openpyxl
from .jb25_evidence import evidence
from .jobbench import load_task,OfficialJudge
from .native import artifact_hashes,JobBenchAcceptance
SHEETS={'Cross-Source Validation','Weather-Usage Correlation','Regulatory Compliance Check','Resolution Matrix'}

def structural_checks(artifacts):
 root=Path(artifacts);books=list(root.rglob('Dispute_Investigation_Workbook.xlsx'));letters=list(root.rglob('Customer_Response_Letters.docx'));pdfs=list(root.rglob('January2025_Dispute_Briefing.pdf'));checks={'named_workbook':bool(books),'named_letters':bool(letters),'named_brief':bool(pdfs)}
 valid=[]
 for f in books:
  try:
   w=openpyxl.load_workbook(f,read_only=True);valid.append(SHEETS<=set(w.sheetnames));w.close()
  except Exception:valid.append(False)
 checks['four_required_sheets']=any(valid)
 checks['letters_docx_container']=any(zipfile.is_zipfile(f) for f in letters)
 checks['brief_pdf_header']=any(f.read_bytes().startswith(b'%PDF-') for f in pdfs)
 return dict(status='pass' if all(checks.values()) else 'fail',checks=checks,artifact_hashes=artifact_hashes(root),scope='Format only; six-case content and calculations checked semantically')

def active_original(original):
 r=copy.deepcopy(original)
 r[1]['criterion'][0]='Flag the Budget Billing concern using recorded January charges445.65 for2364kWh, customer statement and disputed balance. Total_Bill may be actual charges rather than the level payment due; verify the actual payment schedule before asserting a program failure.'
 r[5]['criterion'][0]='Address Patricia Nguyen\'s Budget Billing concern and distinguish recorded January charges445.65, disputed balance523.89 and the level payment due, which is not established by a total-charge column alone.'
 r[5]['criterion'][1]='Explain plausible true-up, plan adjustment/termination or statement-presentation possibilities and the verification steps, without claiming an unverified cause.'
 r[6]['criterion'][4]='Identify DSP-4004 as highest regulatory priority from the earliest deadline and low-income vulnerability, while verifying winter-protection eligibility rather than claiming an unconditional blanket ban.'
 r[7]['criterion'][2]='Flag a potential Budget Billing process or presentation issue for DSP-4003; verify the level-payment, true-up and account-status evidence before concluding the program failed.'
 r[9]['criterion'][3]='Explain the contribution of recorded usage and unit rates/fees to high bills. Low energy-only rates versus an all-in statewide benchmark do not alone prove tariff compliance or absence of a meter problem.'
 return r

EXTRA=[
'Complete all four named workbook sheets, six individualized letters and the PDF briefing. Cross-Source Validation has a clear record for each of the six disputes; amounts, plan, heating, history, supervisor claims and resolution are consistent across deliverables.',
'Compute January and Oct-Dec aggregate HDD from the matching KERI observations, and each customer\'s corresponding kWh/HDD ratios and change. Do not divide a monthly average by a three-month HDD sum. A clearly justified alternate baseline convention must use matched periods and consistent units. Do not double-count copied station/day observations or blend another station.',
'Use actual2024 EIA Pennsylvania rows for every customer, with explicit price/bill scope and units. Distinguish disputed balances from January charges. Benchmarks do not prove tariff compliance.',
'Apply actual cited PA PUC billing, budget-billing, dispute/escalation and winter provisions with source-applicability limits. Do not invent a state senior-discount mandate or unconditional winter immunity; distinguish disputed and undisputed amounts.',
'Calculate each deadline from a declared reporting date and business-day/holiday convention. Flag weekend dates and overdue deadlines; do not impose a hidden as-of date or equate calendar deadlines with30 business days.',
'Use the four permitted resolution labels with source-supported case-specific justifications. Weather normalization does not prove meter accuracy, extra heaters or fraud; monthly totals cannot verify daily outage gaps. Verify level-payment/true-up, CAP, cross-metering and utility discount facts before asserting causes or approvals.',
'All six letters must explain their own account, dispute, usage/bill, weather and next steps consistently with the workbook. Briefing ranks all six using deadlines, vulnerability and exposure, distinguishes confirmed errors from hypotheses, and gives2-3 evidence-grounded systemic recommendations.'
]

def check(artifacts,private_root,variant='full',world=None,**config):
 root=Path(private_root);root.mkdir(parents=True,exist_ok=True);structure=structural_checks(artifacts)
 if structure['status']!='pass':return dict(case='JB25',variant=variant,status='fail',structural=structure,original={'status':'not_run'},completion={'status':'not_run'})
 context=evidence(variant);(root/'source_evidence.json').write_text(json.dumps(context,indent=2,default=str)+'\n')
 source,path,original=load_task('JB25');active=active_original(original)
 active.append(dict(rubric='Complete six-dispute source reconciliation and defensible decisions',weight=1,criterion=EXTRA+['Private source controls; not mandatory copied output: '+json.dumps(context,default=str)]))
 j=OfficialJudge(path,root/'original_judge',**config)
 native=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,original,j)({},{})
 rp=root/'active_rubrics.json';rp.write_text(json.dumps(dict(rubrics=active),indent=2)+'\n')
 aj=OfficialJudge(rp,root/'active_judge',**config)
 verdict=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,active,aj)({},{})
 return dict(case='JB25',variant=variant,status='pass' if verdict.status=='passed' else 'fail',structural=structure,original=asdict(native),completion=asdict(verdict),original_judge_run=str(j.last_run),completion_judge_run=str(aj.last_run),scope='Separate original diagnostic and source-grounded compatible-original/business judgment; no native replay')
