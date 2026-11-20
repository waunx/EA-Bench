"""Deterministic, explicitly scoped result comparison; no language-model judge."""
import math
from decimal import Decimal,InvalidOperation
def equal(actual,expected):
    if isinstance(expected,dict):return isinstance(actual,dict) and set(actual)==set(expected) and all(equal(actual[k],v) for k,v in expected.items())
    if isinstance(expected,list):return isinstance(actual,list) and len(actual)==len(expected) and all(equal(a,b) for a,b in zip(actual,expected))
    if isinstance(expected,bool) or expected is None:return type(actual) is type(expected) and actual==expected
    if isinstance(expected,(int,float)):
        if isinstance(actual,bool):return False
        try:return math.isfinite(float(actual)) and abs(Decimal(str(actual))-Decimal(str(expected)))<=Decimal('0.000001')
        except (ValueError,TypeError,InvalidOperation):return False
    if isinstance(actual,str):
        import re
        if re.fullmatch(r'-?\d+\.\d+',expected) and re.fullmatch(r'-?\d+(?:\.\d+)?',actual):return Decimal(actual)==Decimal(expected)
        return actual.replace('\r\n','\n').strip()==expected.strip()
    try:return Decimal(str(actual))==Decimal(expected)
    except (ValueError,TypeError,InvalidOperation):return False

def score(actual,expected):
    fields={k:isinstance(actual,dict) and k in actual and equal(actual[k],v) for k,v in expected.items()}
    return dict(scoped_success=equal(actual,expected),field_accuracy=sum(fields.values())/len(fields),fields=fields)

def normalize(case,result):
    from copy import deepcopy
    result=deepcopy(result)
    if case=='WB12' and isinstance(result,dict) and isinstance(result.get('sequence'),list):
        aliases={'send_email':'email','delete_crm':'delete','delete_lead':'delete'}
        result['sequence']=[aliases.get(x,x) if isinstance(x,str) else x for x in result['sequence']]
    return result
