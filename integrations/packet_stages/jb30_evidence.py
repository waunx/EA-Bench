"""Purchasing arithmetic and actual confirmed evidence, never selected guesses."""
import csv,io,json,re,sqlite3
from pathlib import Path
from decimal import Decimal
PACKET=Path(__file__).resolve().parents[2]/'data/expanded/JB30'

def quote(path):
    text=path.read_text();lines=text.splitlines();start=next(i for i,s in enumerate(lines) if s.startswith('Item_No,'))
    rows=list(csv.DictReader(io.StringIO('\n'.join(lines[start:]))))
    items=[r for r in rows if str(r['Item_No']).isdigit()]
    def number(label):
        return next(float(r['Extended_Price']) for r in rows if label in str(r.get('Unit_Price')))
    return text,items,number('Subtotal'),number('Freight')

def build(variant,world=None,clarification_records=None):
    folder=PACKET/'variants'/variant/'inputs';vendors={}
    for label,suffix,rates in [('Meridian','A_meridian_office',(45,150)),('Atlas','B_atlas_furnishings',(38,125)),('Pinnacle','C_pinnacle_workspace',(30,100))]:
        text,items,subtotal,freight=quote(folder/f'quotation_vendor_{suffix}.csv')
        recomputed=sum(Decimal(r['Quantity'])*Decimal(r['Unit_Price']) for r in items)
        required=[150,150,75,4,8,88,30];reduced=[150,150,50,4,8,88,20]
        normalized=sum(Decimal(q)*Decimal(r['Unit_Price']) for q,r in zip(required,items))
        adjusted=sum(Decimal(q)*Decimal(r['Unit_Price']) for q,r in zip(reduced,items))
        installation=150*rates[0]+12*rates[1]
        vendors[label]=dict(items=items,printed_subtotal=subtotal,recomputed_quoted_subtotal=float(recomputed),
            printed_extensions_sum=sum(float(r['Extended_Price']) for r in items),
            pr_normalized_original=float(normalized),max_permitted_reduction_merchandise=float(adjusted),
            freight=freight,workstation_install_rate=rates[0],table_install_rate=rates[1],installation=installation,
            installation_inclusive_baseline=float(adjusted)+installation+freight,
            budget_gap=float(adjusted)+installation+freight-310000,
            quantity_mismatches=[dict(item=r['Item_Code'],quoted=int(r['Quantity']),required=q) for q,r in zip(required,items) if int(r['Quantity'])!=q],
            extension_errors=[dict(item=r['Item_Code'],printed=float(r['Extended_Price']),recomputed=float(Decimal(r['Quantity'])*Decimal(r['Unit_Price']))) for r in items if Decimal(r['Quantity'])*Decimal(r['Unit_Price'])!=Decimal(r['Extended_Price'])],
            pricing_notes=text.split('Notes on Pricing:')[-1])
    return dict(vendors=vendors,meridian_facts=observed_facts(folder,clarification_records),history=history(folder),
        visible_sources={p.name:p.read_text() for p in folder.iterdir() if p.suffix in ['.csv','.txt','.json']},
        budget_cap=310000,weights=[.20,.15,.15,.10,.20,.10,.10],
        policy='Baseline assumes maximum permitted reductions and quoted unit rates. Retaining eligible quantities, conditional discounts, vendor repricing, inside delivery and negotiated alternatives are allowed when reconciled and clearly labelled. Unconfirmed specifications may remain pending verification; no hidden selected value is required.')

def observed_facts(folder,records):
    text,items,_,_=quote(folder/'quotation_vendor_A_meridian_office.csv')
    matches={'warranty':re.search(r'(\d+(?:\.\d+)?)-year structural',text),
        'seat_capacity':re.search(r'rated (\d+) lbs',items[1]['Description']),
        'desk_low':re.search(r'\((\d+(?:\.\d+)?)["-]',items[0]['Description'])}
    facts={k:float(v.group(1)) if v else None for k,v in matches.items()}
    path=folder/'source_records.json';claims=json.loads(path.read_text()) if path.exists() else []
    for k,v in facts.items():
        if v is not None:continue
        relevant=[r for r in claims if r['fact']==k]
        if relevant:
            newest=max(r['revision'] for r in relevant);values={r['value'] for r in relevant if r['revision']==newest}
            if len(values)==1:facts[k]=next(iter(values))
    for row in records or []:
        for provided in row.get('provided',[]):
            k=provided.get('fact_id')
            if k in facts and facts[k] is None:facts[k]=provided['value']
    return facts

def history(folder):
    with sqlite3.connect('file:'+str((folder/'vendor_history.db').resolve())+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        orders=[dict(r) for r in db.execute('select * from past_orders')]
        claims=[dict(r) for r in db.execute('select * from warranty_claims')]
        out=[]
        for v in db.execute('select * from vendors'):
            rows=[r for r in orders if r['vendor_id']==v['vendor_id']]
            out.append(dict(vendor=v['vendor_name'],orders=len(rows),on_time=sum(r['on_time'] for r in rows),
                on_time_pct=sum(r['on_time'] for r in rows)/len(rows)*100,
                mean_quality=sum(r['quality_score'] for r in rows)/len(rows),
                claims=[r for r in claims if r['vendor_id']==v['vendor_id']]))
        return out
