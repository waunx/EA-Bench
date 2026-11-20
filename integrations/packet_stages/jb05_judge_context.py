"""Build JB05 judge context from visible sources and actually delivered confirmations."""
import csv,json,re,zipfile,xml.etree.ElementTree as ET
from pathlib import Path

def build(packet,variant,records=()):
 packet=Path(packet);folder=packet/'variants'/variant/'inputs';oracle=json.loads((packet/'private/oracle.json').read_text())
 with zipfile.ZipFile(folder/'project_scope_memo.docx') as z:text=' '.join(ET.fromstring(z.read('word/document.xml')).itertext())
 rates=list(csv.DictReader((folder/'labor_equipment_rates.csv').open()))
 def quantity(pattern):
  value=re.search(pattern,text)[1]
  return float(value) if value!='[unrecorded]' else None
 sourced=dict(repair_area=quantity(r'estimated (\d+|\[unrecorded\]) SF of steel plate replacement'),crack_length=quantity(r'estimated (\d+|\[unrecorded\]) LF of epoxy injection'))
 rate=next(r['Rate_USD'] for r in rates if r['Item_Code']=='M-009');sourced['epoxy_rate']=float(rate) if rate else None
 points={k:v for k,v in sourced.items() if v is not None};confirmed={}
 for record in records:
  for item in record['provided']:
   if item['fact_id'] in sourced:confirmed[item['fact_id']]=item['value']
 points.update(confirmed);unconfirmed=[k for k,v in sourced.items() if v is None and k not in confirmed]
 examples={k:[oracle['atoms'][k]['default'],oracle['atoms'][k]['alternative']] for k in unconfirmed}
 visible=dict(scope_memo=text,local_rate_csv=(folder/'labor_equipment_rates.csv').read_text(),supplements={p.name:json.loads(p.read_text()) for p in folder.glob('*.json')})
 return dict(sourced_or_actually_confirmed_points=points,actually_confirmed_points=confirmed,unconfirmed_attributes=unconfirmed,feasible_alternative_illustrations=examples,visible_records=visible,policy='Alternatives are equally feasible illustrations, not a selected hidden truth or required sensitivity endpoints. Evaluate justified provisional assumptions and material sensitivity; do not demand a particular question or private point value. Confirmed point expectations come only from visible records or delivered replies.')
