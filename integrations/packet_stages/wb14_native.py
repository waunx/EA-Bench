"""WB14 authored cross-domain branches projected to actual native CSV APIs."""
import csv,json,shutil
from pathlib import Path
from .english_packet import RELEASE
from .wb01_native import NATIVE,write_csv,digest,replay,stamp,translate
from .wb07_native import call
from .english_wb14 import load,fact,dates
from .wb14_state import calendar,records

def bind(folder,variant,answers):
    data=load(variant);shutil.copytree(NATIVE/'data',folder/'data');calendar_ids={};rows=[]
    for r in calendar(data,answers):
        if r['owner']!='self' or r['status']=='cancelled':continue
        calendar_ids[r['event']]=f'{len(rows):08d}';rows.append(dict(event_id=calendar_ids[r['event']],event_name=r['title'],participant_email=','.join(r['attendees']),event_start=stamp(r['day'],r['start']),duration=str(r['end']-r['start'])))
    write_csv(folder/'data/processed/calendar_events.csv',rows,['event_id','event_name','participant_email','event_start','duration'])
    owners={r['alias']:r['current_email'] for r in data['people_aliases.csv']};owners.update({r['contact']:r['email'] for r in data['contacts.csv']})
    path=folder/'data/processed/customer_relationship_manager_data.csv'
    with path.open() as f:fields=next(csv.reader(f))
    rows=[];ids={};deleted=[]
    for i,r in enumerate(records(data,answers)):
        ids[r['id']]=f'{i:08d}'
        if r['deleted']:deleted.append(r['id']);continue
        row={k:'' for k in fields};row.update(customer_id=ids[r['id']],assigned_to_email=owners[r['owner']],customer_name=r['id'],status='Lead' if r['record_type']=='lead' else 'Customer',notes=json.dumps(r));rows.append(row)
    write_csv(path,rows,fields)
    # Preserve bundled baseline mail rows: native send adds Timestamp values;
    # an empty baseline produces datetime-only dtype unsupported by its evaluator.
    team=sorted({r['email'] for r in data['contacts.csv']});tasks=[dict(task_id=f'{i:08d}',task_name='Native binding team registry',assigned_to_email=email,list_name='Completed',due_date='2023-11-30',board='Back end') for i,email in enumerate(team)]
    write_csv(folder/'data/processed/project_tasks.csv',tasks,['task_id','task_name','assigned_to_email','list_name','due_date','board'])
    (folder/'data/raw/email_addresses.csv').write_text('\n'.join(sorted(set(owners.values())))+'\n')
    effective={}
    for r in data['visits.csv']+data.get('visits_history.csv',[]):
        if r['quality']!='accepted' and not (r['quality']=='QC2_pending' and fact(data,'qa',answers)):continue
        if r['bucket'] not in effective or int(r['revision'])>int(effective[r['bucket']]['revision']):effective[r['bucket']]=r
    visits=[]
    for r in effective.values():
        for i in range(int(r['visits'])):visits.append(dict(date_of_visit=r['day'],visitor_id=r['bucket']+'-'+str(i),page_views='1',session_duration_seconds='0',traffic_source='authored_visit_count_projection',user_engaged='False'))
    write_csv(folder/'data/processed/analytics_data.csv',visits,['date_of_visit','visitor_id','page_views','session_duration_seconds','traffic_source','user_engaged'])
    binding=dict(case='WB14',variant=variant,answers=answers,record_ids=ids,calendar_ids=calendar_ids,initially_deleted=deleted,owner_aliases=owners,source_data=data,original_identity=json.loads((RELEASE/'WB14/SOURCE.json').read_text()),native_background_emails='Preserved bundled email CSV; unchanged baseline, additions represent authored sent state',provenance='Authored supplemental CSV projection',technical_team_registry=tasks,limitations=['Workspaces share native board name Front end; exact board ID remains supplemental','Team registry bridge tasks enable native assignee validation and must stay unchanged','Cancelled/other-owner calendar and deleted CRM rows remain supplemental metadata','Native final-state comparison cannot certify email-before-transfer sequence','Visits are synthetic count-preserving rows, not native observations'])
    binding['csv_sha256']={str(p.relative_to(folder)):digest(p) for p in (folder/'data').rglob('*.csv')}
    (folder/'binding.json').write_text(json.dumps(binding,indent=2)+'\n');return binding

def captured(events,binding):
    actions=[];owners=binding['owner_aliases'];boards={r['id']:r['name'] for r in binding['source_data']['boards.csv']}
    for e in events:
        a=e.get('action')
        if not isinstance(a,dict):
            if e.get('before')!=e.get('after'):raise ValueError('Unattributed state change')
            continue
        if a.get('tool')!='call' or 'error' in e['reply']:continue
        args=a['arguments'];name=a.get('name')
        if name=='create_event':actions.append(call('calendar.create_event',translate(args)))
        elif name=='create_task':
            owner=owners.get(args['owner'],args['owner']);actions.append(call('project_management.create_task',dict(task_name=args['title'],assigned_to_email=owner,list_name=args['list'].title(),due_date=args['due'],board=boards[args['board']])))
        elif name=='send_email':actions.append(call('email.send_email',dict(recipient=args['to'],subject=args['subject'],body=args['body'])))
        elif name=='transfer_record':
            if args['id'] in binding['initially_deleted']:raise ValueError('Native projection cannot transfer tombstoned records')
            actions.append(call('customer_relationship_manager.update_customer',dict(customer_id=binding['record_ids'][args['id']],field='assigned_to_email',new_value=owners.get(args['owner'],args['owner']))))
    return actions
def reference(target,binding):
    if target['branch']=='task_and_meeting':
        return [call('project_management.create_task',dict(task_name=target['task'],assigned_to_email=target['owner'],list_name=target['list'],due_date=target['due'],board='Front end')),call('calendar.create_event',dict(event_name=target['meeting'],participant_email=target['owner'],event_start=stamp(dates(binding['source_data'])[1],target['start']),duration=str(target['end']-target['start'])))]
    return [call('email.send_email',dict(recipient=target['owner'],subject=target['subject'],body=target['body']))]+[call('customer_relationship_manager.update_customer',dict(customer_id=binding['record_ids'][i],field='assigned_to_email',new_value=target['owner'])) for i in target['crm_updates']]

def evaluate_engine(engine,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);binding=bind(output,engine.variant,engine.answers)
    try:actions=captured(engine.events,binding)
    except (ValueError,KeyError,TypeError) as exc:return dict(status='failed',native_api_actions=0,original_algorithm_calls=0,unsupported_projection=str(exc))
    result=replay(output,[dict(label='live_host_captured_effects',actions=actions)],reference(engine.checker.target,binding))
    return dict(status='passed' if result['predictions'][0]['native_evaluator_passed'] else 'failed',native_api_actions=len(actions),original_algorithm_calls=result['original_evaluator_runs'],evidence=str(output/'result.json'),layer='bundled_native_effect_replay_on_authored_world',requires_supplemental_order_and_workspace_checks=True)
