"""Original rubric acceptance plus full original-task coverage omitted from rubric."""
from pathlib import Path
import json,sqlite3
from .jobbench import load_task,OfficialJudge
from .native import JobBenchAcceptance,artifact_hashes
EXTRA=[
 ('Database coverage and normalized identifiers',[
  'county_analysis.db is valid SQLite with separate county identifiers, current socioeconomic, historical change, health outcomes, demographic dynamics and exclusions tables, each indexed on county FIPS; identifiers include county/state identity, 2023 RUCC and economic typology.',
  'Health data contain all 15 supplied measures as numeric crude-prevalence columns, one row per eligible five-digit county FIPS, without tract or age-adjusted contamination or double-counting copies. Log incomplete joins in exclusions. Preserve supplied 2022 sleep and disclose the temporal difference.',
  'Source transformations and a consistent documented analytic cohort are reproducible; the notebook reads county_analysis.db rather than an unrelated dataset.'
 ]),
 ('Metro decomposition and outliers',[
  'The Metro Decomposition sheet reports metro/nonmetro obesity, diabetes and depression gaps using pooled Blinder-Oaxaca coefficients. Define groups and gap direction; explained plus unexplained equals observed gap, with reproducible computations.',
  'The Outlier Flag Sheet uses selected-model predictions and flags residuals strictly beyond two residual standard deviations. Include county FIPS, name, state, outcome, predicted value, observed value and residual, with reproducible flags.'
 ]),
 ('Competing models and mediation',[
  'Fit static socioeconomic-level models with RUCC controls and dynamic models adding socioeconomic changes and net migration for obesity, diabetes and depression. Compare nested fits on the same observations with correct likelihood-ratio tests and AIC/BIC; identify a best-fitting model per outcome.',
  'Compute poverty-to-inactivity-to-obesity mediation with a defined adjustment set and numerical indirect effect, bootstrap interval and reproducible resampling. Report direct and total associations or explain pathway size without claiming cross-sectional causal identification.'
 ]),
 ('Reproducible visualization and memo',[
  'Notebook code produces coefficient forests across specifications, selected-model state residual maps with diverging colors and a mediation diagram. Results agree across notebook, workbook and memo; images are not uncomputed placeholders.',
  'The actual 2–3 page PDF embeds at least three notebook figures, with substantive reconciliation findings, numerical tests, spatial interpretation, quantified mediation and interval, flagged-county patterns, ecological and temporal limitations and recommendations.'
 ])]
def numerical_rubric(reconciliation,evidence):
 return dict(rubric='Executed analysis and numerical reconciliation',weight=1,criterion=[
   'Require substantive computations in the successful fresh execution of reconciliation_models.ipynb. Host-computed source/reference evidence is validation, never submitted work. Verify database source values, cohort joins/exclusions and normalization; reconcile all three workbook sheets and quantitative PDF claims with actual executed calculations, matching outcome, model, cohort, units and method. A trivial notebook or copied constants cannot establish reproduction.',
   'Accept defensible alternative table/column labels, model fitting libraries, adjustment sets, model selection criteria, resampling and spatial weights conventions. Conditional reference uses unweighted OLS, categorical RUCC, LR p<.05 selection, sample residual SD and row-standardized queen weights; these are not hidden mandated decisions. Explain disagreements rather than requiring reference equality. Missing evidence for a required result is not a pass. Captured tables may be truncated for presentation; diagnostics compare full tables before truncation. Pandas capture is Python-specific; for other kernels reconcile substantive executed outputs and regenerated files without requiring pandas variable capture.',
   'Execution diagnostics: '+json.dumps(reconciliation,default=str),
   'Private numerical evidence: '+json.dumps(evidence,default=str)
  ])
def supplemental_rubric(private,reconciliation=None,evidence=None):
 import copy
 _,_,original=load_task('JB02')
 active=copy.deepcopy(original)
 active[7]['criterion'][2]=('Filter and pivot the 2019-23 bachelor-or-higher educational attainment attribute. '
   'Populate the 2023 RUCC county identifier from an applicable supplied USDA source, including the population file; '
   'the task does not require duplicating the same classification from the education file.')
 if reconciliation is not None:active.append(numerical_rubric(reconciliation,evidence))
 path=Path(private)/'task_completeness_rubrics.json' ;path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps({'rubrics':active+[dict(rubric=title,weight=1,criterion=criteria) for title,criteria in EXTRA]},indent=2)+'\n');return path
def check(artifacts,private_root,variant='full',world=None,run_judge=True,model=None,api_base=None):
 if variant not in {'full','R1','R2','R3'}:raise ValueError('Unsupported JB02 variant')
 artifacts,private=Path(artifacts),Path(private_root);private.mkdir(parents=True,exist_ok=True)
 before=artifact_hashes(artifacts);checks={'submitted_no_symlinks':not artifacts.is_symlink() and not any(p.is_symlink() for p in artifacts.rglob('*'))};required=['county_analysis.db','disparity_profile.xlsx','reconciliation_models.ipynb','reconciliation_memo.pdf']
 for name in required:checks[name]=(artifacts/name).is_file() and (artifacts/name).stat().st_size>0
 if all(checks.values()):
  import openpyxl,nbformat,fitz
  try:
   with sqlite3.connect('file:'+str((artifacts/'county_analysis.db').resolve())+'?mode=ro',uri=True) as db:checks['sqlite_integrity']=db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
   w=openpyxl.load_workbook(artifacts/'disparity_profile.xlsx',read_only=True,data_only=True);checks['workbook_three_sheets']=len(w.sheetnames)==3;w.close()
   nb=nbformat.read(artifacts/'reconciliation_models.ipynb',as_version=4);nbformat.validate(nb);checks['notebook_code']=any(c.cell_type=='code' and c.source.strip() for c in nb.cells)
   with fitz.open(artifacts/'reconciliation_memo.pdf') as pdf:checks['memo_2_to_3_pages']=2<=len(pdf)<=3
  except Exception as e:checks['readable_artifacts']=False;checks['error_type']=type(e).__name__
 reconciliation=None;evidence=None;infrastructure_error=None
 if all(checks[n] for n in required) and checks['submitted_no_symlinks'] and checks.get('readable_artifacts',True):
  from .jb02_reconciliation import build
  try:reconciliation,evidence=build(artifacts,private/'reconciliation',variant,world)
  except RuntimeError as exc:infrastructure_error=str(exc)
  checks['submitted_notebook_replayed']=bool(reconciliation and reconciliation['replay_passed'])

 result=dict(case='JB02' ,variant=variant,task_id='statisticians/task3',format_checks=checks,artifact_hashes=before,original_evaluator_runs=0,complete=False)
 if all(v is True for v in checks.values()) and run_judge:
  source,path,rubrics=load_task('JB02');judge=OfficialJudge(path,private/'original',model=model or __import__('os').environ.get('JUDGE_MODEL','gpt-5.5'),api_base=api_base);native=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,rubrics,judge)({},None)
  result['original']=dict(native.__dict__);result['original_evaluator_runs']=1
  extra=supplemental_rubric(private,reconciliation,evidence);rubrics=json.loads(extra.read_text())['rubrics'];judge=OfficialJudge(extra,private/'task_completeness',model=model or __import__('os').environ.get('JUDGE_MODEL','gpt-5.5'),api_base=api_base);supp=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,rubrics,judge)({},None)
  result['task_completeness']=dict(supp.__dict__);result['complete']=supp.status=='passed'
  result['original_rubric_comparability']='Original rubric independently reported; adapted complete-task rubric permits the valid supplied population RUCC source instead of requiring a duplicate education-source extraction.'
 if artifact_hashes(artifacts)!=before:raise RuntimeError('Artifacts changed during acceptance')
 result['reconciliation']=reconciliation
 result['numerical_checks']={} if reconciliation is None else dict(source_health_values_consistent=reconciliation['database']['source_health_values_consistent'],workbook_reproduction={item['sheet']:item['consistent'] for item in reconciliation['workbook_comparisons']})
 result['numerical_check_policy']='Conditional diagnostics require semantic adjudication of methods, units and labels. No local-only result is a complete acceptance.'
 result['status']='passed' if result['complete'] else ('unavailable' if not run_judge and all(v is True for v in checks.values()) else 'failed')
 if infrastructure_error or (reconciliation and reconciliation.get('infrastructure_error')):
  result['status']='infrastructure_error';result['infrastructure_error']=infrastructure_error or 'Submitted notebook requires an unavailable import; see preserved replay attempts'
 (private/'acceptance.json').write_text(json.dumps(result,indent=2,default=str)+'\n');return result
