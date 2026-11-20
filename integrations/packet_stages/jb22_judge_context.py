"""Protocol expectations use visible records or actual confirmations only."""
import csv,json
from pathlib import Path
FIELDS={'alpha':'Significance_Level_Alpha','dropout':'Dropout_Rate_Anticipated','power':'Statistical_Power'}
def build(packet,variant,records=()):
 packet=Path(packet);folder=packet/'variants'/variant/'inputs'
 rows=list(csv.DictReader((folder/'Clinical_Study_Proposal_CVD_Prevention.csv').open()));params={r['Study_Parameter']:r for r in rows}
 points={k:float(params[field]['Value']) for k,field in FIELDS.items() if params[field]['Value']};confirmed={}
 for record in records:
  for item in record['provided']:
   if item['fact_id'] in FIELDS:confirmed[item['fact_id']]=item['value']
 points.update(confirmed);unknown=[k for k in FIELDS if k not in points];oracle=json.loads((packet/'private/oracle.json').read_text())
 return dict(sourced_or_actually_confirmed_points=points,actual_confirmations=confirmed,unconfirmed_attributes=unknown,feasible_alternative_illustrations={k:[oracle['atoms'][k]['default'],oracle['atoms'][k]['alternative']] for k in unknown},visible_proposal=rows,visible_supplements={p.name:json.loads(p.read_text()) for p in folder.glob('*.json')},policy='Alternatives are equal illustrations, not selected truth. Unconfirmed primary inputs require confirmation or explicit conditional design/sensitivity pending protocol approval. Calculator example defaults, exploratory endpoints and other trial phases do not confirm the primary protocol. No required question count or intermediate-print sequence.')
