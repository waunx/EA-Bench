"""AW11 factual clarification without recommended follow actions."""
def knowledge(facts):
    names={'X1':'Alex Park','X2':'Alex Vale'}
    text=dict(alex='P1 meant '+names[facts['alex']]+' in recommendation M1.',
        p3_scope='P3 '+('is' if facts['p3_scope'] else 'is not')+' in the current friend/coworker recommendation scope.',
        a2_followed='The account '+('currently follows' if facts['a2_followed'] else 'does not currently follow')+' A2 Mara Reed.')
    return {k:dict(value=v,answer=text[k]) for k,v in facts.items()}
