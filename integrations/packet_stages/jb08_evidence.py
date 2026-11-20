"""Independent JB08 sales, funnel and review calculations."""
import csv,json,zipfile,xml.etree.ElementTree as ET
from collections import defaultdict
from decimal import Decimal
from .author_english_jb08 import RELEASE,REFERENCE_ROOT

def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def text(p):
 with zipfile.ZipFile(p) as z:return ' '.join(ET.fromstring(z.read('word/document.xml')).itertext())
def expected(variant,world):
 import openpyxl
 p=RELEASE/'variants'/variant/'inputs';o=json.loads((RELEASE/'private/oracle.json').read_text());spec=o['variants'][variant]
 for k in spec['missing']+spec['conflict']:
  if k not in world:raise ValueError('Missing private world fact: '+k)
 facts={k:world.get(k,a['default']) for k,a in o['atoms'].items()}
 sales=rows(p/'store_sales_data.csv');target=[r for r in sales if r['Order ID']=='CA-2016-152156' and r['Product ID']=='FUR-BO-10001798'];assert len(target)==1;target[0]['Profit']=str(facts['profit'])
 def sales_groups(key):
  groups=defaultdict(list)
  for r in sales:groups[r[key]].append(r)
  out=[]
  for k,v in groups.items():
   revenue=sum(Decimal(r['Sales']) for r in v);profit=sum(Decimal(r['Profit']) for r in v)
   out.append(dict(key=k,revenue=float(revenue),profit=float(profit),margin_pct=float(profit/revenue*100),mean_discount=sum(float(r['Discount']) for r in v)/len(v),distinct_orders=len({r['Order ID'] for r in v}),transaction_count=len(v),names=sorted({r['Product Name'] for r in v})))
  return out
 categories=sales_groups('Sub-Category')
 for row in categories:row.pop('names')
 products=sales_groups('Product ID');worst=sorted(products,key=lambda r:(r['margin_pct'],r['key']))[:10]
 traffic=rows(REFERENCE_ROOT/'website_traffic_data.csv');groups=defaultdict(list)
 for r in traffic:groups[(r['Month'],r['VisitorType'])].append(r)
 funnel=[dict(month=k[0],visitor_type=k[1],sessions=len(v),avg_product_pages=sum(float(r['ProductRelated']) for r in v)/len(v),avg_bounce=sum(float(r['BounceRates']) for r in v)/len(v),avg_page_value=sum(float(r['PageValues']) for r in v)/len(v),conversion=sum(r['Revenue'].upper()=='TRUE' for r in v)/len(v)) for k,v in sorted(groups.items())]
 reviews=rows(REFERENCE_ROOT/'customer_reviews.csv')
 def review_groups(key):
  g=defaultdict(list)
  for r in reviews:g[r[key] or '(missing)'].append(r)
  return [dict(name=k,count=len(v),rating=sum(int(r['Rating']) for r in v)/len(v),recommendation=sum(int(r['Recommended IND']) for r in v)/len(v)) for k,v in sorted(g.items())]
 classes=review_groups('Class Name');departments=review_groups('Department Name')
 bottom=sorted([r for r in classes if r['count']>=30 and r['name']!='(missing)'],key=lambda r:(r['rating'],r['recommendation'],-r['count'],r['name']))[:3]
 excerpts={name:[dict(row=r[''],rating=r['Rating'],text=r['Review Text']) for r in reviews if r['Class Name']==name and int(r['Rating'])<=2 and r['Review Text']][:18] for name in [r['name'] for r in bottom]+['Sweaters']}
 catalog=rows(p/'current_product_listings.csv');titles={r['Title'].casefold() for r in catalog if r['Title']}
 for r in worst:r['exact_catalog_title_matches']=[n for n in r['names'] if n.casefold() in titles]
 b=openpyxl.load_workbook(p/'customer_complaint_emails.xlsx',data_only=True);ticket_rows=list(b.active.values);tickets=[dict(zip(ticket_rows[0],r)) for r in ticket_rows[1:]]
 return dict(confirmed_world=facts,sales_rows=len(sales),subcategories=categories,product_margin_convention='Sum product Profit divided by sum product Sales, grouped by Product ID. Break exact ties by Product ID; alternative tie choices at cutoff are acceptable.',worst_products=worst,traffic_sessions=len(traffic),funnel=funnel,review_count=len(reviews),department_metrics=departments,class_metrics=classes,lowest_classes=bottom,review_excerpt_scope='Examples from <=2-star reviews, not a complete theme-frequency count. Judge themes against cited source language; do not claim these examples exhaust the dataset.',review_excerpts=excerpts,catalog=[{k:v for k,v in r.items() if v} for r in catalog],tickets=tickets,policy=text(p/'store_policies.docx'),supplements={r.name:json.loads(r.read_text()) for r in p.glob('*.json')})

def visible_expected(variant, clarification_records=None):
 """Derive judge context from mounted records and delivered replies only."""
 import re
 p=RELEASE/'variants'/variant/'inputs'
 spec=json.loads((RELEASE/'private/oracle.json').read_text())['variants'][variant]
 unresolved=set(spec['missing']+spec['conflict']);policy=text(p/'store_policies.docx')
 sale=next(r for r in rows(p/'store_sales_data.csv') if r['Order ID']=='CA-2016-152156' and r['Product ID']=='FUR-BO-10001798')
 confirmed={}
 if 'profit' not in unresolved:confirmed['profit']=float(sale['Profit'])
 quality=policy.split('6. Product Quality Guarantee',1)[-1]
 if 'quality_coupon' not in unresolved:confirmed['quality_coupon']=int(re.search(r'A (\d+)% discount code',quality)[1])
 if 'photo_required' not in unresolved:confirmed['photo_required']='Photo documentation of the defect is required' in quality
 accepted=[]
 for record in clarification_records or []:
  for item in record.get('provided',[]):
   key=item.get('fact_id');quote=item.get('reply_evidence');value=item.get('value')
   if key not in {'profit','quality_coupon','photo_required'} or not quote or quote not in record.get('reply',''):continue
   answers={'profit':f'For order CA-2016-152156, product FUR-BO-10001798, realized profit is {value} dollars.', 'quality_coupon':f'The Product Quality Guarantee goodwill discount code is {value} percent.', 'photo_required':'Photo documentation is '+('required' if value else 'not required')+' for Product Quality Guarantee claims.'}
   if quote!=answers[key]:continue
   confirmed[key]=value;unresolved.discard(key);accepted.append(item)
 calculation={k:confirmed.get(k,0 if k!='photo_required' else False) for k in ('profit','quality_coupon','photo_required')}
 ev=expected(variant,calculation);ev['confirmed_world']=confirmed
 if 'profit' in unresolved:
  book=next(r for r in ev['subcategories'] if r['key']=='Bookcases')
  book['profit_formula']=f"{book.pop('profit')} + p, where p is the unresolved target realized profit"
  book.pop('margin_pct');book['margin_formula']='100 * (known profit subtotal + p) / revenue'
  ev['worst_products']=[]
  ev['unresolved_product_ranking']='Compute margins from visible rows; the target product and overall ranking depend on unresolved p. Conditional rankings or an explicitly bounded unresolved rank are acceptable. Do not guess p.'
 ev['clarification_audit']={'records':clarification_records or [],'accepted':accepted,'unconfirmed_keys':sorted(unresolved)}
 return ev
