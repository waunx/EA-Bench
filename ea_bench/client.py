"""Minimal text/image transport for JSON-action solvers and private user models."""
import json
import os
import time
import urllib.error
import urllib.request


class ProviderError(RuntimeError):
    """A transport/service failure, not a task correctness failure."""


def parse_json(text):
    text = text.strip()
    if text.startswith('```') and text.endswith('```'):
        text = text.split('\n', 1)[1].rsplit('```', 1)[0].strip()
    result = json.loads(text)
    if not isinstance(result, dict):
        raise ValueError('Expected one JSON object')
    return result


class ChatClient:
    def __init__(self, config, on_response=None):
        self.config = config
        self.on_response = on_response
        self.calls = 0
        self.usage = {'prompt_tokens': 0, 'completion_tokens': 0}
        self.usage_available = True
        self.usage_details = {}
        self.request_metadata = []
        self.retry_metadata = []

    def complete(self, messages):
        cfg = self.config
        token = os.environ[cfg['api_key_env']]
        api = cfg.get('wire_api', 'chat')
        if api == 'responses':
            converted = []
            for message in messages:
                content = message['content']
                if isinstance(content, list):
                    content = [({'type': 'input_text', 'text': x['text']} if x['type'] == 'text' else
                                {'type': 'input_image', 'image_url': x['image_url']['url']}) for x in content]
                converted.append({'role': message['role'], 'content': content})
            body = {'model': cfg['model'], 'input': converted, 'max_output_tokens': cfg.get('max_tokens', 16384), 'store': False}
            if cfg.get('reasoning_effort'):
                body['reasoning'] = {'effort': cfg['reasoning_effort']}
            endpoint = '/responses'
        else:
            body = {'model': cfg['model'], 'messages': messages, 'max_tokens': cfg.get('max_tokens', 16384)}
            if cfg.get('reasoning_effort'):
                body['reasoning_effort'] = cfg['reasoning_effort']
            endpoint = '/chat/completions'
        request = urllib.request.Request(cfg['base_url'].rstrip('/') + endpoint,
            data=json.dumps(body).encode(), headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        started = time.monotonic()
        for attempt in range(3):
            self.calls += 1
            try:
                with urllib.request.urlopen(request, timeout=cfg.get('timeout', 180)) as response:
                    result = json.load(response)
                break
            except urllib.error.HTTPError as error:
                status = error.code
                self.retry_metadata.append({'attempt': attempt + 1, 'http_status': status})
                if status not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise ProviderError(f'Model endpoint returned HTTP {status}') from None
                time.sleep(2 ** attempt)
            except (urllib.error.URLError, TimeoutError) as error:
                raise ProviderError('Model endpoint connection failed') from error
        usage = result.get('usage') or {}
        for target, source in [('prompt_tokens', 'input_tokens' if api == 'responses' else 'prompt_tokens'),
                               ('completion_tokens', 'output_tokens' if api == 'responses' else 'completion_tokens')]:
            value = usage.get(source)
            if isinstance(value, int):
                self.usage[target] += value
            else:
                self.usage_available = False
        metadata = {'call': self.calls, 'model': result.get('model'), 'usage': usage,
                    'seconds': round(time.monotonic() - started, 3)}
        self.request_metadata.append(metadata)
        if self.on_response:
            self.on_response(metadata)
        if api == 'responses':
            texts = [part['text'] for item in result['output'] if item['type'] == 'message'
                     for part in item['content'] if part['type'] == 'output_text']
            content = ''.join(texts)
        else:
            content = result['choices'][0]['message']['content']
        if not isinstance(content, str) or not content:
            raise ProviderError('Model returned no text content')
        return content
