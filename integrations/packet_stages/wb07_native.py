"""WB07 accepted aggregate metrics and latest task revisions bound to native CSVs."""
import json,shutil,subprocess,sys
from pathlib import Path
from decimal import Decimal
from .wb01_native import NATIVE,write_csv,digest
from .english_packet import RELEASE
from .english_wb07 import load,fact
from .wb07_state import task_records
BOARDS={'FRONT_END':'Front end','BACKEND':'Back end','ARCHIVE':'ARCHIVE'}
STATUSES={'completed':'Completed','done':'Completed','reopened':'Reopened','backlog':'Backlog','in progress':'In Progress','in review':'In Review'}
def call(name,args):return name+'('+', '.join(k+'='+repr(v) for k,v in args.items())+')'
def fields(record):
    return dict(task_name=record['title'],assigned_to_email=record['owner'],list_name=STATUSES[record['status']],due_date=record['due'] or '',board=BOARDS[record['board']])
def bind(folder,variant,answers):
    data=load(variant);shutil.copytree(NATIVE/'data',folder/'data');ids={};rows=[]
    for record in task_records(data,answers):
        ids[record['task']]=f'{len(rows):08d}';rows.append(dict(task_id=ids[record['task']],**fields(record)))
    write_csv(folder/'data/processed/project_tasks.csv',rows,['task_id','task_name','assigned_to_email','list_name','due_date','board'])
    effective={}
    for r in data['metric_partitions.csv']+data.get('metric_history.csv',[]):
        if r['quality']!='accepted' and not (r['quality']=='BF7_pending' and fact(data,'qa',answers)):continue
        if r['partition'] not in effective or int(r['revision'])>int(effective[r['partition']]['revision']):effective[r['partition']]=r
    sessions=[]
    for r in effective.values():
        n=fact(data,'p2_sessions',answers) if r['partition']=='P2' and r['revision']=='1' else int(r['sessions'])
        for i in range(n):sessions.append(dict(date_of_visit=r['day'],visitor_id=f"{r['partition']}-{i}",page_views='1',session_duration_seconds=str(Decimal(r['total_ms'])/Decimal(n)/1000),traffic_source='authored_aggregate_projection',user_engaged='False'))
    write_csv(folder/'data/processed/analytics_data.csv',sessions,['date_of_visit','visitor_id','page_views','session_duration_seconds','traffic_source','user_engaged'])
    binding=dict(case='WB07',variant=variant,answers=answers,task_ids=ids,source_data=data,original_identity=json.loads((RELEASE/'WB07/SOURCE.json').read_text()),provenance='Authored aggregate-to-session and latest-task projection, not observed native sessions',limitations=['Synthetic equal-duration rows preserve session count and mean only','Archived board and reopened state retained as baseline labels; native create restrictions unchanged','Revision/quality provenance stays supplemental','Task due null maps to blank baseline CSV'])
    binding['csv_sha256']={str(p.relative_to(folder)):digest(p) for p in (folder/'data').rglob('*.csv')}
    (folder/'binding.json').write_text(json.dumps(binding,indent=2)+'\n');return binding
def captured(events,binding):
    ids=dict(binding['task_ids']);actions=[]
    for e in events:
        a=e['action']
        if a is None:
            if e.get('before')!=e.get('after'):raise ValueError('Unattributed state change')
            continue
        name=a.get('name')
        if a.get('tool')!='call' or name not in {'create_task','update_task'} or 'error' in e['reply']:continue
        tid=e['reply']['task'];record=next(r for r in e['after']['tasks'] if r['task']==tid)
        values=fields(record)
        if name=='create_task':
            ids[tid]=f'{len(ids):08d}';actions.append(call('project_management.create_task',values))
        else:
            before=next(r for r in e['before']['tasks'] if r['task']==tid);old=fields(before)
            for key,value in values.items():
                if value!=old[key]:
                    if not value:raise ValueError('Native update cannot clear a task field')
                    actions.append(call('project_management.update_task',dict(task_id=ids[tid],field=key,new_value=value)))
    return actions

def references(target):
    if not target['create']:return [[]]
    e=target['create'][0]
    return [[call('project_management.create_task',dict(task_name=e['title'],assigned_to_email=owner,list_name='Backlog',due_date=e['due'],board='Front end'))] for owner in target['permitted_assignees']]
def replay(folder,predictions,expected):
    (folder/'request.json').write_text(json.dumps(dict(predictions=predictions,expected=expected),indent=2)+'\n')
    p=subprocess.run([sys.executable,str(Path(__file__).with_name('wb07_native_worker.py')),str(NATIVE)],cwd=folder,text=True,capture_output=True)
    (folder/'stdout.log').write_text(p.stdout);(folder/'stderr.log').write_text(p.stderr)
    if p.returncode:raise RuntimeError(p.stderr)
    return json.loads((folder/'result.json').read_text())

def evaluate_engine(engine, output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);binding=bind(output,engine.variant,engine.answers)
    try:actions=captured(engine.events,binding)
    except (ValueError,KeyError,TypeError) as exc:return dict(status='failed',native_api_actions=0,original_algorithm_calls=0,unsupported_projection=str(exc))
    result=replay(output,[dict(label='live_host_captured_effects',actions=actions)],references(engine.checker.target))
    return dict(status='passed' if result['predictions'][0]['native_evaluator_passed'] else 'failed',native_api_actions=len(actions),original_algorithm_calls=result['original_evaluator_runs'],evidence=str(output/'result.json'),layer='bundled_native_effect_replay_on_authored_world')
