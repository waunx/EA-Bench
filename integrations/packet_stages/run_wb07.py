"""WB07 facts only, without a threshold result or chosen assignee."""
def knowledge(facts):
    names={'NIA':'Nia Johnson','LUIS':'Luis Ortiz'}
    text=dict(qa='The quality review for backfill BF7 is '+('accepted.' if facts['qa'] else 'rejected.'),
        t3_owner='The owner of completed task T3 is '+names[facts['t3_owner']]+'.',
        p2_sessions='P2 revision 1 contains '+str(facts['p2_sessions'])+' measured sessions.')
    return {k:dict(value=v,answer=text[k]) for k,v in facts.items()}
