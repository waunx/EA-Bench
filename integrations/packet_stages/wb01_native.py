"""WB01 authored CSV binding to actual bundled WorkBench API/evaluator."""
from pathlib import Path
import csv, hashlib, json, shutil, subprocess, sys
from .english_packet import ROOT, RELEASE
from .english_wb01 import load, fact, dates
from .wb01_state import calendar
NATIVE = ROOT/'data/native/workbench'
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write_csv(path, rows, fields):
    with path.open('w', newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
def stamp(day, minute): return f'{day} {minute//60:02d}:{minute%60:02d}:00'
def translate(args):
    if args['owner']!='self' or len(args['attendees'])!=1:
        raise ValueError('Native WB01 binding requires self calendar and exactly one participant')
    return dict(event_name=args['title'],participant_email=args['attendees'][0],event_start=stamp(args['day'],args['start']),duration=str(args['end']-args['start']))
def action(kwargs):
    return 'calendar.create_event('+', '.join(k+'='+repr(v) for k,v in kwargs.items())+')'
def bind(folder, variant, answers):
    data=load(variant);today,since,tomorrow=dates(data)
    shutil.copytree(NATIVE/'data',folder/'data')
    identities={};rows=[]
    for row in calendar(data,answers):
        if row['owner']!='self':continue
        identity=f'{len(rows):08d}';identities[row['event']]=identity
        rows.append(dict(event_id=identity,event_name=row['title'],participant_email=','.join(row['attendees']),event_start=stamp(row['day'],row['start']),duration=str(row['end']-row['start'])))
    write_csv(folder/'data/processed/calendar_events.csv',rows,['event_id','event_name','participant_email','event_start','duration'])
    path=folder/'data/processed/customer_relationship_manager_data.csv'
    with path.open() as stream: fields=next(csv.reader(stream))
    customers=[];customer_ids={}
    for i,customer in enumerate(data['customer_directory.csv']):
        cid=customer['customer'];customer_ids[cid]=f'{i:08d}';owners=[]
        for assignment in data['owner_history.csv']+data.get('owner_archive.csv',[]):
            start=assignment['from'] or fact(data,'handover',answers)
            end=assignment['to'] or fact(data,'handover',answers)
            if assignment['customer']==cid and start<=tomorrow<end:owners.append(assignment['email'])
        contacts=[]
        for event in data['contact_events.csv']+data.get('campaign_events.csv',[]):
            connected=event['result']=='connected'
            if event['event']=='CALL7':connected=fact(data,'connected',answers)
            if event['customer']==cid and event['kind']=='conversation' and connected:contacts.append(event['date'])
        record={k:'' for k in fields};record.update(customer_id=customer_ids[cid],customer_name=customer['name'],assigned_to_email=owners[0] if len(owners)==1 else '',last_contact_date=max(contacts,default=''),notes=json.dumps(dict(company=customer['company'],authored_customer=cid)))
        customers.append(record)
    write_csv(path,customers,fields)
    emails=sorted({r['email'] for r in data['owner_history.csv']+data.get('owner_archive.csv',[])})
    (folder/'data/raw/email_addresses.csv').write_text('\n'.join(emails)+'\n')
    binding=dict(case='WB01',variant=variant,answers=answers,calendar_ids=identities,customer_ids=customer_ids,source_data=data,provenance='Authored supplemental projection; not original native snapshot',excluded_native_semantics=['Other-owned calendars retained in supplemental state','Full contact and assignment histories retained in supplemental state','Native event participant does not prove email delivery'])
    binding['original_identity']=json.loads((RELEASE/'WB01/SOURCE.json').read_text())
    binding['csv_sha256']={str(p.relative_to(folder)):digest(p) for p in (folder/'data').rglob('*.csv')}
    (folder/'binding.json').write_text(json.dumps(binding,indent=2)+'\n')
    return binding

def replay(folder, predictions, expected):
    request=dict(predictions=predictions,expected=expected)
    (folder/'request.json').write_text(json.dumps(request,indent=2)+'\n')
    worker=Path(__file__).with_name('wb01_native_worker.py')
    process=subprocess.run([sys.executable,str(worker),str(NATIVE)],cwd=folder,text=True,capture_output=True)
    (folder/'stdout.log').write_text(process.stdout);(folder/'stderr.log').write_text(process.stderr)
    if process.returncode:raise RuntimeError(process.stderr)
    return json.loads((folder/'result.json').read_text())

def evaluate_engine(engine, output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    binding=bind(output,engine.variant,engine.answers)
    try:
        actions=[]
        for event in engine.events:
            a=event.get('action')
            if isinstance(a,dict) and a.get('tool')=='call' and a.get('name')=='create_event' and 'error' not in event['reply']:
                actions.append(action(translate(a['arguments'])))
        day=dates(engine.data)[2]
        expected=[action(translate(dict(owner='self',day=day,start=e['start'],end=e['end'],title=e['title'],attendees=[e['to']]))) for e in engine.checker.target['events']]
    except (ValueError,KeyError,TypeError) as exc:
        return dict(status='failed',native_api_actions=0,original_algorithm_calls=0,unsupported_projection=str(exc))
    result=replay(output,[dict(label='live_host_captured_effects',actions=actions)],expected)
    return dict(status='passed' if result['predictions'][0]['native_evaluator_passed'] else 'failed',native_api_actions=len(actions),original_algorithm_calls=result['original_evaluator_runs'],evidence=str(output/'result.json'),layer='bundled_native_effect_replay_on_authored_world')
