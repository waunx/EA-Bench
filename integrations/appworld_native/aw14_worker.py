"""Isolated AW14 Splitwise API effects; invoked by host with a preserved request."""
import argparse,json
from pathlib import Path
from integrations.appworld_native.aw14_binding import NativeAW14

def run(request,output):
    e=NativeAW14(request['variant'],request['answers'],request['experiment_name'])
    e.confirm(e.answers)
    try:
        for action in request['actions']:e.step(action)
        if request.get('fault')=='duplicate_share':
            expense=e.models.Expense.by_id(e.expense_map['E02'])
            duplicate=expense.expense_shares[0].to_dict(keep_computed=False)
            duplicate.pop('id')
            e.models.ExpenseShare.create_save(**duplicate)
        checks=e.native_checks()
        result=dict(native_passed=all(checks.values()),native_checks=checks,
                    supplemental=e.checker.final({'summary':'Completed'}).to_dict(),
                    native_calls=e.native_calls,native_state=e.native_snapshot(),
                    mapping=dict(expenses=e.expense_map,members={k:v.id for k,v in e.members.items()},group=e.group.id),
                    original_evaluator_runs=0,
                    projection='Authored Splitwise group, identities and initial expenses seeded over original task; category/month and bill/credit provenance stay supplemental')
        output.write_text(json.dumps(result,indent=2,default=str)+'\n')
    finally:e.native.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--request',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(json.loads(a.request.read_text()),a.output)
