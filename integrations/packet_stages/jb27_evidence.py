"""JB27 source arithmetic; hidden world never supplies missing readings."""
from pathlib import Path
import json,re,math,hashlib
import openpyxl
from .artifact_adapter_jb27 import PACKET,ROOT

def interp(points,key,target=180):
 for a,b in zip(points,points[1:]):
  if a['flow'] is None or b['flow'] is None:continue
  if a['flow']<=target<=b['flow']:
   if a[key] is None or b[key] is None:return None
   return a[key]+(b[key]-a[key])*(target-a['flow'])/(b['flow']-a['flow'])
 return None

def bearing(rpm,z,dw,dm):
 x=dw/dm;orders=dict(BPFO=z/2*(1-x),BPFI=z/2*(1+x),BSF=dm/(2*dw)*(1-x*x),FTF=.5*(1-x))
 return dict(assumed_geometry=dict(balls=z,ball_diameter_mm=dw,pitch_diameter_mm=dm,contact_angle_deg=0),orders=orders,frequencies_hz={k:v*rpm/60 if rpm is not None else None for k,v in orders.items()},scope='Illustrative approximate geometry, not manufacturer-certified; supported alternatives require recomputation.')
def build(variant,world=None,clarification_records=None):
 p=PACKET/'variants'/variant/'inputs';w=openpyxl.load_workbook(p/'vibration_test_data.xlsx',data_only=True);data={s.title:list(s.values) for s in w};w.close();w=openpyxl.load_workbook(p/'pump_specification_datasheet.xlsx',data_only=True);ds={s.title:list(s.values) for s in w};w.close()
 perf=[list(r) for r in data['Performance Data'][4:11]];spec=ds['Pump Datasheet'];aor=re.search(r'30-(\d+)%',spec[23][1]);facts=dict(speed=perf[5][9],power=perf[5][5],aor_pct=int(aor[1]) if aor else None)
 for record in clarification_records or []:
  for item in record.get('provided',[]):
   if item['fact_id'] in facts:facts[item['fact_id']]=item['value']
 perf[5][9]=facts['speed'];perf[5][5]=facts['power'];corrected=[]
 for r in perf:
  ratio=2970/r[9] if r[9] is not None else None
  eta=997*9.80665*r[1]/3600*r[4]/(r[5]*1000)*100 if r[5] is not None else None
  corrected.append(dict(point=r[0],raw=r,ratio=ratio,flow=r[1]*ratio if ratio else None,head=r[4]*ratio**2 if ratio else None,power=r[5]*ratio**3 if ratio and r[5] is not None else None,reported_efficiency=r[6],energy_balance_efficiency=eta,reported_efficiency_consistent=abs(eta-r[6])<1 if eta is not None else None))
 rated={k:interp(corrected,k) for k in ['head','power','reported_efficiency','energy_balance_efficiency']}
 rated['head_pass']=abs(rated['head']-45)<=.03*45 if rated['head'] is not None else None;rated['power_pass']=rated['power']<=58*1.04 if rated['power'] is not None else None
 def limits(flow):
  if flow is None:return dict(range='unresolved',overall=None,discrete=None)
  if flow<54:return dict(range='outside_AOR',overall=None,discrete=None)
  if 126<=flow<=198:return dict(range='POR',overall=3.0,discrete=2.0)
  if flow<126 or (facts['aor_pct'] is not None and flow<=180*facts['aor_pct']/100):return dict(range='AOR_outside_POR',overall=3.9,discrete=2.6)
  return dict(range='unresolved' if facts['aor_pct'] is None else 'outside_AOR',overall=None,discrete=None)
 vibration=[]
 def zone(x):return 'A' if x<=3.2 else 'B' if x<=5.1 else 'C' if x<=8.5 else 'D'
 for r,corr in zip(data['Bearing Housing Vibration'][4:11],corrected):
  lim=limits(r[1]);vibration.append(dict(point=r[0],actual_flow=r[1],de_overall=r[9],nde_overall=r[10],nominal_limits=lim,corrected_flow_sensitivity=limits(corr['flow']),de_pass=r[9]<=lim['overall'] if lim['overall'] else None,nde_pass=r[10]<=lim['overall'] if lim['overall'] else None,de_magnitude_zone=zone(r[9]),nde_magnitude_zone=zone(r[10])))
 spectra={};bearing_data={}
 for sheet,rpm in [('Vibration Spectrum - Rated Flow',facts['speed']),('Vibration Spectrum - 120% Flow',perf[6][9])]:
  samples=data[sheet][4:];peaks={}
  for label,lo,hi in [('1x',45,54),('2x',95,103),('3x',145,152),('VPF',290,303)]:
   peaks[label]=max([dict(hz=f,amplitude=a) for f,a in samples if lo<=f<=hi],key=lambda x:x['amplitude'])
  spectra[sheet]=dict(header=data[sheet][1][0],samples=samples,peaks=peaks,shaft_hz=rpm/60 if rpm else None,vane_pass_hz=6*rpm/60 if rpm else None)
  bearing_data[sheet]=dict(DE=bearing(rpm,8,22.23,102.5),NDE=bearing(rpm,8,20.638,87.5))
 names=list(spectra);growth={k:100*(spectra[names[1]]['peaks'][k]['amplitude']/spectra[names[0]]['peaks'][k]['amplitude']-1) for k in ['1x','2x','VPF']}
 refs=json.loads((PACKET/'private/reference_evidence.json').read_text())
 for n,r in refs.items():
  path=p/n if n=='pump_IOM_manual.pdf' else ROOT/r['source'];assert hashlib.sha256(path.read_bytes()).hexdigest()==r['sha256']
 return dict(confirmed_facts=facts,clarifications=clarification_records or [],datasheet=ds,test_data=data,corrected=corrected,rated_flow_comparison=rated,vibration=vibration,spectra=spectra,bearing_models=bearing_data,spectral_amplitude_growth_pct=growth,references=refs,supplemental={f.name:json.loads(f.read_text()) for f in p.glob('*.json')},scope='Source arithmetic, nominal-flow applicability and explicit normalized-boundary sensitivity; no fixed disposition or hidden unconfirmed values.')
