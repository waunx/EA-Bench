"""Keep requested facts, delivered facts, user turns and action calls distinct."""
import json
from .paths import DATA
from .io import write


def finalize(entry, output, result):
    records_path = output / 'private/user_records.json'
    records = json.loads(records_path.read_text()) if records_path.exists() else []
    user_calls = result.get('user_interactions', result.get('ask_user_calls', 0))
    complete = len(records) == user_calls and all('requested' in r and 'provided' in r for r in records)
    requested = sum(len({x['fact_id'] if x['fact_id'] is not None else ('other', x['question_evidence'])
                         for x in r['requested']}) for r in records) if complete else None
    result.update(episode_id=entry['id'], track=entry['track'], group=entry['group'],
                  requested_facts=requested, request_accounting_complete=complete,
                  delivered_facts=sum(len(r['provided']) for r in records), user_interactions=user_calls)
    if entry['cohort'] == 'expanded':
        oracle = json.loads((DATA / 'authored' / entry['case'] / 'private/oracle.json').read_text())
        spec = oracle['variants'][entry['variant']]
        world = {k:oracle['atoms'][k]['default'] for k in set(spec['missing'] + spec['conflict'])}
        certificate = next(c for c in entry['information_reference']['certificates'] if c['answers'] == world)
        acquired = {x['fact_id'] for row in records for x in row['provided']}
        result['finite_world_information_supported'] = any(set(s) <= acquired for s in certificate['minimal_subsets'])
        result['finite_information_reference'] = certificate['min_facts']
        result['Ei'] = requested - certificate['min_facts'] if complete and entry['track'] == 'Easy' else None
        result['Et'] = None
        result['reference_scope'] = 'Finite checked-world information certificate; no global action reference for expanded tasks.'
    write(output / 'metrics.json', result)
    return result
