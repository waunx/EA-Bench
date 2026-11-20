"""WB14 factual answers without selecting the branch or scheduling actions."""
def knowledge(facts):
    minute=facts['busy_end'];clock=f'{minute//60:02d}:{minute%60:02d}'
    names={'F_KHAN':'Fatima Khan','F_RAHMAN':'Fatima Rahman'}
    text=dict(busy_end='The confirmed CAL1 appointment ends at '+clock+'.',
        recipient='The Fatima intended for this follow-up is '+names[facts['recipient']]+'.',
        qa='The quality review for backfill QC2 is '+('accepted.' if facts['qa'] else 'rejected.'),
        calendar_state='The current status of CAL3 is '+facts['calendar_state']+'.',
        workspace='This follow-up belongs to workspace '+facts['workspace']+'.',
        lead_state='The current deleted flag of NL2 is '+facts['lead_state']+'.')
    return {k:dict(value=v,answer=text[k]) for k,v in facts.items()}
