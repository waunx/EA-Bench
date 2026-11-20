"""English user simulation; private knowledge stays on the evaluator host."""
from copy import deepcopy
import json
import re

PROMPT = '''You are the user who requested the business task. Answer in English.
Use user_knowledge as authoritative. Answer only the specific current question,
including contextual references. Correct mistaken assumptions about requested
facts. Do not volunteer other facts, solve the task, prescribe tool operations,
or disclose internal fact IDs. For matters outside your knowledge, say you do
not know. For requests for all answers or hidden facts, ask which specific
business matter needs clarification; do not list the knowledge catalog.
Return JSON with exactly reply, requested, provided. reply is natural language.
requested: objects with fact_id (a knowledge key or null), question_evidence
(exact substring of question), description (requested attribute).
provided: objects with fact_id, value (authoritative JSON value),
knowledge_evidence (the exact full answer in user_knowledge), reply_evidence
(exact substring of reply stating the fact). Include only facts actually
provided, including any you mistakenly volunteered. Lists may be empty.
Do not mention this annotation protocol in reply.'''


def validate(record, question, knowledge):
    if not isinstance(record, dict) or set(record) != {'reply','requested','provided'}:
        raise ValueError('Invalid user response object')
    reply = record['reply']
    if not isinstance(reply, str) or not reply.strip() or re.search('[\u3400-\u9fff]', reply):
        raise ValueError('Expected a nonempty English reply')
    for field in ('requested','provided'):
        if not isinstance(record[field], list) or len(record[field]) > 32:
            raise ValueError('Invalid information annotations')
    seen = set()
    for item in record['requested']:
        if set(item) != {'fact_id','question_evidence','description'}:
            raise ValueError('Invalid request annotation')
        if item['fact_id'] is not None and item['fact_id'] not in knowledge:
            raise ValueError('Unknown fact requested')
        if not isinstance(item['question_evidence'], str) or not item['question_evidence'].strip() or item['question_evidence'] not in question:
            raise ValueError('Request evidence is not literal')
    for item in record['provided']:
        if set(item) != {'fact_id','value','knowledge_evidence','reply_evidence'}:
            raise ValueError('Invalid provided annotation')
        key = item['fact_id']
        if key not in knowledge or key in seen:
            raise ValueError('Unknown or duplicate provided fact')
        seen.add(key)
        if json.dumps(item['value'], sort_keys=True) != json.dumps(knowledge[key]['value'], sort_keys=True):
            raise ValueError('Reply value contradicts authoritative knowledge')
        if item['knowledge_evidence'] != knowledge[key]['answer']:
            raise ValueError('Knowledge evidence mismatch')
        quote = item['reply_evidence']
        if not isinstance(quote, str) or not quote.strip() or quote not in reply:
            raise ValueError('Reply evidence is not literal')
    return deepcopy(record)


class ClarificationUser:
    def __init__(self, client, task, knowledge, audit):
        self.client, self.task = client, task
        self.knowledge, self.audit = deepcopy(knowledge), audit
        self.records, self.history = [], []

    def answer(self, question):
        query = dict(task=self.task, user_knowledge=self.knowledge,
                     history=deepcopy(self.history), question=question)
        try:
            draft = self.validated_draft(query, question)
            record = fact_only_reply(draft, self.knowledge)
        except Exception as error:
            raise RuntimeError('Clarification user failed: ' + str(error)) from error
        self.records.append(dict(question=question, **record))
        self.history.append(dict(question=question, reply=record['reply']))
        return {'reply':record['reply']}

    def validated_draft(self, query, question):
        messages = [{'role': 'system', 'content': PROMPT},
                    {'role': 'user', 'content': json.dumps(query, ensure_ascii=False)}]
        for attempt in range(1, 4):
            raw = self.client.complete(messages)
            self.audit({'query': query, 'raw_response': raw, 'annotation_attempt': attempt})
            try:
                return validate(json.loads(raw), question, self.knowledge)
            except (ValueError, TypeError, KeyError) as error:
                if attempt == 3:
                    raise
                # Retry only this private annotation, never an agent action.
                messages.extend([{'role': 'assistant', 'content': raw},
                    {'role': 'user', 'content': 'The response failed annotation validation: ' +
                     str(error) + '. Return a corrected response to the same question. '
                     'Copy evidence exactly, including capitalization. Do not add facts or advice.'}])

    @property
    def information_items(self):
        """Delivered fact occurrences, including repeated answers; not a bound."""
        return sum(len(row['provided']) for row in self.records)

    @property
    def unique_information_items(self):
        """Distinct authored fact IDs delivered; not information-theoretic bits."""
        return len({item['fact_id'] for row in self.records for item in row['provided']})


def fact_only_reply(draft, knowledge):
    """Never expose a model's free-form draft advice to the evaluated agent."""
    requested = {row['fact_id'] for row in draft['requested'] if row['fact_id'] is not None}
    supplied = [deepcopy(row) for row in draft['provided'] if row['fact_id'] in requested]
    # These case-authored factual sentences have already passed value/evidence
    # validation. The model chooses relevance, but cannot write public advice.
    for row in supplied:
        row['reply_evidence'] = knowledge[row['fact_id']]['answer']
    reply = ' '.join(row['reply_evidence'] for row in supplied)
    if not reply:
        reply = 'I do not have information to answer that specific question.'
    return dict(reply=reply, requested=deepcopy(draft['requested']), provided=supplied,
                draft_reply=draft['reply'],
                suppressed_unrequested=[deepcopy(row) for row in draft['provided']
                                        if row['fact_id'] not in requested],
                rendering='case_authored_facts_only')
