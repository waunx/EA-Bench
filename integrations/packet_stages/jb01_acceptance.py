"""Full artifact gate; historical 2021 and adapted 2023 results stay separate."""
from pathlib import Path
import json
from .jobbench import load_task, OfficialJudge
from .native import JobBenchAcceptance, artifact_hashes
RUBRICS = [
 ('Primary cohort and provenance', [
  'Use supplied 2023 total-adult state obesity estimates. Exclude county/tract rows, subgroup estimates and territories. Harmonize identifiers and avoid duplicate joins.',
  'Retain jurisdictions having supplied outcome, 2023 exposure and education; resolve incomplete/conflicting authored point estimates with confirmed values below instead of dropping jurisdictions or replacing authored values with an external vintage.',
  'Use USDA 2023 overall poverty, household income and annual unemployment, the December 2021 CDC vaccination snapshot and Census region assignments. Document provenance, absent source/year records and remaining outcome/education vintage limitations. Do not substitute another obesity year.'
 ]),
 ('Reproducible statistical analysis', [
  'An executable notebook connects supplied sources to delivered results with processing/cohort decisions and confirmed point estimates documented sufficiently for reproduction.',
  'Compare obesity-only and socioeconomic-adjusted models including poverty, education, income and unemployment. Report numerical coefficients, uncertainty and model fit; compare standardized predictor effects on appropriate scales.',
  'Evaluate clustering within the four Census regions with a statistically defensible method. Explain the method and numerical result without unwarranted causal interpretation.'
 ]),
 ('Workbook', [
  'An Excel workbook contains the required Clean_Data, Descriptive_Stats, Correlation_Matrix, Model_Comparison and Sensitivity sheets with substantive merged records, summaries, correlations, model comparisons and sensitivity results.',
  'Clean cohort and confirmed point estimates agree with the private factual audit. Workbook values agree with notebook computations and memo claims; no fabricated data or uncomputed placeholders.'
 ]),
 ('Sensitivity and memo', [
  'Calculate leverage or a justified influence diagnostic and compare the adjusted obesity coefficient and uncertainty before/after high-leverage observation removal. Document the criterion, affected states and stability conclusion.',
  'A 2–3 page technical memo directly answers whether obesity is the primary driver with bivariate/adjusted and standardized comparisons and sensitivity results. Include a causal diagram, ecological and temporal limitations and an actionable qualified policy recommendation.'
 ])]

def rubric_file(private, variant, world, reconciliation=None, numerical_evidence=None):
 import copy
 from .author_english_jb01 import PACKET, REFERENCE_ROOT
 from .jb01_analysis import prepare
 clean, quality = prepare(PACKET/'variants'/variant/'inputs', REFERENCE_ROOT, world or {})
 rows=copy.deepcopy(RUBRICS)
 audit=dict(primary_year=2023,states=clean.state.tolist(),excluded=quality['excluded_outcome_states'],Alabama=clean[clean.state.eq('Alabama')][['life','obesity','education','poverty','income','unemployment']].to_dict('records')[0])
 rows[0][1].append('Private factual audit, never shown to the agent: '+json.dumps(audit)+'. Accept equivalent labels and defensible methods; do not require reference-specific filenames or code.')
 if reconciliation is not None:
  rows.append(('Executed notebook and cross-artifact numerical reconciliation', [
   'Identify the primary analysis notebook(s) by submitted filename from the execution records. Require the substantive computations to occur in successful replays, with matching source_notebook provenance on captured tables or rebuilt workbook records. A trivial successful helper never rescues a failed primary analysis notebook. A helper may fail alone if its necessary code was executed successfully within the primary notebook; explain this distinction using the records. Missing provenance or failure of the substantive computation is a failure of this rubric.',
   'Mandatory host evidence follows. Do not credit host-created evidence as work submitted by the agent. Verify substantive notebook computations reproduce the delivered Clean_Data, descriptive statistics, correlations, model estimates/uncertainty/standardized effects, regional analysis and sensitivity. Reconcile memo quantitative claims with corresponding notebook/workbook results. Merely matching numbers somewhere in a table is insufficient; match variables, cohorts, units, models and method. No fixed filenames, workbook layout, internal variable names, model fitting library, or specific regional/sensitivity method is required.',
   'The reference analysis is conditional on its unweighted OLS, region fixed-effect and top-three-leverage choices. Accept statistically defensible alternatives if independently consistent with source data and all required comparisons. Notebook calculations may be stored in captured tables or displayed outputs without exporting a workbook. Reject fabricated or contradictory numbers and uncomputed placeholders. Every required numerical component must be supported; uncertainty about missing evidence is not a pass.',
   'Execution and conditional matching diagnostics: '+json.dumps(reconciliation,default=str),
   'Complete source-grounded numeric evidence (not suggested output): '+json.dumps(numerical_evidence,default=str)
  ]))
 path=Path(private)/'adapted_2023_rubrics.json'
 path.write_text(json.dumps({'rubrics':[dict(rubric=t,weight=1,criterion=c) for t,c in rows]},indent=2)+'\n')
 return path

def check(artifacts, private_root, variant='full', world=None, run_judge=True, model=None, api_base=None):
 artifacts,private=Path(artifacts),Path(private_root);private.mkdir(parents=True,exist_ok=True)
 if artifacts.is_symlink() or any(p.is_symlink() for p in artifacts.rglob('*')):
  result=dict(case='JB01',variant=variant,status='failed',complete=False,format_checks={'submitted_no_symlinks':False},artifact_hashes={},original_evaluator_runs=0,adapted_evaluator_runs=0,validation_layer='submitted_artifact_safety')
  (private/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');return result
 before=artifact_hashes(artifacts)
 books=list(artifacts.rglob('*.xlsx')); notebooks=list(artifacts.rglob('*.ipynb')); memos=list(artifacts.rglob('*.pdf'))
 checks=dict(workbook_present=bool(books),notebook_present=bool(notebooks),memo_present=bool(memos))
 if all(checks.values()):
  import openpyxl,nbformat,fitz
  try:
   valid_books=[]
   for p in books:
    w=openpyxl.load_workbook(p,read_only=True,data_only=True)
    valid_books.append({'Clean_Data','Descriptive_Stats','Correlation_Matrix','Model_Comparison','Sensitivity'}.issubset(w.sheetnames) and all(w[n].max_row>1 for n in ['Clean_Data','Descriptive_Stats','Correlation_Matrix','Model_Comparison','Sensitivity']));w.close()
   checks['five_substantive_sheets']=any(valid_books)
   for p in notebooks:
    nb=nbformat.read(p,as_version=4);nbformat.validate(nb)
   checks['notebook_has_code']=any(any(c.cell_type=='code' and c.source.strip() for c in nbformat.read(p,as_version=4).cells) for p in notebooks)
   pages=[]
   for p in memos:
    with fitz.open(p) as pdf:pages.append(len(pdf))
   checks['memo_2_to_3_pages']=any(2<=n<=3 for n in pages)
  except Exception as exc:
   checks['readable_artifacts']=False
   (private/'format_error.txt').write_text(type(exc).__name__+': '+str(exc))
 reconciliation=None;numerical_evidence=None
 if books and notebooks and memos and checks.get('readable_artifacts',True):
  from .jb01_reconciliation import build
  reconciliation,numerical_evidence=build(artifacts,private/'reconciliation',variant,world)
  checks['candidate_notebook_replayed']=reconciliation['replay_passed']
  if reconciliation['labeled_numeric_reproduction'] is not None:
   checks['labeled_numeric_reproduction']=reconciliation['labeled_numeric_reproduction']
 result=dict(case='JB01',variant=variant,format_checks=checks,artifact_hashes=before,original_evaluator_runs=0,adapted_evaluator_runs=0,complete=False,
  validation_layer='authored_2023_full_artifact',original_rubric_compatibility='Unchanged original 2021 criteria are historical comparison only, not an acceptance gate for the explicitly authored 2023 primary cohort.')
 if run_judge and all(checks.values()):
  source,path,rubrics=load_task('JB01')
  def judge_file(path,rubrics,name):
   judge=OfficialJudge(path,private/name,model=model or __import__('os').environ.get('JUDGE_MODEL','gpt-5.5'),api_base=api_base)
   return JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,rubrics,judge)({},None)
  original=judge_file(path,rubrics,'original_2021');result['original']=dict(original.__dict__);result['original_evaluator_runs']=1
  from .jb01_reconciliation import verify_references
  verify_references(variant)
  path=rubric_file(private,variant,world,reconciliation,numerical_evidence);adapted=judge_file(path,json.loads(path.read_text())['rubrics'],'adapted_2023')
  result['adapted']=dict(adapted.__dict__,layer='authored_2023_full_artifact');result['adapted_evaluator_runs']=1
  result['complete']=all(checks.values()) and adapted.status=='passed'
 if artifact_hashes(artifacts)!=before:raise RuntimeError('Artifacts changed during acceptance')
 result['reconciliation']=reconciliation
 result['status']='passed' if result['complete'] else ('unavailable' if not run_judge and all(checks.values()) else 'failed')
 (private/'acceptance.json').write_text(json.dumps(result,indent=2,default=str)+'\n');return result
