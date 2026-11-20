"""AW10 verifies sent email bytes and actual edit/send effects."""
from copy import deepcopy
from .authored import reviewed_worlds
from .english_aw10 import load,solve
from .acceptance import CheckResult
from .session import BindingError,canonical

def same(a,b):return canonical(a)==canonical(b)
def initial_state(data):
    return dict(source_data=deepcopy(data),drafts={'MAIL1':data['mail_draft.eml']},sent=[],mail_events=[])

def preserved(original,edited):
    if not isinstance(edited,str):return False
    start=original.index('<SONGS>')+len('<SONGS>');end=original.index('</SONGS>')
    return (edited.startswith(original[:start]) and edited.endswith(original[end:])
            and edited.count('<SONGS>')==1 and edited.count('</SONGS>')==1)

class AW10Checker:
    def __init__(self,variant,answers,backend):
        self.data=load(variant);self.target=solve(self.data,answers)
        matches=[e for a,e in reviewed_worlds('AW10',variant) if same(a,answers)]
        if len(matches)!=1 or not same(matches[0],self.target):raise BindingError('AW10 reviewed result mismatch')
        self.backend,self.initial=backend,backend.snapshot()
        if not same(self.initial,initial_state(self.data)):raise BindingError('AW10 initial state mismatch')

    def final(self,report):
        state=self.backend.snapshot();sent=state.get('sent',[])
        expected=[dict(draft_id='MAIL1',message=self.target['message'])]
        valid,bounds=self.ledger(state)
        checks=dict(correct_sent_email=same(sent,expected),draft_consumed=same(state.get('drafts'),{}),
            only_song_entries_modified=bounds,
            mail_effect_ledger=valid,
            source_records_preserved=same(state.get('source_data'),self.initial['source_data']),
            state_fields_preserved=set(state)==set(self.initial),
            report=isinstance(report,dict) and set(report)=={'summary'} and isinstance(report['summary'],str) and bool(report['summary'].strip()))
        return CheckResult.evaluated('authored_state',checks,backend='authored_fixture')

    def ledger(self,state):
        replay=deepcopy(self.initial['drafts']);sent=[];bounds=True
        try:
            for event in state.get('mail_events',[]):
                identity=event['draft_id']
                if identity not in replay:return False,bounds
                if event['op']=='update' and set(event)=={'op','draft_id','message'}:
                    bounds=bounds and preserved(self.data['mail_draft.eml'],event['message'])
                    replay[identity]=event['message']
                elif event['op']=='send' and set(event)=={'op','draft_id'}:
                    sent.append(dict(draft_id=identity,message=replay.pop(identity)))
                else:return False,bounds
        except (TypeError,KeyError):return False,False
        bounds=bounds and all(preserved(self.data['mail_draft.eml'],r['message']) for r in sent)
        return same(replay,state.get('drafts')) and same(sent,state.get('sent')),bounds
