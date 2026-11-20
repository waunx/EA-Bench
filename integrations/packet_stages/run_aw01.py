"""GPT-5.5 single-packet AW01 run on the authored local state environment."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time
from .run_aw06 import ChatClient, parse_json, write, append, ROOT
from .authored import SOURCE, read_json
from .clarification import ClarificationUser
from .open_aw01 import OpenAW01, SYSTEM

ANSWERS = {
    'deadline': 'The replacement must arrive by {value}.',
    'budget': 'The replacement purchase budget is {value} cents.',
    'purchased_size': 'The purchased size of order O102 was {value}.',
    'exp_stock': 'The available stock for quote Q_WHITE_EXP is {value}.',
    'standard_arrival': 'Quote Q_WHITE_STD has a delivery commitment of {value}.',
    'last_order_status': 'Order O103 has fulfillment status {value}.',
}


def run(output, variant='full', *, case='AW01', engine_factory=OpenAW01,
        knowledge_builder=None, world_answers=None, max_actions=100):
    oracle = read_json(SOURCE / case / 'private/oracle.json')
    spec = oracle['variants'][variant]
    world = {k: oracle['atoms'][k]['default'] for k in spec['missing'] + spec['conflict']}
    if world_answers is not None:
        world = world_answers
    engine = engine_factory(variant, world)
    output.mkdir(parents=True, exist_ok=False)
    private = output / 'private'
    private.mkdir(mode=0o700)
    write(private / 'world.json', world)
    from ea_bench.config import role_config
    config = role_config('solver')
    client = ChatClient(config, on_response=lambda r: append(output / 'api.jsonl', r))
    user_client = ChatClient(role_config("user"), on_response=lambda r: append(private / 'user_api.jsonl', r))
    facts = {k: world.get(k, v['default']) for k, v in oracle['atoms'].items()}
    knowledge = (knowledge_builder(facts) if knowledge_builder else
                 {k: dict(value=v, answer=ANSWERS[k].format(value=v)) for k, v in facts.items()})
    user = ClarificationUser(user_client, engine.observation()['task_description'], knowledge,
                             lambda row: append(private / 'user_dialogue.jsonl', row))
    def ask(question):
        reply = user.answer(question)
        engine.confirm({r['fact_id']: r['value'] for r in user.records[-1]['provided']
                        if r['fact_id'] in world})
        return reply
    engine.ask_handler = ask
    archive(engine, output, private, config, case=case, max_actions=max_actions)
    messages = [dict(role='system', content=SYSTEM),
                dict(role='user', content=json.dumps(engine.observation()))]
    for message in messages:
        append(output / 'dialogue.jsonl', message)
    start, status, error = time.monotonic(), 'action_budget_exhausted', None
    try:
        for turn in range(1, max_actions + 1):
            raw = client.complete(messages)
            message = dict(role='assistant', content=raw)
            messages.append(message)
            append(output / 'dialogue.jsonl', message)
            try:
                action = parse_json(raw)
            except (ValueError, TypeError):
                action = None
            reply = engine.step(action)
            append(private / 'events.jsonl', engine.events[-1])
            message = dict(role='user', content=json.dumps(reply))
            messages.append(message)
            append(output / 'dialogue.jsonl', message)
            print(json.dumps(dict(turn=turn, tool=action.get('tool') if isinstance(action, dict) else None,
                                  terminal=engine.done)), flush=True)
            if engine.done:
                status = engine.result['status']
                break
    except Exception as exc:
        status, error = 'service_or_runtime_error', type(exc).__name__ + ': ' + str(exc)
    return finish(engine, client, user, output, private, start, status, error, case=case)


def archive(engine, output, private, config, *, case='AW01', max_actions=100):
    from .native_effect_gate import VERIFIED_CASES
    write(output / 'public_observation.json', engine.observation())
    paths = list(engine.folder.parent.rglob('*'))
    for path in paths:
        if path.is_file():
            target = private / 'packet' / path.relative_to(engine.folder.parent)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
    sources = list(Path(__file__).parent.glob('*.py'))
    sources += list((ROOT / 'evaluation').glob('*.py'))
    for path in sources:
        target = private / 'sources' / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    write(output / 'implementation.json', {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    write(output / 'configuration.json', dict(
        model=config['model'], reasoning_effort=config['reasoning_effort'],
        wire_api=config['wire_api'], max_tokens=config['max_tokens'], max_actions=max_actions,
        validation_layer='authored_fixture', solver_interface='authored_fixture',
        post_submission_native_effect_validation=case in VERIFIED_CASES,
        native_effect_scope='Host-private replay of captured effects; original fixed-world evaluation is separate',
        case=case, variant=engine.variant,
        packet_hashes={str(p.relative_to(engine.folder.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in paths if p.is_file()},
        prompt_mode='task_description_and_generic_output_format', input_delivery='on_request',
        native_api_replays=0, original_evaluator_runs=0))


def finish(engine, client, user, output, private, start, status, error, *, case='AW01'):
    evaluated = status in {'submitted', 'invalid_submission', 'action_budget_exhausted'}
    counts = Counter(e['action'].get('tool') if isinstance(e['action'], dict) else 'invalid'
                     for e in engine.events)
    result = dict(case=case, variant=engine.variant, model=client.config['model'],
        status=status, error=error, success=bool(engine.result and engine.result.get('success')) if evaluated else None,
        evaluated_samples=int(evaluated), requested_samples=1, total_tool_calls=len(engine.events),
        tool_counts=dict(counts), seconds=round(time.monotonic() - start, 3))
    result.update(validation_layer='authored_fixture', native_api_replays=0, original_evaluator_runs=0,
        acceptance=(engine.result or {}).get('acceptance'), executed_writes=engine.calls,
        ask_user_calls=counts.get('ask_user', 0), additional_information_items=user.information_items,
        unique_additional_information_items=user.unique_information_items,
        completed_clarification_calls=len(user.records),
        information_metric_scope='Delivered authored fact occurrences and distinct fact IDs; neither is a proven minimum or a bit count',
        tool_lower_bound=None, information_lower_bound=None,
        model_api_attempts=client.calls, usage=client.usage, usage_details=client.usage_details,
        usage_complete=client.usage_available, user_model_api_attempts=user.client.calls,
        user_model_usage=user.client.usage, reasoning_effort=client.config.get('reasoning_effort'),
        served_models=sorted({r['model'] for r in client.request_metadata if r.get('model')}),
        prompt_mode='task_description_and_generic_output_format', input_delivery='on_request',
        information_annotation='User annotations structurally checked, not independently semantically judged')
    write(private / 'verdict.json', engine.result)
    write(private / 'final_state.json', engine.snapshot())
    write(private / 'user_records.json', user.records)
    from .native_effect_gate import apply as apply_native_effect_gate
    result = apply_native_effect_gate(engine, result, private)
    write(output / 'metrics.json', result)
    print(json.dumps(result), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--variant', default='full')
    args = parser.parse_args()
    result = run(args.output.resolve(), args.variant)
    if result['status'] == 'service_or_runtime_error':
        raise SystemExit(2)
