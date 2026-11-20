"""Closed-state episodes with separate solver, user, grounding, and task outcomes."""
from copy import deepcopy
import json
import time
from pathlib import Path
from ea_bench.client import ChatClient, ProviderError, parse_json
from ea_bench.config import role_config
from ea_bench.io import write, append
from ea_bench.paths import DATA
from ea_bench.registry import verify_entry
from integrations.packet_stages.clarification import ClarificationUser
from .session import ProfessionalSession, OracleError
from .terminal import terminal_reason

SYSTEM = '''Complete the business task using its public documents and tool contract.
Return one JSON action per turn with no surrounding commentary. Use the op field.
Read operations take op only. Draft operations and report take op and data.
Ask the user with {"op":"ask_user","question":"your question"}.
Draft actions save artifacts without revealing whether their values are correct.
The first report is the final submission, including malformed reports.'''


def load(entry):
    folder = verify_entry(entry)
    public = json.loads((folder / 'public.json').read_text())
    private = json.loads((DATA / 'legacy/private' / (entry['case'] + '--' + entry['variant'] + '.json')).read_text())
    private['case_spec'] = json.loads((DATA / 'legacy/cases.json').read_text())[entry['case']]
    return public, private


class User:
    protocol = 'full_knowledge_v1'

    def __init__(self, simulator):
        self.simulator = simulator
        self.last_reply = ''

    def answer(self, question, topics, context):
        try:
            reply = self.simulator.answer(question)
        except (RuntimeError, ValueError, TypeError, KeyError) as error:
            raise OracleError(str(error)) from error
        self.last_reply = reply['reply']
        return {x['fact_id']: x['value'] for x in self.simulator.records[-1]['provided']}


def information_support(entry, private, acquired):
    worlds = json.loads((DATA / 'legacy/reference_worlds.json').read_text())[entry['case'] + '--' + entry['variant']]
    candidates = [w for w in worlds if all(w['policies'][k] == private['policies'][k] for k in acquired)]
    actual = next(w for w in candidates if w['policies'] == private['policies'])
    return all(w['artifacts'] == actual['artifacts'] for w in candidates)


def run(entry, output, max_actions=100, solver=None, user_client=None):
    public, private = load(entry)
    output = Path(output);output.mkdir(parents=True, exist_ok=False)
    audit = output / 'private';audit.mkdir(mode=0o700)
    solver = solver or ChatClient(role_config('solver'))
    user_client = user_client or ChatClient(role_config('user'))
    knowledge = {k: {'value': v['value'], 'answer': v['reply']} for k,v in private['oracle_facts'].items()}
    user = ClarificationUser(user_client, public['instruction'], knowledge,
        lambda r: append(audit / 'user_dialogue.jsonl', r))
    session = ProfessionalSession(public, private, User(user))
    messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': json.dumps(public)}]
    write(output / 'public_observation.json', public)
    started = time.monotonic();status = 'action_budget_exhausted';error = None
    try:
        for _ in range(max_actions):
            raw = solver.complete(messages)
            messages.append({'role': 'assistant', 'content': raw})
            try:
                action = parse_json(raw)
            except (ValueError, TypeError):
                action = None
            stop = terminal_reason(action, raw)
            if stop:
                reply = session.reject_terminal(stop, action)
            else:
                reply = session.step(action)
            append(audit / 'events.jsonl', session.events[-1])
            messages.append({'role': 'user', 'content': json.dumps(reply)})
            if session.done:
                status = 'submitted';break
    except (ProviderError, OracleError) as exc:
        status = 'infrastructure_error';error = str(exc)
    write(output / 'dialogue.json', messages)
    write(audit / 'user_records.json', user.records)
    unknown = set(private['missing_topics'] + private['conflict_topics'])
    acquired = unknown.intersection(session.clarified_topics)
    supported = information_support(entry, private, acquired)
    requests = sum(len({x['fact_id'] if x['fact_id'] is not None else 'other:' + x['question_evidence'] for x in r['requested']}) for r in user.records)
    success = session.success if status != 'infrastructure_error' else None
    information_ref = entry['information_reference']['artifacts']['actual_world_certificate']['size']
    action_ref = len(session.graph) + int(information_ref > 0)
    result = {'episode_id': entry['id'], 'track': entry['track'], 'status': status, 'error': error,
              'task_pass': success, 'grounded_pass': bool(success and supported) if success is not None else None,
              'tool_calls': session.business_calls + session.user_rounds, 'user_interactions': session.user_rounds,
              'requested_facts': requests if status != 'infrastructure_error' else None,
              'acquired_facts': sorted(acquired), 'information_reference': information_ref,
              'action_reference': action_ref, 'seconds': round(time.monotonic() - started, 3)}
    result['Et'] = result['tool_calls'] - action_ref
    result['Ei'] = requests - information_ref if result['requested_facts'] is not None else None
    write(output / 'metrics.json', result)
    return result
