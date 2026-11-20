"""AW08 final lunch balances and request reconciliation."""
import csv
import json
from .english_packet import inputs


class NeedFact(Exception):pass


def load(variant):
    data={}
    for path in inputs('AW08',variant).iterdir():
        if path.suffix=='.csv':
            with path.open(newline='') as f:data[path.name]=list(csv.DictReader(f))
        elif path.suffix=='.json':data[path.name]=json.loads(path.read_text())
        else:data[path.name]=path.read_text()
    return data


def fact(data,raw,key,answers):
    if raw not in ('',None):return raw
    records=data.get(key+'_records.json',[])
    if records:
        revision=max(r['revision'] for r in records)
        values={r['value'] for r in records if r['revision']==revision}
        if len(values)==1:return next(iter(values))
    if key not in answers:raise NeedFact(key)
    return answers[key]


def requests(data):
    return data['request_register.csv']+data.get('request_archive.csv',[])


def solve(data,answers):
    latest={}
    for row in data['meal_replies.csv']+data.get('meal_reply_archive.csv',[]):
        if row['person'] not in latest or int(row['revision'])>int(latest[row['person']]['revision']):latest[row['person']]=row
    food={k:int(fact(data,r['food_cents'],'a_food',answers)) for k,r in latest.items()}
    receipt=data['receipt.json']
    if receipt!=dict(event='LUNCH-0928',delivery_cents=1000,tip_percent=15):raise ValueError('Receipt differs from original request')
    if sum(food.values())*15%100:raise ValueError('Tip requires a separate cent-rounding convention')
    tip=sum(food.values())*15//100; shared=tip+1000; q,rem=divmod(shared,len(food))
    allocation=fact(data,data['cent_allocation.json']['order'],'rounding',answers) if rem else 'ascending'
    ids=sorted(food,reverse=allocation=='descending')
    shares={k:q+(i<rem) for i,k in enumerate(ids)}
    owed={k:food[k]+shares[k] for k in food}; paid={k:0 for k in food}
    for row in data['payments.csv']+data.get('payment_journal.csv',[]):
        event=fact(data,row['event_ref'],'pay17_event',answers)
        if event!=receipt['event']:continue
        status=fact(data,row['status'],'pay18_state',answers)
        if status!='settled':continue
        amount=int(fact(data,row['amount_cents'],'pay17_amount',answers))
        paid[row['person']]+=amount; owed[row['person']]-=amount
    if any(v<0 for v in owed.values()):raise ValueError('Overpayment needs a refund instruction')
    new={k:v for k,v in owed.items() if k!='SELF' and v>0}; keep=[]; cancel=[]; matched=set()
    for row in requests(data):
        if row['event_ref']!=receipt['event']:
            keep.append(row['request']);continue
        state=fact(data,row['state'],'req1_state',answers)
        if state!='pending':continue
        person=row['person']
        if (int(row['amount_cents'])==owed[person] and owed[person]>0 and person not in matched
                and row['public']=='true' and row['note']=='Lunch Meeting Order'):
            keep.append(row['request']);new.pop(person,None);matched.add(person)
        else:cancel.append(row['request'])
    assert sum(shares.values())==shared
    assert sum(owed.values())+sum(paid.values())==sum(food.values())+tip+1000
    return dict(new_requests=new,cancel_requests=sorted(cancel),keep_requests=sorted(keep),
                food=food,shares=shares,paid=paid,owed=owed,shared=shared,public=True,note='Lunch Meeting Order')


def actions(result):
    return {k:result[k] for k in ['new_requests','cancel_requests','keep_requests']}
