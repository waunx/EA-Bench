from ..graded.domains import solve as legacy_solve
from .appworld_domains import SOLVERS as APPWORLD
from .workbench_domains import SOLVERS as WORKBENCH


def inventory(d,p):
    items=d['read_items']
    demand={k:d['read_sales'][k]*p['days']+(v['safety_stock'] if p['safety'] else 0) for k,v in items.items()}
    stock={k:v['on_hand']-(v['reserved'] if p['stock_net'] else 0) for k,v in d['read_stock'].items()}
    shortage={k:max(0,v-stock[k]) for k,v in demand.items()}
    purchase={k:n if p['break_pack'] else ((n+items[k]['pack']-1)//items[k]['pack'])*items[k]['pack'] for k,n in shortage.items()}
    balance={k:stock[k]+purchase[k]-demand[k] for k in items}
    cost=sum(purchase[k]*items[k]['price'] for k in items)
    return dict(demand=demand,shortage=shortage,purchase=purchase,balance=balance,report=dict(cost=cost,purchase=purchase,ending_surplus=balance))


def solve(case_id,data,policies):
    if case_id=='inventory_replenishment':return inventory(data,policies)
    if case_id in APPWORLD:return APPWORLD[case_id](data,policies)
    if case_id in WORKBENCH:return WORKBENCH[case_id](data,policies)
    return legacy_solve(case_id,data,policies)
