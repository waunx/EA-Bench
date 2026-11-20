from copy import deepcopy
from ..domains import solve as legacy_solve


def solve(case_id, data, policies):
    adjusted = deepcopy(data)
    if case_id=='procurement' and policies['installation_included']:
        for row in adjusted['read_quotes']:
            row['install'] = 0
    if case_id=='training' and not policies['a2_authorized']:
        adjusted['read_options'] = [r for r in adjusted['read_options'] if r['id']!='A2']
    if case_id=='reconciliation' and policies['bank_basis']=='posted':
        adjusted['read_bank'] = [r for r in adjusted['read_bank'] if r['posting_status']=='posted']
    answer = legacy_solve(case_id,adjusted,policies)
    if case_id=='workforce':
        salaries = {r['id']:r['monthly_salary'] for r in data['read_candidates']}
        answer['payroll'] = {r:salaries[c]*policies['salary_months'] for r,c in answer['assignment'].items()}
        answer['report']['annual_payroll'] = sum(answer['payroll'].values())
    if case_id=='donor_registry' and policies['corporate_letters']=='separate':
        for key,row in answer['registry'].items():
            if row['type']=='corporate':
                answer['letters'][key]['tier'] = 'corporate'
        answer['report']['major_letters'] = sum(r['tier']=='major' for r in answer['letters'].values())
    return answer
