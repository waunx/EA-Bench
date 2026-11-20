"""Evidence-aware workforce possibilities; never select an undisclosed private world."""
import itertools,json
from .jb11_analysis import PACKET,analyze

def build(variant,clarification_records=()):
 oracle=json.loads((PACKET/'private/oracle.json').read_text());spec=oracle['variants'][variant]
 uncertain=spec['missing']+spec['conflict'];confirmed={}
 for record in clarification_records:
  for item in record.get('provided',[]):
   if item.get('fact_id') in uncertain:confirmed[item['fact_id']]=item['value']
 pending=[k for k in uncertain if k not in confirmed]
 possibilities=[]
 for values in itertools.product(*[[oracle['atoms'][k]['default'],oracle['atoms'][k]['alternative']] for k in pending]):
  possibilities.append(analyze(variant,dict(confirmed,**dict(zip(pending,values)))))
 def unique(rows):
  return list({json.dumps(row,sort_keys=True):row for row in rows}.values())
 role_names=[r['role'] for r in possibilities[0]['roles']];applicants=[a['applicant'] for a in possibilities[0]['screening']]
 totals=[]
 for analysis in possibilities:
  overtime={key:dict(n=sum(r['overtime'][key]['n'] for r in analysis['roles']),departed=sum(r['overtime'][key]['departed'] for r in analysis['roles'])) for key in ['Yes','No']}
  totals.append(dict(employee_count=analysis['employee_count'],departed=analysis['departed'],applicant_count=analysis['applicant_count'],overtime=overtime))
 return dict(scope=possibilities[0]['scope'],actually_confirmed=confirmed,unconfirmed_fields=pending,
  workforce_total_possibilities=unique(totals),
  role_possibilities={name:unique([next(r for r in a['roles'] if r['role']==name) for a in possibilities]) for name in role_names},
  applicant_possibilities={name:unique([next(r for r in a['screening'] if r['applicant']==name) for a in possibilities]) for name in applicants},
  illustrated_unconfirmed_values={key:[oracle['atoms'][key]['default'],oracle['atoms'][key]['alternative']] for key in pending},
  policy='A singleton is invariant under the illustrated feasible interpretations or supported by visible records/actually delivered confirmations. Multiple entries are equally feasible alternatives, not a selected private truth. Accept explicit conditional findings and pending verification with correct scope, quantified material effects and actionable conditional recommendations. Do not require any particular clarification or invented factual commitment. Illustrations are not mandatory endpoints. License gates describe reported eligibility, never independent verification. Co-varying facts must be handled consistently across the documents.')
