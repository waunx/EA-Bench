from copy import deepcopy
from datetime import datetime,timedelta


def mail_cleanup(d,p):
    selected=sorted(r['id'] for r in d['read_emails'] if r['sender']=='team@example.org' and r['folder']=='inbox' and r['age_days']>=p['retention'] and (p['include_read'] or not r['read']) and (not p['protect_starred'] or not r['starred']))
    changes={k:p['folder'] for k in selected}
    final=deepcopy(d['read_emails'])
    for r in final:
        if r['id'] in changes:r['folder']=changes[r['id']]
    return dict(eligible=selected,changes=changes,report=dict(emails=sorted(final,key=lambda r:r['id'])))


def calendar_shift(d,p):
    candidates=sorted([r for r in d['read_calendar'] if r['series']=='S1'],key=lambda r:r['start'])
    selected=[r['id'] for r in (candidates if p['all_series'] else candidates[:1])]
    changed={}
    notices=[]
    for r in candidates:
        if r['id'] not in selected:continue
        start=(datetime.fromisoformat(r['start'])+timedelta(minutes=p['delay'])).strftime('%Y-%m-%d %H:%M')
        end=(datetime.fromisoformat(r['end'])+timedelta(minutes=p['delay'])).strftime('%Y-%m-%d %H:%M') if p['keep_duration'] else r['end']
        changed[r['id']]=dict(start=start,end=end)
        if p['notify']:notices.append(dict(event=r['id'],attendees=sorted(r['attendees']),start=start))
    final=deepcopy(d['read_calendar'])
    for r in final:
        if r['id'] in changed:r.update(changed[r['id']])
    return dict(selected=selected,rescheduled=changed,notifications=notices,report=dict(calendar=sorted(final,key=lambda r:r['id']),notifications=notices))


def crm_transfer(d,p):
    selected=[]
    for r in d['read_crm']:
        interest=r['interest']=='software' if p['interest_match']=='exact' else 'software' in r['interest'].split(';')
        if r['owner']=='U1' and r['status']==p['status'] and interest and (r['active'] or p['include_inactive']):selected.append(r['id'])
    selected.sort();plan={k:p['new_owner'] for k in selected}
    final=deepcopy(d['read_crm'])
    for r in final:
        if r['id'] in plan:r['owner']=plan[r['id']]
    final.sort(key=lambda r:r['id'])
    return dict(selected=selected,transfer_plan=plan,updated_crm=final,report=dict(crm=final,transferred=selected))


def project_handoff(d,p):
    statuses=['in_progress']+(['review'] if p['include_review'] else [])
    selected=sorted(r['id'] for r in d['read_tasks'] if r['owner']=='U1' and r['status'] in statuses and (not p['exclude_blocked'] or not r['blocked']) and (not p['overdue_only'] or r['due_day']<0))
    handoff={k:p['new_owner'] for k in selected}
    final=deepcopy(d['read_tasks'])
    for r in final:
        if r['id'] in handoff:r['owner']=handoff[r['id']]
    final.sort(key=lambda r:r['id'])
    return dict(selected=selected,handoff=handoff,updated_board=final,report=dict(tasks=final,transferred=selected))


def analytics_plot(d,p):
    localized={r['id']:(datetime.fromisoformat(r['utc'])+timedelta(hours=p['utc_offset'])).strftime('%Y-%m-%d') for r in d['read_metrics']}
    records=[r for r in d['read_metrics'] if p['start_date']<=localized[r['id']]<='2026-09-02' and (p['include_internal'] or not r['internal'])]
    groups={}
    for r in records:groups.setdefault(localized[r['id']],[]).append(r)
    daily={}
    for day,rows in sorted(groups.items()):
        visits=sum(r['visits'] for r in rows)
        numerator=sum(r['duration_seconds']*(r['visits'] if p['weighted'] else 1) for r in rows)
        denominator=visits if p['weighted'] else len(rows)
        daily[day]=dict(visits=visits,mean_duration_ms=(2*numerator*1000+denominator)//(2*denominator))
    chart=dict(type='bar',dates=list(daily),visits=[r['visits'] for r in daily.values()],mean_duration_ms=[r['mean_duration_ms'] for r in daily.values()])
    return dict(localized=localized,filtered=sorted(r['id'] for r in records),daily=daily,chart_spec=chart,report=dict(charts=chart,daily=daily))


def capacity_lead(d,p):
    staff={r['id']:r for r in d['read_staff']}
    eligible=sorted(k for k,r in staff.items() if p['include_away'] or not r['away'])
    workload=dict.fromkeys(eligible,0)
    for r in d['read_tasks']:
        if r['owner'] in workload and (r['status']=='in_progress' or (r['status']=='review' and p['include_review'])):
            workload[r['owner']]+=r['points'] if p['weighted'] else 1
    owner=min(eligible,key=lambda k:(workload[k],staff[k]['priority'] if p['tie_break']=='priority' else 0,k))
    lead=dict(id='CNEW',owner=owner,status='Lead')
    final=sorted(deepcopy(d['read_crm'])+[lead],key=lambda r:r['id'])
    return dict(eligible_staff=eligible,workload=workload,assignee=dict(owner=owner),new_lead=lead,state_patch=final,report=dict(crm=final,assigned_to=owner))


SOLVERS={'wb_mail_cleanup':mail_cleanup,'wb_calendar_shift':calendar_shift,'wb_crm_transfer':crm_transfer,'wb_project_handoff':project_handoff,'wb_analytics_plot':analytics_plot,'wb_capacity_lead':capacity_lead}
