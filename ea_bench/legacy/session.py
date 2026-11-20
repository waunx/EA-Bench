"""Port of the original first-submission grader and dependency-tracking session."""
from copy import deepcopy
import json
import secrets
from .expanded.domains import solve
AUTOMATIC = 'automatic_dependencies_v1'
class OracleError(RuntimeError):
    pass

def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)

def action_protocol(public):
    mode = public['tool_contract']['action_protocol']
    if mode != AUTOMATIC:
        raise ValueError('This release uses automatic private dependency tracking')
    return mode

class ProfessionalSession:
    def __init__(self, public, private, oracle):
        self.public = deepcopy(public)
        self.action_protocol = action_protocol(public)
        self.private = private
        self.oracle = oracle
        self.solve = solve
        self.case = private['case_spec']
        self.graph = {**{op: [] for op in self.case['data']}, **self.case['stages']}
        self.free_questions = True
        self.handles, self.outputs, self.events = {}, {}, []
        self.clarified_topics, self.clarified_before_errors = set(), set()
        self.business_calls = self.user_rounds = self.revisions = 0
        self.done = self.success = False
        self.submission = self.submitted_report = None
        self._resolved_inputs = None

    def reject_terminal(self, reason, action=None):
        """Close an explicit terminal attempt that has no valid report object."""
        if self.done:
            return {'error':'session_finalized'}
        self.business_calls += 1
        self.done = True
        self.success = False
        self.submitted_report = None
        self.submission = dict(passed=False,reason=reason,verified_cost=None)
        result = {'submission_received':True,'terminal':True}
        self.events.append(deepcopy(dict(action=action,result=result,terminal_reason=reason)))
        return result

    def step(self, action):
        if self.done:
            return {'error':'session_finalized'}
        self._resolved_inputs = None
        op = action.get('op') if isinstance(action,dict) else None
        if op == 'ask_user':
            self.user_rounds += 1
        else:
            self.business_calls += 1
        try:
            result = self._step(action,op)
        except OracleError as error:
            # Preserve failed questions for post-run information accounting.
            # The caller still terminates the episode as a user_agent_error.
            from .terminal import administrative_stop
            if administrative_stop(action):
                result={'reply':'','from':'Evaluator','user_agent_error':str(error)}
            else:
                self.events.append(deepcopy(dict(action=action,result={'error':'user_agent_error'})))
                raise
        except (KeyError,TypeError,ValueError):
            result = {'error':'invalid_action_or_dependencies'}
        from .terminal import administrative_stop
        if op == 'ask_user' and administrative_stop(action):
            self.done=True
            self.success=False
            self.submitted_report=None
            self.submission=dict(passed=False,reason='agent_requested_stop_without_submission',verified_cost=None)
            result=dict(result,terminal=True)
        if op == 'report':
            self.done = True
            self.success = 'error' not in result
            self.submitted_report = deepcopy(action.get('data'))
            objective = self.case['objective']
            self.submission = dict(passed=self.success,reason=result.get('error'),
                verified_cost=(self.outputs['report'].get(objective) if self.success and objective else None))
            result = {'submission_received':True,'terminal':True}
        event = dict(action=action,result=result)
        if self.action_protocol == AUTOMATIC:
            event['resolved_inputs'] = self._resolved_inputs
        self.events.append(deepcopy(event))
        visible = deepcopy(result)
        if self.action_protocol == AUTOMATIC:
            visible.pop('handle', None)
        return visible

    def _step(self, action, op):
        if op == 'ask_user':
            if set(action) != {'op','question'} or not isinstance(action['question'],str) or not 0<len(action['question'].strip())<=4000:
                raise ValueError()
            answers = self.oracle.answer(action['question'],list(self.private['policies']),{'completed_operations':list(self.outputs)})
            self.clarified_topics.update(answers)
            if not any('error' in e['result'] for e in self.events):
                self.clarified_before_errors.update(answers)
            if getattr(self.oracle,'protocol',None)=='full_knowledge_v1':
                return {'reply':self.oracle.last_reply,'from':'Project owner'}
            return {'answers':{t:self.private['oracle_facts'][t]['reply'] for t in answers},'from':'Project owner'}
        if not isinstance(op,str) or op not in self.graph:
            raise ValueError()
        reading = op.startswith('read_')
        automatic = self.action_protocol == AUTOMATIC
        keys = {'op'} if automatic else {'op','inputs'}
        if set(action) != keys | (set() if reading else {'data'}):
            raise ValueError()
        if automatic:
            missing = [p for p in self.graph[op] if p not in self.handles]
            if missing:
                return {'error':'missing_dependencies','operations':missing}
            inputs = {p:self.handles[p] for p in self.graph[op]}
            self._resolved_inputs = deepcopy(inputs)
        else:
            inputs = action['inputs']
        if not isinstance(inputs,dict) or set(inputs) != set(self.graph[op]):
            raise ValueError()
        if any(p not in self.handles or inputs[p] != self.handles[p] for p in self.graph[op]):
            raise ValueError()
        if reading:
            return self._store(op,self.private['sources'][op])
        data = action['data']
        expected_type = list if isinstance(self.case['shapes'][op],list) else dict
        if not isinstance(data,expected_type):
            raise ValueError()
        canonical(data)
        if op == 'report':
            expected = self.solve(self.private['case_id'],self.private['data'],self.private['policies'])
            submitted = {**self.outputs,'report':data}
            if any(canonical(submitted.get(k)) != canonical(v) for k,v in expected.items()):
                return {'error':'incorrect_artifacts_or_nonoptimal_plan'}
        return self._store(op,data)

    def _store(self, op, value):
        if op in self.handles:
            self.revisions += 1
        invalid = {op}
        for child,parents in self.graph.items():
            if invalid.intersection(parents):
                invalid.add(child)
        for child in invalid:
            self.handles.pop(child,None)
            self.outputs.pop(child,None)
        handle = secrets.token_hex(16)
        self.handles[op] = handle
        self.outputs[op] = deepcopy(value)
        return {'handle':handle,'data':deepcopy(value)}
