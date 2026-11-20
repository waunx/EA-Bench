"""AW08 factual clarification knowledge; transport is shared by run_case."""
def knowledge(facts):
    answers=dict(
        pay17_event='PAY17 belongs to event '+facts['pay17_event']+'.',
        a_food="Participant A's final food amount is "+str(facts['a_food'])+' cents.',
        req1_state='The current state of REQ1 is '+facts['req1_state']+'.',
        pay17_amount='The settled amount of PAY17 is '+str(facts['pay17_amount'])+' cents.',
        pay18_state='PAY18 is '+facts['pay18_state']+'.',
        rounding='Allocate residual shared cents by person ID in '+facts['rounding']+' order.')
    return {k:dict(value=v,answer=answers[k]) for k,v in facts.items()}
