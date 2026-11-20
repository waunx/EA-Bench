"""Factual AW10 answers; no song selection or email drafting advice."""
def knowledge(facts):
    sentences=dict(
        merge='For this edit, '+('merge' if facts['merge'] else 'do not merge')+' different editions with the same ISRC.',
        harbor_liked='T6 Harbor is '+('currently liked.' if facts['harbor_liked'] else 'not currently liked.'),
        t2_isrc='The recording ISRC for T2 is '+facts['t2_isrc']+'.')
    return {k:dict(value=v,answer=sentences[k]) for k,v in facts.items()}
