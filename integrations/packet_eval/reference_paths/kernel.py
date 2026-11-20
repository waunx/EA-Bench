import ast,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];SOURCE=ROOT/'data/authored'
SPECIAL={'AW01','AW04','AW08','JB03','JB11','WB02','WB14'}
class RemoveOracleAssertions(ast.NodeTransformer):
 def visit_Assert(self,node):
  if any(isinstance(x,ast.Name) and x.id=='O' for x in ast.walk(node)):return None
  if any(isinstance(x,ast.Subscript) and isinstance(x.slice,ast.Constant) and x.slice.value in {'default','alternative'} for x in ast.walk(node)):return None
  return node

def extract(case):
 p=SOURCE/case/'check.py';tree=ast.parse(p.read_text());out=[];defined=set()
 for node in tree.body:
  if isinstance(node,(ast.Import,ast.ImportFrom,ast.ClassDef)):out.append(node)
  elif isinstance(node,ast.FunctionDef) and node.name not in {'expected','audit','redundancy_control','run','collect_questions'}:
   out.append(RemoveOracleAssertions().visit(node));defined.add(node.name)
  elif isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
   if isinstance(node.value,ast.Name) and node.value.id in defined:
    out.append(node);defined.add(node.targets[0].id)
   elif node.targets[0].id=='ALIASES':out.append(node)
 text=ast.unparse(ast.fix_missing_locations(ast.Module(body=out,type_ignores=[])))
 for var in ['v','variant']:text=text.replace("ROOT / 'variants' / "+var+" / 'inputs'",'INPUTS')
 if case=='JB03':
  o=json.load(open(SOURCE/case/'private/oracle.json'))
  fields={k:{n:a[n] for n in ['table','id','field']} for k,a in o['atoms'].items()}
  text=text.replace("O['atoms']",'FIELD_MAP')
  text='FIELD_MAP='+repr(fields)+'\n'+text
 assert not any(isinstance(x,ast.Name) and x.id in {'O','EXPECTED','DEFAULT','SINGLES'} for x in ast.walk(ast.parse(text))),case
 return text

def environment(case, inputs):
 env={'INPUTS':Path(inputs)}
 exec(extract(case),env)
 return env

def read_data(case,env):
 return env['load']('selected') if case in SPECIAL else env['collect'](env['INPUTS'])

def decide(case,env,data,answers):
 result=env['solve'](data,answers) if case in SPECIAL-{'JB03','JB11'} else env['project'](data,answers)
 return env['actions'](result) if case=='AW08' else result
