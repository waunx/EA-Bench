"""Private transaction and network source audit, never mounted for agents."""
from pathlib import Path
import json,hashlib
import pandas as pd,openpyxl
from .author_english_jb14 import PACKET,REFERENCE_ROOT

def analyze(variant,world=None):
 world=world or {};folder=PACKET/'variants'/variant/'inputs';d=pd.read_csv(folder/'orders_and_shipments.csv',dtype=str,keep_default_na=False);d.columns=d.columns.str.strip()
 target=(d['Order ID']=='3535')&(d['Order Item ID']=='8793');assert target.sum()==1
 claims=json.loads((folder/'source_records.json').read_text()) if (folder/'source_records.json').exists() else []
 for key,col in [('ship_day','Shipment Day'),('discount','Discount %'),('profit','Profit')]:
  raw=d.loc[target,col].iloc[0]
  if not raw:
   rr=[r for r in claims if r['fact']==key];vals={r['value'] for r in rr if r['revision']==max(x['revision'] for x in rr)} if rr else set()
   if len(vals)==1:raw=next(iter(vals))
   elif key in world:raw=world[key]
   else:raise ValueError('Unresolved '+key)
   d.loc[target,col]=str(raw)
 dash_discounts=d['Discount %'].str.strip().eq('-');dash_count=int(dash_discounts.sum());d.loc[dash_discounts,'Discount %']='0'
 for c in ['Order Quantity','Gross Sales','Discount %','Profit']:d[c]=pd.to_numeric(d[c])
 d['net_sales']=d['Gross Sales']*(1-d['Discount %'])
 def dates(prefix):return pd.to_datetime(dict(year=d[prefix+' Year'],month=d[prefix+' Month'],day=d[prefix+' Day']))
 d['calendar_days']=(dates('Shipment')-dates('Order')).dt.days
 d['schedule_delta']=d['calendar_days']-pd.to_numeric(d['Shipment Days - Scheduled'])
 d['dispatch_after_schedule']=d['schedule_delta']>0
 groups=d.groupby(['Warehouse Country','Customer Region','Order Year']).agg(order_lines=('Order ID','size'),shipped_units=('Order Quantity','sum'),net_sales=('net_sales','sum'),profit=('Profit','sum'),gross_sales=('Gross Sales','sum'),dispatch_days_sum=('calendar_days','sum'),schedule_delta_sum=('schedule_delta','sum'),dispatch_after_schedule_lines=('dispatch_after_schedule','sum')).reset_index()
 monthly=d.groupby(['Warehouse Country','Order YearMonth']).agg(order_lines=('Order ID','size'),shipped_units=('Order Quantity','sum')).reset_index()
 t=d.loc[target].iloc[0];net=float(t['net_sales']);row=dict(calendar_days=int(t['calendar_days']),schedule_delta=int(t['calendar_days'])-int(t['Shipment Days - Scheduled']),net_sales=net,profit=float(t['Profit']),margin_pct=round(float(t['Profit'])/net*100,4))
 w=openpyxl.load_workbook(folder/'warehouse_master_data.xlsx',read_only=True,data_only=True);master={}
 for s in w:
  records=list(s.values);master[s.title]=[dict(zip(records[0],r)) for r in records[1:] if r[0]]
 w.close();references={}
 for f in REFERENCE_ROOT.glob('*.csv'):
  raw=pd.read_csv(f);references[f.name]=dict(columns=list(raw.columns),rows=len(raw),sha256=hashlib.sha256(f.read_bytes()).hexdigest())
 network_totals=dict(order_lines=len(d),shipped_units=int(d['Order Quantity'].sum()),gross_sales=float(d['Gross Sales'].sum()),net_sales=float(d['net_sales'].sum()),profit=float(d['Profit'].sum()),dispatch_days_sum=int(d['calendar_days'].sum()),schedule_delta_sum=int(d['schedule_delta'].sum()),dispatch_after_schedule_lines=int(d['dispatch_after_schedule'].sum()))
 return dict(network_totals=network_totals,discount_dash_records=dash_count,discount_dash_assumption='Corridor net_sales treats accounting dashes as zero discount; other justified disclosed handling is acceptable.',transaction=row,order_lines=len(d),years=sorted(d['Order Year'].unique()),regions_by_warehouse=d.groupby('Warehouse Country')['Customer Region'].nunique().to_dict(),monthly=monthly.to_dict('records'),corridors=groups.to_dict('records'),master=master,references=references,
  measurement_limits=['Inventory and fulfillment reference files lack warehouse identifiers; allocation by DC needs an explicit assumption.','Order lines, shipped units, storage positions and pallet-days are different quantities.','Dispatch interval versus schedule is not directly observed customer arrival performance.'])
