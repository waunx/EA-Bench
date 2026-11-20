"""Opaque dependency handles, terminal grading, and branch-aware stage counts."""
from copy import deepcopy
import json
import secrets
from jsonschema import Draft202012Validator, ValidationError

UNIT = 'dag_stage_calls_v1'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':'))


class BindingError(ValueError):
    pass


class StageSession:
    def __init__(self, nodes, readers, checkers, final_checker, *, writers=None, ask_handler=None,
                 observers=None, effect_checkers=None):
        self.nodes = {n['id']:deepcopy(n) for n in nodes}
        if len(self.nodes)!=len(nodes) or 'report' in self.nodes or 'ask_user' in self.nodes:
            raise BindingError('Duplicate or reserved node IDs')
        self.readers, self.checkers = readers, checkers
        self.writers, self.ask_handler = writers or {}, ask_handler
        self.final_checker = final_checker
        self.observers = observers or {}
        self.effect_checkers = effect_checkers or {}
        # Host-only evidence; never a model-visible output or dependency.
        self.evidence, self.check_results = {}, {}
        self.handles, self.outputs, self.events = {}, {}, []
        self.done = self.success = False
        self.stage_calls = self.ask_calls = self.information_items = 0
        self.verdict = None
        self.order = self._validate_bindings()

    def _validate_bindings(self):
        if not callable(self.final_checker):
            raise BindingError('A complete task checker is required')
        for identity, node in self.nodes.items():
            if node.get('when'):
                guard = node['when']['node']
                if guard not in node['parents']:
                    node['parents'].append(guard)
            if set(node['parents'])-set(self.nodes):
                raise BindingError('Unknown prerequisite')
            if node['kind']=='read':
                if not callable(self.readers.get(identity)):
                    raise BindingError('Missing reader: '+identity)
            else:
                if not callable(self.checkers.get(identity)):
                    raise BindingError('Missing semantic checker: '+identity)
                Draft202012Validator.check_schema(node['schema'])
            if node['kind']=='write' and not callable(self.writers.get(identity)):
                raise BindingError('Missing state/artifact executor: '+identity)
            if node['kind']=='write':
                if not callable(self.observers.get(identity)):
                    raise BindingError('Missing state/artifact observer: '+identity)
                if not callable(self.effect_checkers.get(identity)):
                    raise BindingError('Missing post-execution checker: '+identity)
        order, remaining = [], set(self.nodes)
        while remaining:
            ready = sorted(n for n in remaining if set(self.nodes[n]['parents']) <= set(order))
            if not ready:
                raise BindingError('Cyclic dependencies')
            order.extend(ready)
            remaining.difference_update(ready)
        return order

    def active(self, identity):
        when = self.nodes[identity].get('when')
        if not when:
            return True
        if when['node'] not in self.outputs:
            return None
        value = self.outputs[when['node']]
        for field in when.get('path', []):
            value = value[field]
        return canonical(value)==canonical(when['equals'])

    def _parents(self, identity):
        parents = self.nodes[identity]['parents']
        if any(self.active(p) is None for p in parents):
            raise ValueError('Branch prerequisites unresolved')
        return [p for p in parents if self.active(p)]

    def _check_handles(self, supplied, required):
        if not isinstance(supplied, dict) or set(supplied)!=set(required):
            raise ValueError('Incorrect dependency set')
        if any(p not in self.handles or supplied[p]!=self.handles[p] for p in required):
            raise ValueError('Missing, stale, or foreign handle')

    def step(self, action):
        if self.done:
            return {'error':'session_finalized'}
        op = action.get('op') if isinstance(action, dict) else None
        if op=='ask_user':
            self.ask_calls += 1
        else:
            self.stage_calls += 1
        try:
            result = self._step(action, op)
        except BindingError as error:
            result = {'accepted':None, 'status':'evaluation_error'}
            diagnostic = str(error)
            self.done = True
            self.verdict = deepcopy(result)
        except (KeyError, TypeError, ValueError, ValidationError) as error:
            result = {'error':'invalid_action_or_dependencies'}
            diagnostic = type(error).__name__+': '+str(error)
        except Exception as error:
            result = {'accepted':None, 'status':'execution_error'}
            diagnostic = type(error).__name__+': '+str(error)
            self.done = True
            self.verdict = deepcopy(result)
        else:
            diagnostic = None
        if op=='report':
            self.done = True
            self.success = result.get('accepted') is True
            self.verdict = deepcopy(result)
            visible = {'submission_received':True, 'terminal':True}
        else:
            visible = result
        self.events.append(deepcopy(dict(action=action, result=visible, private_diagnostic=diagnostic)))
        return deepcopy(visible)

    def _step(self, action, op):
        if op=='ask_user':
            if set(action)!={'op','question'} or not isinstance(action['question'], str) or not action['question'].strip():
                raise ValueError('Invalid question')
            if not callable(self.ask_handler):
                raise BindingError('Missing user agent')
            answer = self.ask_handler(action['question'])
            if type(answer.get('information_items')) is not int or answer['information_items']<0:
                raise BindingError('Missing information feedback')
            self.information_items += answer['information_items']
            return {'reply':answer['reply']}
        if op=='report':
            return self._report(action)
        if op not in self.nodes or self.active(op) is not True:
            raise ValueError('Unknown, inactive, or unresolved operation')
        node = self.nodes[op]
        keys = {'op','inputs'} | (set() if node['kind']=='read' else {'data'})
        if set(action)!=keys:
            raise ValueError('Incorrect action keys')
        parents = self._parents(op)
        self._check_handles(action['inputs'], parents)
        context = {p:deepcopy(self.outputs[p]) for p in parents}
        if node['kind']=='read':
            try:
                value = self.readers[op](context)
            except Exception as error:
                raise BindingError('Source reader failed: '+op) from error
        else:
            value = deepcopy(action['data'])
            Draft202012Validator(node['schema']).validate(value)
        canonical(value)
        return self._store(op, value)

    def _store(self, op, value):
        invalid = {op}
        for identity in self.order:
            if invalid.intersection(self.nodes[identity]['parents']):
                invalid.add(identity)
        for identity in invalid:
            self.handles.pop(identity, None)
            self.outputs.pop(identity, None)
            self.evidence.pop(identity, None)
        self.handles[op] = secrets.token_hex(24)
        self.outputs[op] = deepcopy(value)
        return {'handle':self.handles[op], 'data':deepcopy(value)}

    def _report(self, action):
        if set(action)!={'op','inputs','data'}:
            raise ValueError('Malformed terminal report')
        states = {n:self.active(n) for n in self.nodes}
        if None in states.values():
            raise ValueError('Unresolved branches')
        required = [n for n, active in states.items() if active]
        self._check_handles(action['inputs'], required)
        failed = []
        for identity in self.order:
            if identity not in required:
                continue
            if self.nodes[identity]['kind']=='read':
                continue
            parents = self._parents(identity)
            context = {p:deepcopy(self.outputs[p]) for p in parents}
            try:
                accepted = self.checkers[identity](deepcopy(self.outputs[identity]), context)
            except Exception as error:
                raise BindingError('Semantic checker failed: '+identity) from error
            if type(accepted) is not bool:
                raise BindingError('Checker did not supply a boolean verdict')
            self.check_results[identity] = {'plan': accepted}
            if not accepted:
                failed.append(identity)
        if failed:
            accepted = False
        else:
            # Like the 270 release, intermediate calls do not expose semantic
            # grades. Only validated write plans are committed, in DAG order.
            for identity in self.order:
                if identity in required and self.nodes[identity]['kind']=='write':
                    context = {p:deepcopy(self.outputs[p]) for p in self._parents(identity)}
                    try:
                        before = deepcopy(self.observers[identity]())
                        self.evidence[identity] = dict(before=before, execution_status='started')
                        receipt = self.writers[identity](deepcopy(self.outputs[identity]), context)
                        after = deepcopy(self.observers[identity]())
                        evidence = dict(before=before, after=after, receipt=deepcopy(receipt))
                        canonical(evidence)
                        self.evidence[identity] = evidence
                        effect_ok = self.effect_checkers[identity](
                            deepcopy(self.outputs[identity]), context, deepcopy(evidence))
                    except Exception as error:
                        self.evidence.setdefault(identity, {})['execution_status'] = 'error'
                        # A writer can fail after a partial side effect. Preserve
                        # what is observable; never execute the writer again.
                        try:
                            self.evidence[identity]['after_error'] = deepcopy(self.observers[identity]())
                        except Exception:
                            self.evidence[identity]['after_error_unavailable'] = True
                        raise BindingError('State/artifact execution failed: '+identity) from error
                    if type(effect_ok) is not bool:
                        raise BindingError('Post-execution checker did not supply a boolean verdict')
                    self.check_results[identity]['effect'] = effect_ok
                    if not effect_ok:
                        failed.append(identity)
                        break
            if failed:
                accepted = False
            else:
                try:
                    accepted = self.final_checker(deepcopy(self.outputs), deepcopy(action['data']))
                except Exception as error:
                    raise BindingError('Final task checker failed') from error
        if type(accepted) is not bool:
            raise BindingError('Final checker did not supply a boolean verdict')
        return dict(accepted=accepted and not failed, failed_nodes=failed,
                    required_nodes=required, stage_lower_bound=len(required)+1 if accepted and not failed else None,
                    stage_calls=self.stage_calls, ask_calls=self.ask_calls,
                    information_items=self.information_items, unit=UNIT,
                    validation_layer=getattr(self, 'validation_layer', 'host_bound'),
                    acceptance=deepcopy(getattr(self.final_checker, 'results', {})))
