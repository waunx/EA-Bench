from copy import deepcopy
from datetime import datetime,timedelta
from itertools import product


def note_mail(d,p):
    rows=[r for r in d['read_notes'] if r['id']=='N2' and (not p['approved_only'] or r['approved'])]
    row=max(rows,key=lambda r:r['revision'])
    selected=dict(id=row['id'],revision=row['revision'])
    exported=dict(filename='note-N2.txt',content='\n'.join(x['text'] for x in row['paragraphs'] if not (p['omit_internal'] and x['internal'])))
    mail=deepcopy(d['read_draft'])
    mail['attachments']=(mail['attachments'] if p['keep_attachments'] else [])+[exported['filename']]
    mail['cc']=['owner@example.org'] if p['cc_owner'] else []
    mail['sent']=True
    return dict(select_note=selected,export_note=exported,compose_mail=mail,report=dict(file=exported,message=mail))


def artist_follow(d,p):
    candidates=sorted({r['artist_id'] for r in d['read_recommendations'] if r['age_days']<=p['window'] and (r['channel']=='email' or p['include_sms'])})
    filtered=[k for k in candidates if not (p['exclude_muted'] and d['read_artists'][k]['muted'])]
    old=set(d['read_follows'])
    final=set(filtered)|(old if p['keep_existing'] else set())
    changes=dict(add=sorted(final-old),remove=sorted(old-final))
    return dict(candidate_ids=candidates,filtered_ids=filtered,changes=changes,report=dict(following=sorted(final),changes=changes))


def trip_checkout(d,p):
    offers={r['id']:r for r in d['read_offers']}
    ids=sorted(k for k,r in offers.items() if r['arrival']<=5 and (not r['substitute'] or p['substitution']))
    skus=sorted(d['read_order'])
    def costs(chosen):
        goods=sum(offers[k]['price']*d['read_order'][s] for s,k in zip(skus,chosen))
        groups={}
        tax=0
        for s,k in zip(skus,chosen):
            r=offers[k]
            groups[r['vendor'] if p['freight_group']=='vendor' else s]=r['freight']
            tax+=0 if p['tax_included'] else r['tax_each']*d['read_order'][s]
        freight=sum(groups.values())
        credit=min(d['read_wallet']['credit'],goods+freight+tax) if p['use_credit'] else 0
        return dict(goods=goods,freight=freight,tax=tax,credit_used=credit,due=goods+freight+tax-credit)
    choices=product(*[[k for k in ids if offers[k]['sku']==s] for s in skus])
    _,chosen=min((costs(c)['due'],c) for c in choices)
    plan=dict(zip(skus,chosen));cost=costs(chosen)
    return dict(eligible_offers=ids,purchase_plan=plan,costing=cost,report=dict(amount_due=cost['due'],purchase=plan))


def flight_alarms(d,p):
    flight=datetime.fromisoformat(d['read_flights']['F1']['departure_utc'])
    times=[(flight-timedelta(minutes=n)+timedelta(hours=p['utc_offset'])).strftime('%Y-%m-%d %H:%M') for n in (120,125,130)]
    plan=[dict(id=f'NEW{i+1}',flight='F1',device=p['device'],time_local=t,sound=p['sound'],label='Flight F1') for i,t in enumerate(times)]
    removed=sorted(r['id'] for r in d['read_alarms'] if p['replace_old'] and r['flight']=='F1' and r['device']==p['device'])
    diff=dict(remove=removed,add=plan)
    final=sorted([r for r in d['read_alarms'] if r['id'] not in removed]+plan,key=lambda r:r['id'])
    return dict(times=times,alarm_plan=plan,state_diff=diff,report=dict(alarms=final))


def music_mail(d,p):
    tracks={r['id']:r for r in d['read_playlist']}
    filtered=sorted(k for k,r in tracks.items() if not (p['exclude_explicit'] and r['explicit']))
    groups={}
    for k in filtered:groups.setdefault(tracks[k]['base_id'],[]).append(k)
    wanted='live' if p['prefer_live'] else 'studio'
    versions=sorted(min(ids,key=lambda k:(tracks[k]['version']!=wanted,k)) for ids in groups.values())
    key=(lambda k:(tracks[k]['artist'],k)) if p['order']=='artist' else (lambda k:(-tracks[k]['added_day'],k))
    ordered=sorted(versions,key=key)
    lines=[tracks[k]['artist']+' - '+tracks[k]['title']+(' '+tracks[k]['url'] if p['links'] else '') for k in ordered]
    mail=deepcopy(d['read_draft']);mail['body']+='\n'+'\n'.join(lines);mail['sent']=True
    return dict(filtered=filtered,versions=versions,ordered=ordered,compose_mail=mail,report=dict(message=mail))


def order_returns(d,p):
    selected=[r for r in d['read_items'] if r['id'] in ('I1','I2')]
    groups={}
    for r in selected:groups.setdefault(r[p['group_labels']],[]).append(r['id'])
    labels=[dict(group=k,items=sorted(v),carrier='USPS',fee=2) for k,v in sorted(groups.items())]
    goods=sum(r['price'] for r in selected)
    shipping=sum(d['read_orders'][k]['original_shipping'] for k in {r['order'] for r in selected}) if p['refund_shipping'] else 0
    restocking=0 if p['waive_fee'] else sum(r['restocking_fee'] for r in selected if r['opened'])
    fees=2*len(labels)
    refund=dict(goods=goods,shipping=shipping,restocking=restocking,label_fees=fees,total=goods+shipping-restocking-fees,destination=p['destination'])
    ids=sorted(r['id'] for r in selected)
    return dict(return_items=ids,labels=labels,refund=refund,report=dict(returned=ids,kept=sorted(r['id'] for r in d['read_items'] if r['id'] not in ids),labels=labels,refund=refund))


SOLVERS={'aw_note_mail':note_mail,'aw_artist_follow':artist_follow,'aw_trip_checkout':trip_checkout,'aw_flight_alarms':flight_alarms,'aw_music_mail':music_mail,'aw_order_returns':order_returns}
