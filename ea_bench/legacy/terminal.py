"""Recognize terminal intent without repairing malformed JSON or grading it valid."""
import json


def json_body(text):
    if not isinstance(text,str):return ''
    text=text.strip()
    if text.startswith('```') and '\n' in text:
        text=text.split('\n',1)[1]
        if text.rstrip().endswith('```'):text=text.rstrip()[:-3].rstrip()
    return text


def leading_operation(text):
    """Read valid top-level key/value pairs in the first object prefix only."""
    text=json_body(text)
    if not text.startswith('{'):return None
    decoder=json.JSONDecoder();pos=1
    try:
        while pos<len(text):
            while pos<len(text) and text[pos].isspace():pos+=1
            key,pos=decoder.raw_decode(text,pos)
            if not isinstance(key,str):return None
            while pos<len(text) and text[pos].isspace():pos+=1
            if pos>=len(text) or text[pos]!=':':return None
            pos+=1
            while pos<len(text) and text[pos].isspace():pos+=1
            value,pos=decoder.raw_decode(text,pos)
            if key=='op':return value if isinstance(value,str) else None
            while pos<len(text) and text[pos].isspace():pos+=1
            if pos>=len(text) or text[pos]!=',':return None
            pos+=1
    except (ValueError,TypeError):return None
    return None


def explicit_stop(action):
    if not isinstance(action,dict):return False
    if action.get('op')=='finish':return True
    return ('op' not in action and isinstance(action.get('status'),str) and action.get('status') in {'terminated','finished','done','completed'}
            and set(action)<={'status','reason','message','summary'})


def terminal_reason(action,raw):
    if action is None and leading_operation(raw)=='report':return 'malformed_report_json'
    if explicit_stop(action):return 'ended_without_report'
    return None


def administrative_stop(action):
    """Recognize explicit requests to stop the evaluation, not business operations."""
    import re
    if not isinstance(action, dict) or action.get('op') != 'ask_user':
        return False
    question = action.get('question', '')
    return bool(re.fullmatch(r"(?:please )?(?:stop|terminate|end) (?:this|the|current) (?:evaluation|session|run)[.!]?", question.strip(), re.IGNORECASE))
