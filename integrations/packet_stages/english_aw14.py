"""AW14 usage-period billing, effective credits and resident shares."""
import csv,json
from .english_packet import inputs
class NeedFact(Exception):pass

def load(variant):
    data={}
    for p in inputs('AW14',variant).iterdir():
        if p.suffix=='.csv':
            with p.open(newline='') as f:data[p.name]=list(csv.DictReader(f))
        elif p.suffix=='.json':data[p.name]=json.loads(p.read_text())
        else:data[p.name]=p.read_text()
    return data

def observed(data):
    note=data.get('case_decision.md','')
    status=True if 'is currently effective.' in note else False if 'is not currently effective.' in note else None
    march=next(r['amount_cents'] for r in data['bills.csv'] if r['bill']=='B03')
    credit=next(r['amount_cents'] for r in data['credit_notice.csv'] if r['credit']=='CR2')
    return dict(active=status,march=int(march) if march else None,credit=int(credit) if credit else None)

def fact(data,key,answers):
    value=observed(data)[key]
    if value is not None:return value
    records=[r for r in data.get('source_records.json',[]) if r['fact']==key]
    if records:
        top=max(r['revision'] for r in records);values={r['value'] for r in records if r['revision']==top}
        if len(values)==1:return next(iter(values))
    if key not in answers:raise NeedFact(key)
    return answers[key]

def expenses(data):
    rows=[]
    for raw in data['existing_expenses.csv']+data.get('expense_history.csv',[]):
        row=dict(raw);row['amount_cents']=int(row['amount_cents']);row['shares']=json.loads(row['shares']);row['deleted']=row['deleted']=='1'
        rows.append(row)
    return rows

def entry(data,month,amount):
    people=sorted(r['person'] for r in data['roommates.csv'] if r['resident_from']<=month<=r['resident_through'])
    if not people or 'SELF' not in people:raise NeedFact('Resident membership')
    q,rem=divmod(amount,len(people));year,m=month.split('-')
    return dict(category='electricity',usage_month=month,amount_cents=amount,deleted=False,
        group=data['account_context.json']['group'],payer='SELF',note='electricity bill for '+m+'/'+year[2:],
        shares={p:q+(i<rem) for i,p in enumerate(people)})

def solve(data,answers):
    year=data['account_context.json']['snapshot_date'][:4];months={}
    for r in data['bills.csv']+data.get('statement_archive.csv',[]):
        month=r['usage_month']
        if not month.startswith(year+'-'):continue
        amount=fact(data,'march',answers) if r['bill']=='B03' else int(r['amount_cents'])
        if r['bill']=='B02' and fact(data,'active',answers):amount-=fact(data,'credit',answers)
        other=data.get('credit_archive.json')
        if other and other['effective'] and other['bill']==r['bill']:amount-=other['amount_cents']
        if amount<0:raise ValueError('Credit exceeds bill amount')
        if month in months:raise NeedFact('Duplicate usage-month bills')
        months[month]=amount
    actions=[];shares={};existing=expenses(data)
    for month,amount in sorted(months.items()):
        desired=entry(data,month,amount)
        current=[r for r in existing if r['group']==desired['group'] and r['category']=='electricity' and r['usage_month']==month and not r['deleted']]
        if len(current)>1:raise NeedFact('Duplicate current expenses')
        if not current:actions.append(dict(op='create',month=month,amount_cents=amount))
        elif {k:v for k,v in current[0].items() if k!='expense'}!=desired:
            actions.append(dict(op='update',expense=current[0]['expense'],month=month,amount_cents=amount))
        shares[month]=desired['shares']
    return dict(actions=actions,total_cents=sum(months.values()),shares=shares,protected=['E01','E90'])
