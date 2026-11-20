"""Source-based reconciliation for all JB20 records; no selected hidden values."""
import csv,json,hashlib
from pathlib import Path
from decimal import Decimal
import openpyxl
ROOT=Path(__file__).resolve().parents[2]
PACKET=ROOT/'data/expanded/JB20'
NUMERIC={'Units_Sold','Unit_Price','Total_Revenue'}

def table(path,sheet=None):
 w=openpyxl.load_workbook(path,data_only=True);s=w[sheet] if sheet else w.active;r=list(s.values);w.close()
 return [dict(zip(r[0],row)) for row in r[1:] if row[0] is not None]

def equal(field,a,b):
 if field in NUMERIC and a is not None and b is not None:return Decimal(str(a))==Decimal(str(b))
 return a==b

def source_context(variant,records=None):
 p=PACKET/'variants'/variant/'inputs';crm=table(p/'Source_Sales_Orders_Q3_2025.xlsx');erp=table(p/'Data_Entry_Records_Q3_2025.xlsx')
 with (p/'Customer_Master_List.csv').open(encoding='utf-8-sig') as f:master=list(csv.DictReader(f))
 scans=json.loads((PACKET/'private/scan_transcription.json').read_text())
 for name,digest in scans['image_hashes'].items():assert hashlib.sha256((p/name).read_bytes()).hexdigest()==digest
 scan={r['Order_ID']:r for r in scans['rows']}
 claims=json.loads((p/'source_records.json').read_text()) if (p/'source_records.json').exists() else []
 byid={r['Order_ID']:r for r in crm}
 facts=dict(registered_name=next(r['Customer_Name'] for r in master if r['Customer_ID']=='CUST-001') or None,channel26=byid['ORD-202509-0026']['Sales_Channel'],date12=byid['ORD-202507-0012']['Order_Date'])
 supplied={x['fact_id']:x['value'] for r in (records or []) for x in r.get('provided',[])}
 for k,v in list(facts.items()):
  if v is None:
   rs=[r for r in claims if r['fact']==k]
   if rs:
    latest=max(r['revision'] for r in rs);vs={r['value'] for r in rs if r['revision']==latest}
    if len(vs)==1:facts[k]=next(iter(vs))
  if k in supplied:facts[k]=supplied[k]
 unresolved=[k for k,v in facts.items() if v is None]
 o=json.loads((PACKET/'private/oracle.json').read_text())
 alternatives={k:[o['atoms'][k]['default'],o['atoms'][k]['alternative']] for k in unresolved}
 import copy
 effective=copy.deepcopy(crm);emaster=copy.deepcopy(master)
 for r in effective:
  if r['Order_ID']=='ORD-202509-0026':r['Sales_Channel']=facts['channel26']
  if r['Order_ID']=='ORD-202507-0012':r['Order_Date']=facts['date12']
 for r in emaster:
  if r['Customer_ID']=='CUST-001':r['Customer_Name']=facts['registered_name']
 aligned={};links=[]
 for e in erp:
  key=e['Order_ID']
  if key not in byid:
   candidates=[r['Order_ID'] for r in crm if all(equal(k,r[k],e[k]) for k in r if k!='Order_ID')]
   assert len(candidates)==1,'Ambiguous malformed ERP identifier'
   key=candidates[0]
   links.append(dict(raw_erp_id=e['Order_ID'],matched_crm_id=key,basis='Unique exact match on eight other fields'))
  assert key not in aligned;aligned[key]=e
 assert set(aligned)==set(byid)
 discrepancies=[];missing=[];expected=[]
 for r in effective:
  key=r['Order_ID'];target=dict(scan.get(key,r));expected.append(target)
  for system,raw in [('CRM',byid[key]),('ERP',aligned[key])]:
   for field,correct in target.items():
    value=raw[field]
    if value in [None,'']:
     missing.append(dict(order=key,source=system,field=field));continue
    if correct is not None and not equal(field,value,correct):
     discrepancies.append(dict(order=key,source=system,field=field,observed=value,correct=correct))
  if target['Order_Date'] is None and int(str(aligned[key]['Order_Date']).split('/')[0])>12:
   discrepancies.append(dict(order=key,source='ERP',field='Order_Date',observed=aligned[key]['Order_Date'],correct=None,note='Known format error; actual date unresolved'))
 registered={r['Customer_Name'] for r in emaster if r['Customer_Name']}
 uncertain_names=set(alternatives.get('registered_name',[]));registration={}
 for r in expected:
  name=r['Customer_Name'];status='registered' if name in registered else ('unresolved' if name in uncertain_names else 'unregistered')
  registration[r['Order_ID']]=dict(customer=name,status=status)
 arithmetic=[]
 for system,data in [('CRM',crm),('ERP',erp)]:
  for r in data:
   if all(r[k] is not None for k in NUMERIC):
    calc=Decimal(str(r['Units_Sold']))*Decimal(str(r['Unit_Price']));delta=Decimal(str(r['Total_Revenue']))-calc
    if abs(delta)>Decimal('.01'):arithmetic.append(dict(source=system,order=r['Order_ID'],units=r['Units_Sold'],unit_price=r['Unit_Price'],stored=r['Total_Revenue'],product=str(calc),variance=str(delta)))
 templates={}
 for name in ['Error_Log_Template.xlsx','Compliance_Checklist.xlsx']:
  w=openpyxl.load_workbook(p/name,data_only=False);templates[name]={s.title:list(s.values) for s in w};w.close()
 return dict(visible_crm=crm,visible_erp=erp,visible_master=master,scan_transcription=scans,templates=templates,
  resolved_facts={k:v for k,v in facts.items() if v is not None},unresolved_alternatives=alternatives,clarification_records=records or [],
  authoritative_reconciled_rows=expected,discrepancies=discrepancies,missing_source_fields=missing,registration=registration,erp_identity_recovery=links,
  raw_record_formula_errors=arithmetic,records=len(crm),known_discrepant_orders=len({x['order'] for x in discrepancies}),
  supplements={f.name:json.loads(f.read_text()) for f in p.glob('*.json')},
  interpretation='Disagreements, missing fields, raw arithmetic and registration findings are distinct metrics. Use stated units and phases; unknown is not a verified match. Do not invent a selected hidden value.')
