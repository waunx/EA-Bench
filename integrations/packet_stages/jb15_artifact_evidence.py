"""Full-row serialization and analysis references; never repairs submissions."""
from pathlib import Path
import json,sqlite3,shutil,copy
from .native import artifact_hashes
from .jb15_statistics import evidence,table

def prepare(artifacts,private_root,source_variant="full"):
 source=Path(artifacts);root=Path(private_root)
 original=root/'full_sqlite_evidence_input'
 shutil.copytree(source,original)
 before=artifact_hashes(source);records=[];analyses=[]
 for index,path in enumerate(sorted(source.rglob('harmonized_survey.db'))):
  try:
   con=sqlite3.connect('file:'+str(path.resolve())+'?mode=ro',uri=True)
   names=[r[0] for r in con.execute("select name from sqlite_master where type='table'")]
   for n,name in enumerate(names):
    rows=table(con,name)
    for chunk,start in enumerate(range(0,len(rows),100)):
     target=original/('_host_sqlite_%s_%s_%s.json'%(index,n,chunk))
     target.write_text(json.dumps(dict(host_derived=True,source=str(path.relative_to(source)),table=name,start_row=start,total_rows=len(rows),rows=rows[start:start+100]),separators=(',',':'))+'\n')
    records.append(dict(source=str(path.relative_to(source)),table=name,rows=len(rows)))
   con.close();analysis=evidence(path);analysis.pop('full_cleaned_rows',None)
   source_db=Path(__file__).resolve().parents[2]/'data/expanded/JB15/variants'/source_variant/'inputs/climate_policy_survey_raw.db'
   analysis['cleaning_audit']=cleaning_audit(path,source_db);analyses.append(analysis)
  except Exception as exc:analyses.append(dict(source=str(path.relative_to(source)),status='unavailable',error=type(exc).__name__+': '+str(exc)))
 (original/'_HOST_SQLITE_NOTICE.txt').write_text('Evaluator-provided files named _host_sqlite are complete row serializations of submitted SQLite tables, not extra solver deliverables. They address the original reader limit of 500 rows per table; they contain no corrected values.\n')
 authored=root/'statistical_evidence_input';shutil.copytree(original,authored)
 public_references(authored,source_variant)
 displayed=copy.deepcopy(analyses)
 for index,analysis in enumerate(displayed):
  audit=analysis.get('cleaning_audit',{})
  for key in ['source_anomalies','source_changes']:
   records_for_key=audit.pop(key,[]);audit[key+'_files']=[]
   for chunk,start in enumerate(range(0,len(records_for_key),20)):
    name='_HOST_%s_%s_%s.json'%(key,index,chunk);audit[key+'_files'].append(name)
    (authored/name).write_text(json.dumps(dict(host_derived=True,**{key:records_for_key[start:start+20]}),separators=(',',':'))+'\n')
 (authored/'_HOST_STATISTICAL_REFERENCES.json').write_text(json.dumps(dict(host_derived=True,scope='Conditional numerical references from submitted data; assumptions are not mandatory methods. Do not treat references as model deliverables or credit their presence as fulfilled work.',analyses=displayed),separators=(',',':'))+'\n')
 assert artifact_hashes(source)==before
 report=dict(selected_source_variant=source_variant,original_artifact_hashes=before,source_artifacts_unchanged=True,serialized_tables=records,statistical_references=analyses,scope='Private host-derived evidence, not repaired or additional submitted work')
 (root/'derived_sqlite_evidence.json').write_text(json.dumps(report,indent=2)+'\n')
 return original,authored,report

def cleaning_audit(database,source_database):
 c=sqlite3.connect('file:'+str(Path(database).resolve())+'?mode=ro',uri=True)
 cleaned=table(c,'cleaned_responses')
 names={r[0] for r in c.execute("select name from sqlite_master where type='table'")}
 for name in ['cleaned_respondents','respondents']:
  if name in names:
   joined={}
   for row in table(c,name):joined.setdefault(row.get('respondent_id'),[]).append(row)
   for row in cleaned:
    match=joined.get(row.get('respondent_id'),[])
    if len(match)==1:
     for key,value in match[0].items():row.setdefault(key,value)
   break
 c.close()
 c=sqlite3.connect('file:'+str(Path(source_database).resolve())+'?mode=ro',uri=True)
 people=table(c,'respondents');responses=table(c,'survey_responses');c.close()
 by_response={r['response_id']:r for r in cleaned};original={r['response_id']:r for r in responses};by_person={}
 for r in people:by_person.setdefault(r['respondent_id'],[]).append(r)
 aliases={'Untied States':'United States','Germny':'Germany','Brazl':'Brazil','Austrlia':'Australia'}
 anomalies=[];link_changes=[];changes=[]
 for row in responses:
  rid=row['response_id'];out=by_response.get(rid);person=by_person.get(row['respondent_id'],[]);issues=[]
  if not person:issues.append('orphan respondent')
  if len(person)>1:issues.append('multiple demographic records')
  for p in person:
   if p['country'] in aliases:issues.append('country spelling: '+p['country'])
   if p['country'] is None or not str(p['country']).strip():issues.append('missing country')
   if p['age'] is not None and not 0<p['age']<=120:issues.append('invalid age '+str(p['age']))
   if p['political_ideology'] is not None and not 1<=p['political_ideology']<=7:issues.append('invalid ideology '+str(p['political_ideology']))
   if p['gender'] in ['M','male']:issues.append('gender label '+p['gender'])
  from .jb15_statistics import LIKERT
  for k in LIKERT:
   if row.get(k) is None:issues.append('missing '+k)
   elif not 1<=row[k]<=5:issues.append('out-of-range '+k+'='+str(row[k]))
  if out and out.get('respondent_id')!=row['respondent_id']:link_changes.append(rid)
  if out:
   fields=[]
   for key,before in row.items():
    if key in out and key not in ['response_id','respondent_id'] and str(out[key])!=str(before):
     from .jb15_statistics import finite
     if finite(out[key]) is not None and finite(before) is not None and finite(out[key])==finite(before):continue
     fields.append(dict(field=key,before=before,after=out[key]))
   for key in ['country','age','gender','education','income_level','urban_rural','political_ideology','survey_date']:
    before_values=[p[key] for p in person if key in p]
    if key in out and before_values and all(str(out[key])!=str(value) for value in before_values):
     fields.append(dict(field=key,before_candidates=before_values,after=out[key]))
   if fields:changes.append(dict(response_id=rid,fields=fields,data_quality_flag=out.get('data_quality_flag')))
  if issues:anomalies.append(dict(response_id=rid,respondent_id=row['respondent_id'],source_issues=issues,source_demographics=person,submitted_row=out))
 return dict(invented_response_ids=sorted(set(by_response)-set(original)),omitted_response_ids=sorted(set(original)-set(by_response)),changed_respondent_links=link_changes,source_anomalies=anomalies,source_changes=changes,scope='Full source scan identifies records needing review; corrections or justified exclusions are assessed from submitted flags/memo, not forced to one cleaning policy.')

def public_references(target,source_variant="full"):
 import csv,pdfplumber
 root=Path(__file__).resolve().parents[2]
 packet=root/'data/expanded/JB15/variants'/source_variant/'inputs'
 con=sqlite3.connect(packet/'climate_policy_survey_raw.db');countries={r[0] for r in con.execute('select country from country_metadata')};con.close()
 countries.add('United States of America')
 with (packet/'Climate_Change_Opinion_Survey_2023_aggregated.csv').open() as stream:
  reader=csv.DictReader(stream);headers=reader.fieldnames;rows=[r for r in reader if r['country'] in countries]
 with (target/'_HOST_PUBLIC_METAYALE_SOURCE.csv').open('w') as stream:
  writer=csv.DictWriter(stream,fieldnames=headers);writer.writeheader();writer.writerows(rows)
 public=root/'data/source/dataset/social_science_research_assistants/task3/files_required_to_search'
 with pdfplumber.open(public/'ESS_Climate_Change_Topline_Results.pdf') as pdf:
  (target/'_HOST_PUBLIC_ESS_TABLE1.txt').write_text('Host reference: supplied ESS PDF page 4, not submitted work.\n'+(pdf.pages[3].extract_text() or ''))
 shutil.copy2(public/'Climate_Change_Opinion_Survey_Codebooks_2021to2023.xlsx',target/'_HOST_PUBLIC_CODEBOOK.xlsx')
 (target/'_HOST_PUBLIC_NOTICE.txt').write_text('Files prefixed _HOST_PUBLIC are evaluator-provided source references, not solver deliverables. Never credit their presence as fulfilled workbook, crosswalk, memo or source-consultation work. Compare the submitted outputs against them. The Meta/Yale subset retains all response rows for the 15 study countries, including the US naming alias.\n')
