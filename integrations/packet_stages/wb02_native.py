"""WB02 translated host trace replay using real bundled WorkBench tools."""
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from .english_packet import ROOT, RELEASE
from .english_wb02 import aliases, fact, load

NATIVE = ROOT / 'data/native/workbench'
WORKER = Path(__file__).with_name('wb02_native_worker.py')

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write_csv(path, columns, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

def bind_world(variant, answers, directory):
    data = load(variant)
    shutil.copytree(NATIVE / 'data', directory / 'data')
    crm_path = directory / 'data/processed/customer_relationship_manager_data.csv'
    with crm_path.open() as stream:
        columns = next(csv.reader(stream))
    mapping, rows = {}, []
    for index, record in enumerate(data['crm_records.json'], 1):
        native_id = f'{index:08d}'
        mapping[record['record']] = native_id
        row = dict.fromkeys(columns, '')
        row.update(customer_id=native_id, customer_name=record['name'],
                   assigned_to_email=record['owner'], status=record['status'])
        rows.append(row)
    write_csv(crm_path, columns, rows)
    task_path = directory / 'data/processed/project_tasks.csv'
    with task_path.open() as stream:
        task_columns = next(csv.reader(stream))
    owners = aliases(data)
    emails = {r['employee']: r['email'] for r in data['employees.csv']}
    same_task = fact(data, 'same_task', answers)
    tasks, task_ids = {}, {}
    for record in data['assigned_tasks.csv'] + data.get('closed_tasks.csv', []) + data.get('unavailable_staff_tasks.csv', []):
        logical = 'T17' if same_task and record['task'] == 'T18' else record['task']
        if logical not in tasks:
            row = dict.fromkeys(task_columns, '')
            row.update(task_id=f'{len(tasks)+1:08d}', task_name=logical,
                       assigned_to_email=emails[owners[record['owner']]],
                       list_name=record['status'].title(), board='WB02 authored workload')
            tasks[logical] = row
        task_ids[record['task']] = tasks[logical]['task_id']
    write_csv(task_path, task_columns, list(tasks.values()))
    (directory/'data/raw/email_addresses.csv').write_text('\n'.join(emails.values())+'\n')
    packet = RELEASE/'WB02/variants'/variant
    binding = dict(case='WB02', variant=variant, answers=answers,
                   original_id=json.loads((RELEASE/'WB02/SOURCE.json').read_text())['original_id'],
                   crm_id_mapping=mapping, task_id_mapping=task_ids, source_data=data,
                   supplemental_only_fields=['eligibility', 'last-lead dates', 'alias/migration evidence', 'operation chronology'],
                   packet_hashes={str(p.relative_to(packet)):digest(p) for p in packet.rglob('*') if p.is_file()},
                   native_source_hashes={str(p.relative_to(NATIVE)):digest(p) for p in (NATIVE/'src').rglob('*.py')},
                   bound_data_hashes={str(p.relative_to(directory)):digest(p) for p in (directory/'data').rglob('*.csv')},
                   provenance='Authored world projected to bundled native CSV schema; not an original native snapshot')
    (directory/'binding.json').write_text(json.dumps(binding,indent=2)+'\n')
    return data, mapping

def translate(events, data, mapping):
    owners = aliases(data)
    emails = {r['employee']:r['email'] for r in data['employees.csv']}
    mapping = dict(mapping)
    actions = []
    def action(name, **kwargs):
        return 'customer_relationship_manager.'+name+'('+', '.join(k+'='+repr(v) for k,v in kwargs.items())+')'
    for event in events:
        call, reply = event['action'], event['reply']
        if not isinstance(call,dict) or call.get('tool')!='call' or 'error' in reply:
            continue
        name, args = call['name'], call['arguments']
        if name not in {'create_record','update_record'}:
            continue
        owner = emails[args['owner']] if args['owner'] in emails else emails[owners[args['owner']]]
        if name=='create_record':
            native_id = f'{max([int(v) for v in mapping.values()]+[0])+1:08d}'
            mapping[reply['record']] = native_id
            actions.append(action('add_customer', customer_name=args['name'], assigned_to_email=owner, status=args['status']))
        else:
            for field, value in [('customer_name',args['name']),('assigned_to_email',owner),('status',args['status'])]:
                actions.append(action('update_customer', customer_id=mapping[args['record']], field=field,new_value=value))
    return actions

def replay(variant, answers, events, expected, output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    data, mapping = bind_world(variant, answers, output)
    predicted = translate(events, data, mapping)
    reference = ['customer_relationship_manager.add_customer('+
                 ', '.join(k+'='+repr(v) for k,v in dict(customer_name=expected['lead'],
                    assigned_to_email=expected['assign_to'],status='Lead').items())+')']
    request = dict(predicted=predicted, reference=reference)
    (output/'request.json').write_text(json.dumps(request,indent=2)+'\n')
    (output/'host-events.json').write_text(json.dumps(events,indent=2)+'\n')
    with (output/'worker.log').open('w') as log:
        run = subprocess.run([sys.executable,str(WORKER),str(NATIVE),str(output/'request.json')],
                             cwd=output,stdout=log,stderr=subprocess.STDOUT,timeout=90)
    if run.returncode:
        raise RuntimeError('Native WB02 worker failed; see '+str(output/'worker.log'))
    result = json.loads((output/'result.json').read_text())
    result.update(case='WB02',variant=variant,evidence_root=str(output.relative_to(ROOT)),
                  binding_sha256=digest(output/'binding.json'),host_events_sha256=digest(output/'host-events.json'),
                  adapter_sha256=digest(__file__),worker_sha256=digest(WORKER),
                  scope='Bundled native API replay of translated captured CRM actions in authored bound world; supplemental invariants checked separately')
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def evaluate_engine(engine, output):
    return replay(engine.variant,engine.answers,engine.events,engine.checker.target,output)
