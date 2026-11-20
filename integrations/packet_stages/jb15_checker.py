"""JB15 harmonization and complete statistical artifact checks."""
from pathlib import Path
from dataclasses import asdict
import json,sqlite3,zipfile,xml.etree.ElementTree as ET
from .jobbench import load_task,OfficialJudge
from .native import artifact_hashes,JobBenchAcceptance
ROOT=Path(__file__).resolve().parents[2];PACKET=ROOT/'data/expanded/JB15'
EXTRA=[dict(rubric='Auditable cleaning and full integrated statistical analysis',weight=1,criterion=[
'Cleaned SQLite preserves source record identifiers and documents every correction/exclusion. Resolve duplicate demographic joins without multiplying responses; flag personal conflicts and orphan/missing-country records. Invalid values and missingness are handled with justified rules, not unexplained imputation. Data-quality flags identify correction reasons.',
'Descriptive statistics give mean, sample SD and median by country and overall for Likert variables with valid n and stated missingness. Pearson matrix has actual coefficients, justified common or pairwise sample counts and defined variable encodings.',
'Two OLS models use the exact requested outcomes and full predictor sets, including macro controls. Report intercept, coefficients, standard errors, p-values, R-squared and model n; explain categorical encoding, sample exclusions and missing-value policy. Results must be computable from the delivered cleaned database, not placeholders or invented estimates.',
'Integrated benchmarks use disclosed threshold/denominator conversions for local Likert and categorical constructs, exact Meta/Yale codebook names and ESS values. Keep percent versus proportion units consistent, unavailable constructs/countries N/A and only construct-compatible differences interpretable.',
'Divergence flags include every absolute difference strictly greater than 15 percentage points with specific sampling/wording/time explanations. Treat this descriptive threshold separately from statistical significance; memo discusses three-source overlaps, construct limitations and manuscript recommendations.'])]
def structural_checks(artifacts,world=None,variant="full",clarification_records=None):
 import openpyxl
 root=Path(artifacts);details={};dbs=[];books=[];memos=[]
 from .jb15_judge_context import build
 import math
 context=build(PACKET,variant,clarification_records or [])
 metadata=context['verified_point_expectations'];columns=list(next(iter(metadata.values())))
 expected={country:[row[col] for col in columns] for country,row in metadata.items()}
 for p in root.rglob('harmonized_survey.db'):
  try:
   c=sqlite3.connect('file:'+str(p.resolve())+'?mode=ro',uri=True);tables={r[0] for r in c.execute("select name from sqlite_master where type='table'")}
   valid={'cleaned_responses','variable_crosswalk','country_metadata'}<=tables
   cols={r[1] for r in c.execute('pragma table_info(cleaned_responses)')};valid=valid and {'response_id','data_quality_flag'}<=cols
   count=c.execute('select count(*),count(distinct response_id) from cleaned_responses').fetchone();valid=valid and count[0]>0 and count[0]==count[1]
   actual={r[0]:list(r) for r in c.execute('select '+','.join(columns)+' from country_metadata')};macro_match=set(actual)==set(expected) and all(all(value is None or actual[country][index]==value for index,value in enumerate(row)) for country,row in expected.items())
   numeric_complete=all(all(isinstance(row[index],(int,float)) and math.isfinite(row[index]) for index,col in enumerate(columns) if col not in {'country','region'}) for row in actual.values())
   valid=valid and macro_match and numeric_complete
   valid=valid and c.execute('select count(*) from variable_crosswalk').fetchone()[0]>0 and c.execute('pragma integrity_check').fetchone()[0]=='ok'
   dbs.append(valid);details[p.name]=dict(cleaned_rows=count[0],unique_responses=count[1],macro_match=macro_match,numerical_indicators_complete=numeric_complete,unconfirmed_source_fields=context['unconfirmed_attributes']);c.close()
  except Exception as e:details[p.name]=dict(error=str(e))
 for p in root.rglob('cross_study_analysis.xlsx'):
  try:
   w=openpyxl.load_workbook(p,data_only=False);books.append({'Country_Benchmarks','Descriptive_Stats','Correlation_Matrix','Regression_Models','Divergence_Flags'}<=set(w.sheetnames));details[p.name]=dict(sheets=w.sheetnames)
  except Exception as e:details[p.name]=dict(error=str(e))
 for p in root.rglob('reconciliation_memo.docx'):
  try:
   with zipfile.ZipFile(p) as z:text=' '.join(ET.fromstring(z.read('word/document.xml')).itertext())
   memos.append(bool(text.strip()))
  except Exception as e:details[p.name]=dict(error=str(e))
 checks=dict(clean_sqlite_and_preserved_macro=any(dbs),required_analysis_sheets=any(books),readable_memo=any(memos))
 return dict(status='pass' if all(checks.values()) else 'fail',checks=checks,details=details,artifact_hashes=artifact_hashes(root),scope='SQLite integrity, unique IDs, numerical country coverage and equality only for sourced/confirmed macro points; unresolved verification and statistical semantics judged separately')
def check(artifacts,private_root,variant='full',world=None,clarification_records=None,**judge_config):
 private_root=Path(private_root);private_root.mkdir(parents=True,exist_ok=True)
 oracle=json.loads((PACKET/'private/oracle.json').read_text());assert variant in oracle['variants']
 records_path=private_root.parent/'user_records.json'
 records=clarification_records if clarification_records is not None else (json.loads(records_path.read_text()) if records_path.exists() else [])
 structure=structural_checks(artifacts,world,variant,records)
 if not structure['artifact_hashes']:return dict(case='JB15',status='failed',structural=structure,original=dict(status='not_run'))
 unknown=set(oracle['variants'][variant]['missing']+oracle['variants'][variant]['conflict'])
 if unknown-set(world or {}):raise ValueError('Explicit private world values required for unresolved variant facts')
 from .jb15_judge_context import build
 from .jb15_rubric_adaptation import adapt
 context=build(PACKET,variant,records)
 (private_root/'source_and_confirmation_context.json').write_text(json.dumps(context,indent=2)+'\n')
 extra=EXTRA+[dict(rubric='Verified macro inputs and duplicate evidence scope',weight=1,criterion=[
 'Retain every study country with verified numerical indicators. Preserve sourced/actually confirmed values and propagate verified US inputs into both requested regressions. Unconfirmed fields require determining evidence, not a lucky private-point match or undocumented imputation. No question wording/count is imposed. Private evaluator context, not requested output: '+json.dumps(context),
 'Copies corroborate rather than add rows. Missing-country/orphan records must not acquire invented countries. Conflicting demographics need flags and documented handling.'])]
 from .jb15_artifact_evidence import prepare
 from .jb15_statistics import RECONCILIATION_RUBRIC
 original_input,authored_input,derived=prepare(artifacts,private_root,variant);extra.append(RECONCILIATION_RUBRIC)
 source,path,rubrics=load_task('JB15');active,map_record=adapt(rubrics,context);active+=extra
 (private_root/'rubric_adaptation.json').write_text(json.dumps(map_record,indent=2)+'\n')
 native_judge=OfficialJudge(path,private_root/'original_judge',**judge_config)
 native=JobBenchAcceptance(source['original_id'],source['original_id'],original_input,rubrics,native_judge)({},{})
 extra_file=private_root/'authored_completion_rubrics.json';extra_file.write_text(json.dumps(dict(rubrics=active),indent=2)+'\n');judge=OfficialJudge(extra_file,private_root/'completion_judge',**judge_config)
 completion=JobBenchAcceptance(source['original_id'],source['original_id'],authored_input,active,judge)({},{})
 passed=structure['status']=='pass' and completion.status=='passed'
 return dict(case='JB15',derived_sqlite_evidence=str(private_root/'derived_sqlite_evidence.json'),source_artifacts_unchanged=derived['source_artifacts_unchanged'],original_diagnostic_only=True,status='passed' if passed else 'failed',structural=structure,original=asdict(native),completion=dict(asdict(completion),layer='adapted_original_and_authored'),adaptation=map_record,original_judge_run=str(native_judge.last_run),completion_judge_run=str(judge.last_run),scope='Full-row/statistical evidence retained. All six original groups remain in the active gate; only US metadata clauses are adapted. Unchanged original rubric is a separate diagnostic.')
