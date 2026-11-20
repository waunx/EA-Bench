"""Evidence-aware workforce artifact acceptance and unchanged historical judge."""
from pathlib import Path
from dataclasses import asdict
import json,zipfile,xml.etree.ElementTree as ET
from .jobbench import load_task,OfficialJudge
from .native import JobBenchAcceptance,artifact_hashes
from .jb11_judge_context import build
EXTRA=[
 dict(rubric='Executive workforce findings and compensation equity',weight=1,criterion=[
  'Workforce_Planning_Report.docx has an executive summary with three prioritized evidence-backed findings; compensation equity table compares correctly annualized departed mean or median income consistently across relevant roles against current employer bands, with gaps and coverage caveats. Do not confuse MonthlyRate or DailyRate with MonthlyIncome, or claim employer bands establish independent market competitiveness.',
  'Calculate role-specific turnover rates using employees in each role as denominators. Identify Sales Representative high attrition, investigate root causes and prioritize Laboratory Technician and Research Scientist hiring using actual open positions and priorities, not by converting departures to vacancies. If no acceptable policy threshold is supplied, say so and distinguish analytical flags from approved policy.'
 ]),
 dict(rubric='Overtime and strategic planning',weight=1,criterion=[
  'Compare overtime and non-overtime attrition denominators/rates at company and relevant role levels, including Laboratory Technician and Research Scientist. Use visible source facts or actual confirmations; preserve uncertainty in affected denominators and rates. Interpret the association without claiming the observational data establish causality.',
  'Provide actionable compensation and non-compensation workforce recommendations tied to findings, priorities, open roles, workload/overtime, retention and hiring constraints, with a practicable follow-up plan.'
 ]),
 dict(rubric='Complete applicant screening',weight=1,criterion=[
  'The Word report and Applicant_Screening_Results.xlsx cover every current-cycle applicant with position-specific education level and field, experience, required skills, license requirements and salary alignment, plus a reasoned recommendation. Preferred credentials must not silently become mandatory. Accept defensible semantic skill matches, not just literal keyword matching.',
  'Qualification, salary gaps and counts agree across report/workbook and with source-supported facts. Above-band salary should be transparent; do not invent salary commitments. For unconfirmed facts, accept explicit pending findings or conditional analyses that quantify material effects and explain corresponding recommendations; do not require a hidden point value or any specific question. A detail that cannot change the recommendation may remain explicitly pending rather than being invented.'
 ]),
 dict(rubric='Verification and workbook completeness',weight=1,criterion=[
  'The workbook contains the full qualification matrix, meaningful summary statistics and a candidate license-verification follow-up tracking sheet. Recommendations distinguish hard requirement failures, pending verification and salary negotiations; summaries reconcile with all applicants.',
  'Applicant-reported Active status is not independent verification. Required licenses need suitable verification actions; match candidate, license type, issuing authority and date before applying a registry record. Do not treat A001 unrelated Medical Technologist record as Professional License evidence. Do not include prior-cycle applicants or peer-company staff in current scoped totals.'
 ])]
def authored_rubrics(context):
 import copy
 extra=copy.deepcopy(EXTRA)
 extra.append(dict(rubric='Private factual consistency audit',weight=1,criterion=['Compare artifact numbers and candidate requirements to this evidence-aware source context: '+json.dumps(context)+'. No selected hidden world is provided. Accept sensible rounding, equivalent labels and explicit conditional results with quantified material effects and corresponding recommendations. The context license_gate is applicant-reported eligibility, NOT proof of verification.']))
 # Each rubric is judged independently; sibling rubric evidence is not shared.
 for rubric in extra[:-1]:
  rubric['criterion'].append('Private evaluator context for this criterion, not required output text: '+json.dumps(context))
 return extra

def check(artifacts,private_root,variant='full',world=None,run_judge=True,clarification_records=None,**judge_config):
 import openpyxl,copy
 artifacts,private_root=Path(artifacts),Path(private_root);private_root.mkdir(parents=True,exist_ok=True);before=artifact_hashes(artifacts)
 records_path=private_root.parent/'user_records.json'
 records=clarification_records if clarification_records is not None else (json.loads(records_path.read_text()) if records_path.exists() else [])
 context=build(variant,records)
 (private_root/'evidence_context.json').write_text(json.dumps(context,indent=2)+'\n')
 doc=artifacts/'Workforce_Planning_Report.docx';book=artifacts/'Applicant_Screening_Results.xlsx';checks=dict(report_present=doc.is_file(),workbook_present=book.is_file())
 try:
  if checks['report_present']:
   with zipfile.ZipFile(doc) as z:text=' '.join(ET.fromstring(z.read('word/document.xml')).itertext())
   checks['report_has_content']=bool(text.strip())
  if checks['workbook_present']:
   w=openpyxl.load_workbook(book,read_only=True,data_only=False);checks['workbook_readable']=bool(w.sheetnames)
   matrix_coverage=[]
   for sheet in w:
    cells=' '.join(str(c) for row in sheet.values for c in row if c is not None).lower()
    matrix_coverage.append(all(name.lower() in cells or possibilities[0]['name'].lower() in cells for name,possibilities in context['applicant_possibilities'].items()))
   checks['all_current_applicants_on_a_matrix_sheet']=any(matrix_coverage);w.close()
 except Exception as exc:
  checks['readable_artifacts']=False;(private_root/'format_error.txt').write_text(str(exc))
 result=dict(case='JB11',variant=variant,status='failed',format_checks=checks,artifact_hashes=before,original_evaluator_runs=0,native_environment_replays=0,original_rubric_judge_runs=0,adapted_evaluator_runs=0,complete=False,
  scope='Full evidence-aware authored artifact gate. Original numerical rubrics remain separate historical scores: allowed alternatives change departed-income means and salary bands.')
 if run_judge and all(checks.values()):
  source,path,rubrics=load_task('JB11');original_judge=OfficialJudge(path,private_root/'original',**judge_config)
  original=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,rubrics,original_judge)({},None);result['original']=asdict(original);result['original_rubric_judge_runs']=1
  extra=authored_rubrics(context)
  path=private_root/'adapted_rubrics.json';path.write_text(json.dumps(dict(rubrics=extra),indent=2)+'\n')
  judge=OfficialJudge(path,private_root/'adapted',**judge_config);adapted=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,extra,judge)({},None)
  result['adapted']=dict(asdict(adapted),layer='authored_evidence_aware_full_artifact');result['adapted_evaluator_runs']=1;result['complete']=adapted.status=='passed'
 if artifact_hashes(artifacts)!=before:raise RuntimeError('Submitted artifacts changed during checking')
 result['status']='passed' if result['complete'] else ('unavailable' if not run_judge and all(checks.values()) else 'failed')
 (private_root/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');return result
