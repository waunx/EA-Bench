"""Macro expectations use visible records and actual confirmations, never selected hidden points."""
import json,sqlite3
from pathlib import Path
COLUMNS={'gdp':'gdp_per_capita','co2':'co2_per_capita','vulnerability':'climate_vulnerability_index'}
def build(packet,variant,records=()):
 packet=Path(packet);folder=packet/'variants'/variant/'inputs'
 with sqlite3.connect('file:'+str((folder/'climate_policy_survey_raw.db').resolve())+'?mode=ro',uri=True) as con:
  cols=[r[1] for r in con.execute('pragma table_info(country_metadata)')];source={r[0]:dict(zip(cols,r)) for r in con.execute('select * from country_metadata')}
 expected={k:dict(v) for k,v in source.items()};confirmed={}
 for record in records:
  for item in record['provided']:
   if item['fact_id'] in COLUMNS:confirmed[item['fact_id']]=item['value'];expected['United States'][COLUMNS[item['fact_id']]]=item['value']
 unknown=[k for k,col in COLUMNS.items() if expected['United States'][col] is None]
 oracle=json.loads((packet/'private/oracle.json').read_text())
 return dict(visible_country_metadata=source,verified_point_expectations=expected,actual_confirmations=confirmed,unconfirmed_attributes=unknown,feasible_alternative_illustrations={k:[oracle['atoms'][k]['default'],oracle['atoms'][k]['alternative']] for k in unknown},visible_supplements={p.name:json.loads(p.read_text()) for p in folder.glob('*.json')},policy='Both alternatives are illustrations, not selected truth. All country indicators must be numerical and verified; unknown fields need determining source evidence, not a lucky match to a private default. No required question wording/count. Conditional statistics cannot silently remove a study country.')
