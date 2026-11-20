"""Isolated real-AppWorld worker for AW04 authored worlds and captured effects."""
from ea_bench.paths import APPWORLD_ROOT, APPWORLD_PYTHON
import argparse,json,os,sys,hashlib,faulthandler
faulthandler.dump_traceback_later(60, repeat=True)
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from integrations.appworld_native.aw04_binding import NativeAW04

def run(request,output):
    os.environ['APPWORLD_ROOT']=APPWORLD_ROOT;os.chdir(APPWORLD_ROOT)
    engine=NativeAW04(request['variant'],request['answers'],experiment_name=request['experiment_name'])
    try:
        engine.confirmed=dict(request['answers'])
        for a in request['actions']:
            reply=engine.step(a)
            if 'error' in reply:raise ValueError('Native-bound replay rejected host effect: '+str(reply))
        engine.step(dict(tool='submit',result=dict(summary='Native effect replay.')))
        checks=engine.native_checks();snapshot=engine.native_snapshot();new=set(snapshot['orders'])-set(engine.baseline['orders']);orders=[]
        for identity in new:
            order=engine.models.Order.by_id(identity)
            orders.append(dict(order_id=identity,paid_cents=round(order.paid_amount*100),tax_cents=round(order.tax*100),discount_cents=round(order.discount*100),delivery_fee_cents=round(order.delivery_fee*100),items=[dict(product_id=r.product_id,packs=r.ordered_quantity,price_cents=round(r.price*100),expected_delivery_at=str(r.expected_delivery_at)) for r in order.order_items]))
        result=dict(case='AW04',variant=request['variant'],answers=request['answers'],native_checks=checks,native_passed=all(checks.values()),supplemental_verdict=engine.result,native_calls=engine.native_calls,orders=orders,product_binding=engine.product_map,native_debit_cents=engine.baseline['balance_cents']-snapshot['balance_cents'],financial_projection='Native fees and monthly membership remain unchanged. Authored zone tariff and membership price are checked in supplemental verdict only.',supplemental_only=['zone shipping tariffs','gift tariffs','membership quote','recipient confirmation'],packet_sha256={str(p.relative_to(engine.folder.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in engine.folder.parent.rglob('*') if p.is_file()},provenance='Authored supplemental seed on 30e8586_1 native database, timestamp advanced to 2026-09-29',original_evaluator_runs=0)
        result['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('aw04_*.py')}
        output.write_text(json.dumps(result,indent=2,default=str)+'\n');return result
    finally:engine.native.close()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--request',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(json.loads(a.request.read_text()),a.output)
