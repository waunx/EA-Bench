"""Host-private bound-world native effect gate, separate from original fixed worlds."""
import importlib
import json
from pathlib import Path

VERIFIED_CASES = {'WB01','WB02','WB07','WB12','WB14','AW01','AW02','AW03','AW04','AW06','AW11'}

def apply(engine, result, private):
    if getattr(engine,'case',None) not in VERIFIED_CASES or not result.get('evaluated_samples'):
        return result
    supplemental_success=result['success']
    try:
        name=('integrations.appworld_native.'+engine.case.lower()+'_replay'
              if engine.case.startswith('AW') else
              'integrations.packet_stages.'+engine.case.lower()+'_native')
        module=importlib.import_module(name)
        native=module.evaluate_engine(engine,Path(private)/'native_replay')
        if native['status'] not in {'passed','failed'}:
            raise ValueError('Native effect gate did not produce a verdict')
        result.update(native_api_replays=1,
                      bound_world_evaluator_runs=native['original_algorithm_calls'],
                      native_effect_acceptance=native,
                      supplemental_state_success=supplemental_success,
                      success=bool(supplemental_success and native['status']=='passed'),
                      validation_layer='authored_state_and_bound_native_effect_replay')
    except Exception as exc:
        result.update(success=None,evaluated_samples=0,checker_status='infrastructure_error',
                      supplemental_state_success=supplemental_success,
                      native_effect_error=type(exc).__name__+': '+str(exc))
    # Existing original_evaluator_runs remains the original fixed-world metric.
    (Path(private)/'combined_acceptance.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
