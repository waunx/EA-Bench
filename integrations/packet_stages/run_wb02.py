"""WB02 factual clarification, without a winner or computed workload."""
def knowledge(facts):
    text=dict(eligible_y='Yuki '+('is' if facts['eligible_y'] else 'is not')+' eligible to receive new leads this week.',
        same_task='T17 and T18 refer to '+('the same actual task.' if facts['same_task'] else 'two independent tasks.'),
        c_last_lead='Chenwei last received a lead on '+facts['c_last_lead']+'.')
    return {k:dict(value=v,answer=text[k]) for k,v in facts.items()}
