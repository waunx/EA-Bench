"""AW12 facts without catalog-match or migration-plan advice."""
def knowledge(facts):
    text=dict(batch='The authorized backup is '+facts['batch']+'.',
        s2_duration='Recording s2 in backup A has a source duration of '+str(facts['s2_duration'])+' seconds.',
        road_private='Road Trip in backup A is '+('private.' if facts['road_private'] else 'public.'))
    return {k:dict(value=v,answer=text[k]) for k,v in facts.items()}
