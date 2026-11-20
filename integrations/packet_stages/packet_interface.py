"""Generic file/action boundary; no case rules or expected decisions."""
from copy import deepcopy
from pathlib import PurePosixPath
from .session import canonical
def same(a,b): return canonical(a)==canonical(b)
SYSTEM = 'Return exactly one JSON action per turn using the supplied output format.'
OUTPUT_FORMAT = {'list_files': {'tool': 'list_files'}, 'read_file': {'tool': 'read_file', 'path': 'relative input filename'}, 'list_tools': {'tool': 'list_tools'}, 'call': {'tool': 'call', 'name': 'API name', 'arguments': {}}, 'ask_user': {'tool': 'ask_user', 'question': 'question text'}, 'submit': {'tool': 'submit', 'result': {'summary': 'final response to the user'}}}

class PacketInterface:

    def snapshot(self):
        return deepcopy(self.state)

    def observation(self):
        return dict(task_description=(self.folder.parent / 'prompt.md').read_text(), output_format=deepcopy(OUTPUT_FORMAT))

    def confirm(self, values):
        if any((k not in self.answers or not same(v, self.answers[k]) for k, v in values.items())):
            raise ValueError('Host answer does not match the selected world')
        self.confirmed.update(deepcopy(values))

    def step(self, action):
        if self.done:
            return {'error': 'session_finalized'}
        before = self.snapshot()
        terminal = isinstance(action, dict) and action.get('tool') == 'submit'
        try:
            reply = self.dispatch(action)
        except self.need_fact_error as error:
            reply = {'error': self.fact_labels[str(error)] + ' requires confirmation.'}
        except (KeyError, ValueError, TypeError) as error:
            reply = {'error': str(error)}
            if terminal:
                self.result = dict(success=False, status='invalid_submission')
        if terminal:
            self.done = True
            reply = {'submission_received': True, 'terminal': True}
        self.events.append(dict(action=deepcopy(action), reply=deepcopy(reply), before=before, after=self.snapshot()))
        return reply

    def dispatch(self, action):
        if not isinstance(action, dict):
            raise ValueError('Expected one JSON object')
        tool = action.get('tool')
        if tool in {'list_files', 'list_tools'}:
            if set(action) != {'tool'}:
                raise ValueError('Unexpected argument')
            return {'files': sorted(self.files)} if tool == 'list_files' else {'apis': deepcopy(self.api_formats)}
        if tool == 'read_file':
            name = action.get('path')
            if set(action) != {'tool', 'path'} or not isinstance(name, str):
                raise ValueError('Expected path string')
            if name not in self.files or PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts:
                raise ValueError('Unknown input file')
            return {'path': name, 'content': self.files[name].read_text()}
        if tool == 'call':
            if set(action) != {'tool', 'name', 'arguments'} or not isinstance(action['arguments'], dict):
                raise ValueError('Expected API name and arguments object')
            return self.call(action['name'], action['arguments'])
        return self.finish_or_ask(action)

    def finish_or_ask(self, action):
        if action.get('tool') == 'ask_user':
            if set(action) != {'tool', 'question'} or not isinstance(action['question'], str):
                raise ValueError('Expected question string')
            if self.ask_handler is None:
                raise RuntimeError('Clarification user is not configured')
            return self.ask_handler(action['question'])
        if action.get('tool') == 'submit':
            if set(action) != {'tool', 'result'}:
                raise ValueError('Expected result object')
            try:
                verdict = self.checker.final(action['result'])
            except Exception as error:
                raise RuntimeError('State evaluator failed') from error
            self.result = dict(status='submitted', success=verdict.status == 'passed', acceptance=verdict.to_dict())
            return {'submission_received': True}
        raise ValueError('Unknown tool')
