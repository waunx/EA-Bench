"""JB16 geometry, installed-rate and complete reinforcement controls."""
import csv,json,math,re
from decimal import Decimal,ROUND_HALF_UP
from .author_english_jb16 import RELEASE,REFERENCE_ROOT

def expected(variant,world):
 p=RELEASE/'variants'/variant/'inputs';o=json.loads((RELEASE/'private/oracle.json').read_text());spec=o['variants'][variant]
 for k in spec['missing']+spec['conflict']:
  if k not in world:raise ValueError('Missing private estimate field '+k)
 facts={k:world.get(k,a['default']) for k,a in o['atoms'].items()}
 costs=list(csv.DictReader((p/'Material_Labor_Unit_Costs_2024.csv').open()));target=next(r for r in costs if r['Item Description']=='Precast Conc. Box Culvert 10x8')
 equipment=Decimal(target['Equipment Cost ($/unit)']);unit=Decimal(str(facts['material']))+Decimal(str(facts['installation']))+equipment
 header=None;bars=[]
 for row in csv.reader((p/'Reinforcement_Schedule_Template.csv').open()):
  if row and row[0]=='Bar Mark':header=row
  elif row and header and row[0].startswith(('WW-','HW-','AP-','M-')):
   r=dict(zip(header,row));weight=Decimal(r['Total Length (ft)'])*Decimal(r['Unit Weight (lb/ft)']);bars.append(dict(source=r,weight_unrounded=str(weight),weight_half_up=str(weight.quantize(Decimal('.01'),rounding=ROUND_HALF_UP))))
 subtotal=sum(Decimal(r['weight_unrounded']) for r in bars);rounded=sum(Decimal(r['weight_half_up']) for r in bars)
 controls=dict(duration=facts['duration'],precast_length=72,installed_unit_cost=float(unit),precast_line_cost=float(unit*72),excavation_template_base_ft=72/math.cos(math.radians(15)),apron_inlet_cy=8*14*(8/12)/27,apron_outlet_cy=12*14*(10/12)/27,riprap_cy=150*1.5/27,steel_exact_subtotal=str(subtotal),steel_row_rounded_subtotal=str(rounded),steel_exact_with_waste=str(subtotal*Decimal('1.05')),steel_row_rounded_with_waste=str((rounded*Decimal('1.05')).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)))
 benchmark=[dict(item=item,unit=u,low_bidder=low,engineer_estimate=engineer,page=page) for item,u,low,engineer,page in [('Removing cement concrete pavement','SY',25.5,30,1),('Removing asphalt pavement','SY',22.5,12.5,1),('Roadway excavation including haul','CY',72.85,70,2),('Crushed surfacing base course','TON',75,48.7,3),('Cement concrete pavement','CY',425,400,3),('Corrosion resistant dowel bar','EACH',23,20.2,3),('Tie bar with drill hole','EACH',51,20,3),('HMA3/8PG64H-28','TON',146,185,3),('HMA1/2PG64H-28','TON',320,320,3),('Inlet protection','EACH',320,300,4),('Seeding and mulching','ACRE',8500,5000,4),('Portable changeable message sign','HR',10,15,5),('Project temporary traffic control','LS',250000,150000,5),('Construction signs class A','SF',31,40,5),('Plugging existing pipe','EACH',1100,500,6),('Adjust manhole','EACH',1400,1400,6)]]
 import hashlib
 wsdot=json.loads((RELEASE/'private/wsdot_extraction.json').read_text());assert hashlib.sha256((p/wsdot['source']).read_bytes()).hexdigest()==wsdot['sha256']
 published={r['bar_size']:r for r in csv.DictReader((p/'published_rebar_weights.csv').open())}
 for bar in bars:assert Decimal(bar['source']['Unit Weight (lb/ft)'])==Decimal(published[bar['source']['Bar Size']]['weight_lb_per_ft'])
 return dict(published_weights=published,world=facts,controls=controls,bar_checks=bars,costs=costs,specifications=(p/'Box_Culvert_Project_Specifications.txt').read_text(),quantity_template=(p/'Quantity_Takeoff_Template.csv').read_text(),reinforcement_template=(p/'Reinforcement_Schedule_Template.csv').read_text(),wsdot=wsdot,benchmarks=benchmark,benchmark_note='Low bidder is ACME on contract total, not lowest price per item among bidders. Roadway excavation and differing HMA grades need scope adjustments, not a false direct match.',supplements={x.name:json.loads(x.read_text()) for x in p.glob('*.json')})
