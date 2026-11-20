"""WB12 live CRM removal and email replay; chronology remains supplemental."""
import csv,json,shutil
from pathlib import Path
from .english_packet import RELEASE
from .wb01_native import NATIVE,write_csv,digest,replay
from .wb07_native import call
from .english_wb12 import load,fact
from .wb12_state import records

def bind(folder,variant,answers):
    data=load(variant);shutil.copytree(NATIVE/'data',folder/'data');ids={};rows=[];deleted=[]
    path=folder/'data/processed/customer_relationship_manager_data.csv'
    with path.open() as f:fields=next(csv.reader(f))
    people={r['employee']:r['email'] for r in data['people.json']};aliases={r['email']:people[r['employee']] for r in data['owner_aliases.csv']}
    for i,r in enumerate(records(data,answers)):
        ids[r['id']]=f'{i:08d}'
        if r['deleted']:deleted.append(r['id']);continue
        row={k:'' for k in fields};row.update(customer_id=ids[r['id']],assigned_to_email=aliases[r['owner']],customer_name=r['name'],status='Lead' if r['record_type']=='lead' else 'Customer',notes=json.dumps(dict(authored_id=r['id'],record_type=r['record_type'],raw_owner=r['owner'])))
        rows.append(row)
    write_csv(path,rows,fields)
    # Preserve bundled baseline mail rows: native send adds Timestamp values;
    # an empty baseline produces datetime-only dtype unsupported by its evaluator.
    sessions=[]
    for r in data['engaged_users.csv']+data.get('gap_fill_samples.csv',[]):
        if r['quality']!='accepted' and not (r['sample']=='Z7' and fact(data,'measurement',answers)):continue
        value=int(r['value'])
        if str(value)!=r['value']:raise ValueError('Only integer engaged-count observations have a lossless count projection')
        for i in range(max(1,value)):sessions.append(dict(date_of_visit=r['day'],visitor_id=r['sample']+'-'+str(i),page_views='1',session_duration_seconds='0',traffic_source='authored_count_projection',user_engaged=str(value>0)))
    write_csv(folder/'data/processed/analytics_data.csv',sessions,['date_of_visit','visitor_id','page_views','session_duration_seconds','traffic_source','user_engaged'])
    (folder/'data/raw/email_addresses.csv').write_text('\n'.join(people.values())+'\n')
    binding=dict(case='WB12',variant=variant,answers=answers,record_ids=ids,initially_deleted=deleted,source_data=data,original_identity=json.loads((RELEASE/'WB12/SOURCE.json').read_text()),native_background_emails='Preserved bundled email CSV; unchanged baseline, additions represent authored sent state',provenance='Authored live-row CRM and engaged-count projection',limitations=['Deleted records omitted from native CRM and retained as supplemental tombstones','Record type retained in status/notes; original full facts remain supplemental','Delete-before-email order is checked supplementally: native final-state evaluator ignores cross-domain order','Engaged visits are synthetic count-preserving rows'])
    binding['csv_sha256']={str(p.relative_to(folder)):digest(p) for p in (folder/'data').rglob('*.csv')}
    (folder/'binding.json').write_text(json.dumps(binding,indent=2)+'\n');return binding
def captured(events,binding):
    actions=[];deleted=set(binding['initially_deleted'])
    for e in events:
        a=e.get('action')
        if not isinstance(a,dict):
            if e.get('before')!=e.get('after'):raise ValueError('Unattributed state change')
            continue
        if a.get('tool')!='call' or 'error' in e['reply']:continue
        args=a['arguments']
        if a.get('name')=='delete_record':
            identity=args['id']
            if identity not in deleted:
                actions.append(call('customer_relationship_manager.delete_customer',dict(customer_id=binding['record_ids'][identity])));deleted.add(identity)
        elif a.get('name')=='send_email':actions.append(call('email.send_email',dict(recipient=args['to'],subject=args['subject'],body=args['body'])))
    return actions

def reference(target,binding):
    return [call('customer_relationship_manager.delete_customer',dict(customer_id=binding['record_ids'][i])) for i in target['delete']]+[call('email.send_email',dict(recipient=target['to'],subject=target['subject'],body=target['body']))]

def evaluate_engine(engine,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);binding=bind(output,engine.variant,engine.answers)
    try:actions=captured(engine.events,binding)
    except (ValueError,KeyError,TypeError) as exc:return dict(status='failed',native_api_actions=0,original_algorithm_calls=0,unsupported_projection=str(exc))
    result=replay(output,[dict(label='live_host_captured_effects',actions=actions)],reference(engine.checker.target,binding))
    return dict(status='passed' if result['predictions'][0]['native_evaluator_passed'] else 'failed',native_api_actions=len(actions),original_algorithm_calls=result['original_evaluator_runs'],evidence=str(output/'result.json'),layer='bundled_native_effect_replay_on_authored_world',requires_supplemental_order_check=True)
