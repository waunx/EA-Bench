"""Public entry point: verify inputs, replay references, run, or grade one episode."""
import argparse
from collections import Counter
from copy import deepcopy
import importlib
import json
from pathlib import Path
from .config import load_config
from .io import write
from .paths import DATA
from .registry import entries, get_entry, verify_entry


def reference_check():
    from .legacy.runner import load
    from .legacy.session import ProfessionalSession
    from .legacy.expanded.domains import solve
    total = 0
    for entry in entries():
        if entry['cohort'] != 'legacy':continue
        public, private = load(entry)
        worlds = json.loads((DATA / 'legacy/reference_worlds.json').read_text())[entry['case'] + '--' + entry['variant']]
        for world in worlds:
            state = deepcopy(private);state['policies'] = world['policies']
            expected = solve(entry['case'], state['data'], state['policies'])
            if expected != world['artifacts']:raise AssertionError('Reference drift: ' + entry['id'])
            session = ProfessionalSession(public, state, None)
            for op in session.graph:
                action = {'op': op}
                if not op.startswith('read_'):action['data'] = expected[op]
                session.step(action)
            if not session.success:raise AssertionError('Reference replay failed: ' + entry['id'])
            malformed = ProfessionalSession(public, state, None)
            malformed.step({'op': 'report', 'data': expected['report']})
            if malformed.success:raise AssertionError('Missing prerequisites accepted')
            total += 1
    return {'status': 'passed', 'conditions': 68, 'reference_worlds': total}


def run(entry, output, max_actions):
    verify_entry(entry)
    if entry['cohort'] == 'legacy':
        from .legacy.runner import run as run_legacy
        return run_legacy(entry, output, max_actions)
    case, variant = entry['case'], entry['variant']
    if case.startswith('JB'):
        from integrations.packet_stages.run_artifact_case import run as artifact_run
        return artifact_run(case, variant, output, 'integrations.packet_stages.artifact_adapter_' + case.lower(), max_actions=max_actions)
    from integrations.packet_stages.run_aw01 import run as state_run
    module = importlib.import_module('integrations.packet_stages.open_' + case.lower())
    engine = getattr(module, 'Open' + case)
    if case == 'AW06':
        cls = engine
        engine = lambda variant, world: cls(variant=variant, answers=world)
    knowledge = None
    if case != 'AW01':
        name = 'run_aw06_variants' if case == 'AW06' else 'run_' + case.lower()
        knowledge = importlib.import_module('integrations.packet_stages.' + name).knowledge
    return state_run(Path(output), variant, case=case, engine_factory=engine, knowledge_builder=knowledge, max_actions=max_actions)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('list')
    commands.add_parser('verify')
    commands.add_parser('check-references')
    p = commands.add_parser('run');p.add_argument('--episode', required=True);p.add_argument('--config', required=True)
    p.add_argument('--output', required=True, type=Path);p.add_argument('--max-actions', type=int, default=100)
    p = commands.add_parser('grade');p.add_argument('--episode', required=True);p.add_argument('--config', required=True)
    p.add_argument('--artifacts', required=True, type=Path);p.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.command == 'list':
        result = {'base_tasks': len({x['case_key'] for x in entries()}), 'conditions':len(entries()),
                  'tracks': dict(Counter(x['track'] for x in entries())),
                  'episodes': [{k:x[k] for k in ('id','track','group')} for x in entries()]}
    elif args.command == 'verify':
        for entry in entries():verify_entry(entry)
        result = {'status':'passed', 'conditions':len(entries())}
    elif args.command == 'check-references':
        result = reference_check()
    else:
        load_config(args.config);entry = get_entry(args.episode)
        if args.command == 'run':
            if args.max_actions <= 0:parser.error('--max-actions must be positive')
            result = run(entry,args.output,args.max_actions)
            from .metrics import finalize
            result = finalize(entry,args.output,result)
        else:
            if not entry['case'].startswith('JB') or entry['cohort']!='expanded':parser.error('grade accepts expanded JobBench artifact tasks')
            verify_entry(entry)
            from integrations.packet_stages.authored import SOURCE,read_json
            oracle=read_json(SOURCE/entry['case']/'private/oracle.json');spec=oracle['variants'][entry['variant']]
            world={k:oracle['atoms'][k]['default'] for k in spec['missing']+spec['conflict']}
            adapter=importlib.import_module('integrations.packet_stages.artifact_adapter_'+entry['case'].lower())
            result=adapter.check(args.artifacts,args.output,entry['variant'],world)
    print(json.dumps(result,indent=2,default=str))

if __name__ == '__main__':main()
