"""Empirical baselines use only independently audited grounded successes."""
from integrations.packet_audit.common import read,sha

def attach(run,item,source,row):
    mpath=source/'metrics.json';apath=run/'audit'/row['model']/(item['id']+'.json')
    version=read(run/'audit/implementation.json',{}).get('signature');a=read(apath,{})
    valid=row['status'] in {'submitted','action_budget_exhausted'}
    status='pending' if valid else 'not_applicable'
    if valid and a.get('audit_signature')==version and a.get('metrics_sha256')==sha(mpath) and a.get('trace_sha256')==sha(source/'dialogue.jsonl'):status=a['status']
    row.update(audit_status=status,information_sufficient=a.get('information_sufficient') if status=='complete' else None,grounded_success=a.get('grounded_success') if status=='complete' else None)
    if status in {'complete','needs_review','annotation_error'}:
        for k in ['requested_information_items','question_rounds','duplicate_requests','actual_tool_calls','semantic_model_calls','self_report_disagreements','unsolicited_topics']:row[k]=a.get(k)
    return a if status in {'complete','needs_review'} else None

def baselines(rows):
    groups={}
    for r in rows:
        r.update(extra_tool_calls=None,extra_information_items=None,extra_question_rounds=None,empirical_baseline_models=0)
        if r.get('audit_status')=='complete' and r.get('grounded_success'):groups.setdefault(r['id'],[]).append(r)
    for rr in groups.values():
        tools=min(r['actual_tool_calls'] for r in rr);info=min(r['requested_information_items'] for r in rr);rounds=min(r['question_rounds'] for r in rr)
        for r in rr:
            r.update(extra_tool_calls=r['actual_tool_calls']-tools,extra_information_items=r['requested_information_items']-info,extra_question_rounds=r['question_rounds']-rounds,empirical_baseline_models=len(rr),empirical_baseline=dict(tools=tools,information_items=info,question_rounds=rounds))

def summary(rows):
    eligible=[r for r in rows if r.get('grounded_success') and r.get('audit_status')=='complete']
    mean=lambda key:sum(r[key] for r in eligible)/len(eligible) if eligible else None
    return dict(audit_complete=sum(r.get('audit_status')=='complete' for r in rows),audit_pending=sum(r.get('audit_status')=='pending' for r in rows),audit_review=sum(r.get('audit_status')=='needs_review' for r in rows),audit_errors=sum(r.get('audit_status')=='annotation_error' for r in rows),grounded=sum(bool(r.get('grounded_success')) for r in rows),extra_tools=mean('extra_tool_calls'),extra_info=mean('extra_information_items'),extra_rounds=mean('extra_question_rounds'),efficiency_n=len(eligible),comparable_n=sum(r.get('empirical_baseline_models',0)>1 for r in eligible),semantic_dialogue_audits=sum(r.get('audit_status')=='complete' and bool(r.get('semantic_model_calls')) for r in rows))
