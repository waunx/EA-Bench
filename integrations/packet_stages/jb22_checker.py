"""JB22 source-aware statistical artifact gate, distinct from unchanged original diagnostics."""
from pathlib import Path
from dataclasses import asdict
import json,shutil,hashlib
import openpyxl
from .jobbench import load_task,OfficialJudge
from .native import artifact_hashes,JobBenchAcceptance
ROOT=Path(__file__).resolve().parents[2];PACKET=ROOT/'data/expanded/JB22'
FILES=['Eligibility_Analysis.xlsx','Sample_Size_Justification.xlsx','Baseline_Subgroup_Analysis.xlsx']
EXTRA=[dict(rubric='Auditable fixed and sequential design justification',weight=1,criterion=[
'Primary fixed-design calculation states sourced/confirmed inputs or clearly conditional assumptions, equal allocation, two-sided test, formula/method and per-arm versus total counts. Empirical recalculation preserves the 5-percentage-point absolute difference with matching alpha/power; do not silently convert it to a fixed relative reduction.',
'Explain integer rounding and dropout inflation separately from sequential inflation. The calculator uses its unrounded result before dropout; conservative ceiling-first rounding is also acceptable if transparent. Do not reject a result only for807 versus808 under these declared conventions.',
'Implement the planned OBrien-Fleming spending approach at information fractions 0.5 and 0.75 plus final 1.0. Document spending/boundaries and overall Type I error, target power, maximum sample size and dropout assumptions. An arbitrary inflation percentage or a mention of interim analysis is insufficient; coherent validated alternatives require explicit justification.',
'Cross-validate fixed-design results against the supplied Wan Nor Arifin Proportion C1 worksheet, recording inputs/output comparison and explaining differences. Do not claim that this fixed-design calculator validates group-sequential inflation.'])]
EXTRA += [dict(rubric='Empirical and regulatory interpretation',weight=1,criterion=[
'Eligibility uses only observable age, sysBP, stroke and diabetes fields, with explicit CKD/broader prior-CVD limitations; do not filter on future TenYearCHD outcome. Assess uncertainty and external validity of the 217/1108 empirical estimate.',
'Distinguish cohort 10-year CHD from the proposed composite endpoint and trial follow-up horizon. Use empirical data to examine assumptions, not automatically replace protocol rates or assert causal drug efficacy. Cite relevant actual ICH E9 sections 3.4/3.5 and pre-specification, sensitivity and integrity principles; do not invent guidance.',
'E9 Section 5.7 supports careful subgroup interpretation, not a universal n = 30 threshold. Explicitly report whether the chosen strata cross the pragmatic screen and consider event counts/precision. Observational risk heterogeneity is not demonstrated treatment-effect modification.'])]
EXTRA += [dict(rubric='Complete subgroup and eligible-population missing-data evidence',weight=1,criterion=[
'Provide counts, events and rates plus variable-specific n, mean and sample SD of sysBP/totChol/BMI for every age, sex, smoking and risk-tertile stratum. Describe risk-score formula or justified Framingham approximation, missing predictor handling and tie/cutpoint rules; arbitrary unexplained scores or omitted risk tertiles are insufficient.',
'Use the eligible 1108 denominator for missingness, including 103 missing glucose values. Quantify outcome association using an appropriate documented method and underlying counts; the reference table is 19 events/84 nonevents among missing versus 198/807 observed. A nonsignificant test does not prove MCAR or MAR.',
'Recommend an appropriate handling and sensitivity strategy, distinguishing protocol MAR multiple imputation from empirically proven missingness mechanisms. All three workbooks must agree on populations, design parameters and reported totals.'])]

def structural_checks(artifacts):
 root=Path(artifacts);checks={};details={}
 for name in FILES:
  matches=list(root.rglob(name))
  p=matches[0] if len(matches)==1 else root/name
  try:
   if len(matches)!=1:raise ValueError('Expected exactly one workbook with this filename')
   book=openpyxl.load_workbook(p,data_only=False);nonempty=any(c.value is not None for sheet in book for row in sheet for c in row)
   checks[name]=bool(book.sheetnames) and nonempty;details[name]=dict(sheets=book.sheetnames);book.close()
  except Exception as exc:checks[name]=False;details[name]=dict(error=type(exc).__name__+': '+str(exc))
 return dict(status='pass' if all(checks.values()) else 'fail',checks=checks,details=details,artifact_hashes=artifact_hashes(root),scope='Three readable nonempty workbook files only; content and calculations require semantic/source checks.')

def check(artifacts,private_root,variant='full',world=None,clarification_records=None,**judge_config):
 from copy import deepcopy
 from .jb22_judge_context import build
 from .jb22_rubric_adaptation import adapt
 private_root=Path(private_root);private_root.mkdir(parents=True,exist_ok=True);structure=structural_checks(artifacts)
 if not structure['artifact_hashes']:return dict(case='JB22',status='failed',structural=structure,original=dict(status='not_run'))
 oracle=json.loads((PACKET/'private/oracle.json').read_text());assert variant in oracle['variants']
 unknown=set(oracle['variants'][variant]['missing']+oracle['variants'][variant]['conflict'])
 if unknown-set(world or {}):raise ValueError('Explicit private world values required for unresolved protocol facts')
 records_path=private_root.parent/'user_records.json';records=clarification_records if clarification_records is not None else (json.loads(records_path.read_text()) if records_path.exists() else [])
 protocol=build(PACKET,variant,records);validation=PACKET/'private/numerical-validation-20261012';report=json.loads((validation/'result.json').read_text())
 assert report['status']=='pass' and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in report['source_hashes'].items())
 assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in report['implementation_hashes'].items())
 references=json.loads((validation/'references.json').read_text());context=dict(protocol=protocol,numerical_references=references)
 (private_root/'source_and_confirmation_context.json').write_text(json.dumps(context,indent=2)+'\n')
 source,path,rubrics=load_task('JB22');active,adaptation=adapt(rubrics,protocol);extra=deepcopy(EXTRA)
 extra[0]['rubric']+=' Private numerical controls, not submitted work or selected protocol truth: '+json.dumps({k:references[k] for k in ['conditional_design_grid','canonical_sequential_controls','calculator','scope']})
 extra[1]['rubric']+=' Private public-source excerpts, not submitted citations: '+json.dumps(references['regulatory_excerpts'])
 extra[2]['rubric']+=' Private cohort controls, not submitted analysis: '+json.dumps(references['cohort'])
 active+=extra
 (private_root/'rubric_adaptation.json').write_text(json.dumps(adaptation,indent=2)+'\n')
 original_judge=OfficialJudge(path,private_root/'original_judge',**judge_config)
 original=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,rubrics,original_judge)({},{})
 active_file=private_root/'active_rubrics.json';active_file.write_text(json.dumps(dict(rubrics=active),indent=2)+'\n');judge=OfficialJudge(active_file,private_root/'completion_judge',**judge_config)
 completion=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,active,judge)({},{})
 passed=structure['status']=='pass' and completion.status=='passed'
 return dict(case='JB22',status='passed' if passed else 'failed',structural=structure,original_diagnostic_only=True,original=asdict(original),completion=dict(asdict(completion),layer='adapted_original_and_authored'),original_judge_run=str(original_judge.last_run),completion_judge_run=str(judge.last_run),adaptation=adaptation,scope='Unchanged original diagnostic separate. Blocking gate retains all eight original groups with a narrow grid-count/header adaptation and source-aware statistical/regulatory checks. No native environment replay claimed.')
