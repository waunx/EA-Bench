"""AW14 factual clarification; no computed net amounts or share recommendations."""
def knowledge(facts):
    text=dict(active='Credit CR2 against B02 is '+('currently effective.' if facts['active'] else 'not currently effective.'),
        march='Bill B03 has a gross amount of '+str(facts['march'])+' cents.',
        credit='Credit CR2 against B02 has an adjustment amount of '+str(facts['credit'])+' cents.')
    return {k:dict(value=v,answer=text[k]) for k,v in facts.items()}
