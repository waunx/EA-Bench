"""WB12 factual clarification without deletion or email-branch advice."""
def knowledge(facts):
    text=dict(measurement='Quality review identifies Z7 as '+('a genuine zero observation.' if facts['measurement'] else 'a missing-data placeholder.'),
        l2_owner='The current assigned owner of L2 is '+facts['l2_owner']+'.',
        l5_deleted='The current deleted flag of L5 is '+facts['l5_deleted']+'.')
    return {k:dict(value=v,answer=text[k]) for k,v in facts.items()}
