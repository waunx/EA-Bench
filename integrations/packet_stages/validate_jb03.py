"""Independent JB03 branch/provenance audit; artifact scoring is separate."""
import hashlib,itertools,json,sqlite3,re,copy
from collections import defaultdict,Counter
from .author_english_jb03 import ROOT,RELEASE
EVIDENCE=RELEASE/'private/validation-20261011'
def load(variant):
 p=RELEASE/'variants'/variant/'inputs';c=sqlite3.connect('file:'+str(p/'researcher_computing_survey.db')+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
 assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
 d={t:[dict(r) for r in c.execute('select * from '+t)] for t in ['researchers','computing_needs','current_infrastructure','software_requirements']};c.close();return d

def resolve(variant,answers):
 o=json.loads((RELEASE/'private/oracle.json').read_text());d=load(variant)
 for key,a in o['atoms'].items():
  row=next(r for r in d[a['table']] if r['id']==a['id'])
  if row[a['field']]=='':
   if key not in answers:raise ValueError('Missing confirmed value for '+a['table']+'.'+a['field']+' at row '+str(a['id']))
   row[a['field']]=answers[key]
 return d

def metrics(d):
 rows=d['computing_needs'];groups=defaultdict(list)
 for r in rows:groups[r['researcher_id']].append(r)
 totals={k:sum(r['gpu_hours_monthly'] for r in v) for k,v in groups.items()}
 cost=lambda r:r['gpu_hours_monthly']*36*(2.5 if r['memory_gb_required']>48 else 1.2)
 return dict(monthly_hours=sum(r['gpu_hours_monthly'] for r in rows),cloud_3year=sum(map(cost,rows)),researcher_max_memory_cloud_3year=sum(totals[k]*36*(2.5 if max(r['memory_gb_required'] for r in v)>48 else 1.2) for k,v in groups.items()),workload_cloud_3year=sum(cost(r) for r in rows if r['gpu_hours_monthly']<=500),researcher_cloud_3year=sum(cost(r) for r in rows if totals[r['researcher_id']]<=500),researcher_hours=totals,workload_types=dict(Counter(r['workload_type'] for r in rows)),wait_sum=sum(r['current_wait_time_hours'] for r in rows),status_counts=dict(Counter(r['status'] for r in d['current_infrastructure'])))
def applicable_metrics(d, attachments):
 """Apply explicit collection, institution and approval scope."""
 d=copy.deepcopy(d)
 for name,r in attachments.items():
  if name=='pilot_survey_archive.json' and r['collection']=='researcher_computing_survey':d['computing_needs'].extend(r['needs'])
  if name=='shared_asset_inventory.json' and r['institution']=='State University':d['current_infrastructure'].extend(r['assets'])
  if name=='survey_correction_history.json' and r['status']=='approved':
   row=next(x for x in d['computing_needs'] if x['id']==r['record']);row[r['field']]=r['value']
 return metrics(d)

def resolve_exports(records):
 """Same-issuer exports: supersession, revision, then peer agreement."""
 superseded={x for r in records for x in r.get('supersedes',[])}
 active=[r for r in records if r['copy'] not in superseded]
 active=[r for r in active if r['revision']==max(x['revision'] for x in active)]
 values={r['value'] for r in active}
 return next(iter(values)) if len(values)==1 else None

def main():
 o=json.loads((RELEASE/'private/oracle.json').read_text());manifest=json.loads((RELEASE/'MANIFEST.json').read_text());report={};reviews=[]
 for v,spec in o['variants'].items():
  folder=RELEASE/'variants'/v;d=load(v);unknown=spec['missing']+spec['conflict'];defaults={k:a['default'] for k,a in o['atoms'].items()}
  assert o['original_text'] in (folder/'prompt.md').read_text()
  actual={str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()};assert actual==manifest[v]
  assert all(n=='prompt.md' or n.startswith('inputs/') for n in actual)
  for p in (folder/'inputs').glob('*.json'):assert not re.search('[\u4e00-\u9fff]',p.read_text())
  for key,a in o['atoms'].items():
   val=next(r for r in d[a['table']] if r['id']==a['id'])[a['field']]
   assert val==('' if key in unknown else a['default'])
   if key in spec['conflict']:
    rr=json.loads((folder/'inputs'/(key+'_records.json')).read_text())
    assert len({(r['issuer'],r['revision'],r['table'],r['id'],r['field']) for r in rr})==1
    assert {r['value'] for r in rr}=={a['default'],a['alternative']}
    assert resolve_exports(rr) is None
    for field in ('revision','supersedes','value'):
     changed=copy.deepcopy(rr)
     if field=='revision':changed[1]['revision']+=1
     elif field=='supersedes':changed[1]['supersedes']=[changed[0]['copy']]
     else:changed[0]['value']=changed[1]['value']
     assert resolve_exports(changed)==a['alternative']
   if key in spec['missing']:assert not (folder/'inputs'/(key+'_records.json')).exists()
  worlds=[]
  for bits in itertools.product([0,1],repeat=len(unknown)):
   answers=dict(defaults)
   for k,b in zip(unknown,bits):answers[k]=o['atoms'][k]['alternative' if b else 'default']
   resolved=resolve(v,answers);computed=metrics(resolved)
   attachments={p.name:json.loads(p.read_text()) for p in (folder/'inputs').glob('*.json') if p.name in {'pilot_survey_archive.json','shared_asset_inventory.json','survey_correction_history.json'}}
   assert applicable_metrics(resolved,attachments)==computed
   for name,field,value,metric,delta in [
    ('pilot_survey_archive.json','collection','researcher_computing_survey','monthly_hours',1200),
    ('shared_asset_inventory.json','institution','State University','status_counts',None),
    ('survey_correction_history.json','status','approved','wait_sum',12-answers['wait3'])]:
    if name not in attachments:continue
    changed=copy.deepcopy(attachments);changed[name][field]=value
    alternative=applicable_metrics(resolved,changed)
    if metric=='status_counts':assert alternative[metric]['operational']==computed[metric]['operational']+1
    else:assert alternative[metric]==computed[metric]+delta
    assert alternative!=computed
   assert computed['monthly_hours']==75200+answers['hours44']
   assert abs(computed['cloud_3year']-(6746940+answers['hours44']*36*(2.5 if answers['memory44']>48 else 1.2)))<0.001
   assert computed['wait_sum']==2408+answers['wait3']
   assert computed['workload_types']['Model Training']==(18 if answers['workload30']=='Model Training' else 17)
   assert computed['researcher_hours'][1]==(3600 if answers['owner1']==1 else 400)
   assert computed['status_counts']['degraded']==(2 if answers['status3']=='operational' else 3)
   worlds.append(dict(answers={k:answers[k] for k in unknown},metrics=computed))
  assert len({json.dumps(w['metrics'],sort_keys=True) for w in worlds})==len(worlds)
  for name,field,disallowed in [('pilot_survey_archive.json','collection','researcher_computing_survey'),('shared_asset_inventory.json','institution','State University'),('survey_correction_history.json','status','approved')]:
   p=folder/'inputs'/name
   if p.exists():assert json.loads(p.read_text())[field]!=disallowed
  report[v]=dict(status='pass',worlds=worlds,visible_hashes=actual,conflict_resolution_counterfactuals=3*len(spec['conflict']),redundancy_applicability_counterfactuals=len(attachments)*len(worlds))
  reviews.append((v,spec,len(worlds)))
 for n in (1,2,3):assert report[f'M{n}R{n}C{n}']['worlds']==report[f'M{n}C{n}']['worlds']
 assert metrics(load('full'))==metrics(load('R3'))
 EVIDENCE.mkdir(parents=True,exist_ok=True)
 (EVIDENCE/'variant_audit.json').write_text(json.dumps(dict(case='JB03',layer='packet and branch checks only',variants=report),indent=2)+'\n')
 variant_review={v:dict(status='pass',changed_information=spec,worlds=count,
  business_conditions=[dict(o['atoms'][k],atom=k) for k in spec['missing']+spec['conflict']],
  clarification_sufficiency='Each answer identifies the database table, row ID, field and confirmed value; all joint answer combinations were calculated.',
  leakage_review='Unknown cells remain blank in this variant. No replacement survey values occur in the authored supplements; pilot collection, institution and withdrawn status determine non-applicability. Broader document leakage is a manual review, not a formal proof.',
  conflict_review='Same issuer and revision; neither export supersedes the other. Higher revision, explicit supersession and matching values are tested as resolvable counterfactuals.' if spec['conflict'] else 'No conflict condition.',
  redundancy_review='Out-of-scope records are applied through explicit scope predicates and leave all world metrics unchanged; each scope-switch counterfactual has an exact expected changed metric.' if spec['redundancy_groups'] else 'No redundant attachment condition.',
  state_branch_evidence=str((EVIDENCE/'variant_audit.json').relative_to(ROOT)),mount_scope='Only selected variants/'+v+'/prompt.md and inputs/',validation_layer='authored packet files and branch decisions') for v,spec,count in reviews}
 (RELEASE/'VARIANT_REVIEW.json').write_text(json.dumps(variant_review,indent=2)+'\n')
 summary=dict(status='pass',packets=len(report),worlds=sum(len(r['worlds']) for r in report.values()),validation_layer='authored packet files and branch decisions',evidence_root=str(EVIDENCE.relative_to(ROOT)),scope='Source/manifest, 200 answer worlds, attachment applicability and conflict counterfactuals only. No native evaluation or semantic artifact pass claimed.')
 (RELEASE/'check_result.json').write_text(json.dumps(summary,indent=2)+'\n')
 text='# JB03 release review\n\nOriginal task ID/text preserved; changes are authored supplements, not native snapshots. All attachments are English. Original PDF reference is cached with provenance. Historical files are untouched. Mount only the chosen prompt and inputs.\n\nSource scoring caveat: native hybrid rubric thresholds individual workload rows, whereas task prose says per researcher. Both interpretations must be disclosed in comparative work; original and authored completion scores remain separate. Proposed 64 GPUs cannot serve 75,800 GPU-hours/month even at continuous utilization; capacity shortfall cannot be hidden by cheaper undersizing. No time series is supplied, so temporal peak-to-average requires an explicit scenario, not a fabricated observed statistic.\n'
 for v,spec,count in reviews:
  text+=f'\n## {v}\n\nChanged information: {json.dumps(spec)}. Verified {count} distinct answer worlds.\n\n'
  for key in spec['missing']+spec['conflict']:
   a=o['atoms'][key];text+=f"- {a['table']}, row {a['id']}, {a['field']}: {a['default']!r} versus {a['alternative']!r}. Purpose: {a['kind']}; one explicit row/field value resolves this condition.\n"
  text+='\nLeakage review: remaining survey columns and software preferences do not determine missing memory, workload category or owner; vendor, WBS, NSF and LBNL files contain no replacement survey cells. Conflicts share issuer and revision, with neither export authoritative. Pilot survey belongs to a different collection; external inventory belongs to North Valley University; withdrawn correction is not effective. These records are neutral in all answer worlds. Scope counterfactuals are executed in each world: admitting the pilot adds 1,200 monthly GPU-hours; admitting the external inventory adds one operational asset; approving the correction sets row 3 wait to 12 hours. Each conflict also tests higher revision, explicit supersession and equal-value agreement, each resolving to the alternative value. Default and alternative calculations, joint branches, mount boundary and exact source hashes are checked by check.py.\n'
 text+='\nValidation scope: packet and branch evidence is in data/expanded/JB03/private/validation-20261011/variant_audit.json. Full artifact semantics require jb03_checker; these checks do not claim original evaluator success.\n'
 text+='\n## 2026-10-11 checker and feedback follow-up\n\nGPT-5.5 private static packet review is recorded under private/validation-20261011/feedback-p8kig6r9 and reported no blocking findings. It did not open binary attachments or execute checks and is not native evaluation. Its memory-tier ambiguity feedback is addressed by computing both workload-tier and researcher-maximum-memory costs and accepting an explicitly explained, consistent convention. Missing confirmations now identify the affected field instead of raising an opaque key error.\n\nAuthored acceptance no longer requires knowledge of hidden native rubric conventions, exact unrequested audit column names, or an infeasible smaller hybrid. The original rubric score remains separate. A failed structural gate returns failure before any semantic judge, including empty submissions. Six structural/confirmation/CLI regressions and the first live empty submission recheck are saved privately. Source artifacts and old evaluation traces remain unchanged.\n\nGPT-5.5 full artifact attempts are stored under private/validation-20261011/agent-full-*. These are solving-agent attempts with private feedback enabled; their metrics and artifact verdicts determine success separately from this packet check. The pinned Docker Excel runtime is unavailable locally, so no official semantic artifact pass is claimed.\n'
 if (EVIDENCE/'summary.json').exists():
  text+='\nFinal model evidence: first live attempt submitted no files and the corrected structural gate rejects it (original runtime-error record retained alongside the recheck). The second attempt was interrupted after five consecutive invalid protocol actions; it is an interrupted_protocol_diagnostic with zero evaluated samples, not a task-quality verdict. See private/validation-20261011/summary.json.\n'
 # Generated variant prose is evidence; do not overwrite accumulated case review.
 (EVIDENCE/'generated_variant_review.md').write_text(text)
 if not (RELEASE/'REVIEW.md').exists():(RELEASE/'REVIEW.md').write_text(text)
 print(json.dumps(dict(variants=len(report),worlds=sum(len(r['worlds']) for r in report.values()),status='pass')))
if __name__=='__main__':main()
