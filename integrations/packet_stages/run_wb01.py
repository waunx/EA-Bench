"""WB01 factual answers without suggested meeting times or assignees."""
def knowledge(facts):
    minute=facts['busy_end'];clock=f'{minute//60:02d}:{minute%60:02d}'
    text=dict(connected='CALL7 '+('connected.' if facts['connected'] else 'did not connect.'),
        busy_end='The self-owned December 1 event starting at 10:15 ends at '+clock+'.',
        handover='The Sofia-to-Akira assignment handover takes effect on '+facts['handover']+'.')
    return {k:dict(value=v,answer=text[k]) for k,v in facts.items()}
