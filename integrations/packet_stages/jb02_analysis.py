"""Private reproducible reference calculations for JB02."""
from pathlib import Path
import json,sqlite3
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.formula.api as smf
from shapely.geometry import shape
OUTCOMES=['OBESITY','DIABETES','DEPRESSION']
def read_csv(p):
 try:return pd.read_csv(p,dtype=str,encoding='utf-8-sig')
 except UnicodeDecodeError:return pd.read_csv(p,dtype=str,encoding='latin1')
def wide(path):
 d=read_csv(path);d=d.rename(columns={d.columns[0]:'FIPS'});d.FIPS=d.FIPS.str.zfill(5)
 d=d[d.FIPS.str.fullmatch(r'\d{5}') & ~d.FIPS.str.endswith('000')].copy()
 d.Value=pd.to_numeric(d.Value.str.replace(',',''),errors='coerce')
 assert not d.duplicated(['FIPS','Attribute']).any()
 return d.pivot(index='FIPS',columns='Attribute',values='Value')
def prepare(inputs,refs):
 inputs,refs=Path(inputs),Path(refs);h=read_csv(inputs/'cdc_places_county_health_measures.csv')
 for name in ['tract_health_extract','adjusted_health_extract','county_health_copy']:
  p=inputs/(name+'.json')
  if p.exists():h=pd.concat([h,pd.DataFrame([json.loads(p.read_text())])],ignore_index=True)
 h=h[h.LocationID.str.fullmatch(r'\d{5}') & ~h.LocationID.str.endswith('000') & h.DataValueTypeID.eq('CrdPrv')].copy()
 assert h.groupby(['Year','LocationID','MeasureId']).Data_Value.nunique().max()==1
 h=h.drop_duplicates(['Year','LocationID','MeasureId'])
 h.Data_Value=pd.to_numeric(h.Data_Value,errors='coerce');health=h.pivot(index='LocationID',columns='MeasureId',values='Data_Value');health.index.name='FIPS'
 names=h.drop_duplicates('LocationID').set_index('LocationID')[['LocationName','StateAbbr','StateDesc']].rename(columns={'LocationName':'county','StateAbbr':'state','StateDesc':'state_name'})
 p=wide(inputs/'poverty_estimates_2023.csv');u=wide(refs/'unemployment_income_2000_23.csv');e=wide(refs/'education_attainment_1970_2023.csv');pop=wide(refs/'population_estimates_2020_23.csv')
 current=pd.DataFrame({'poverty':p.PCTPOVALL_2023,'income':p.MEDHHINC_2023,'unemployment':u.Unemployment_rate_2023,'education':e["Percent of adults with a bachelor's degree or higher, 2019-23"],'population':pop.POP_ESTIMATE_2023})
 historical=pd.DataFrame({'unemployment_2010':u.Unemployment_rate_2010,'unemployment_2023':u.Unemployment_rate_2023,'income_2022':u.Median_Household_Income_2022,'income_2023':p.MEDHHINC_2023})
 historical['unemployment_change']=historical.unemployment_2023-historical.unemployment_2010;historical['income_change']=historical.income_2023-historical.income_2022
 dynamics=pd.DataFrame({'net_migration_rate':pop.R_NET_MIG_2023,'natural_change_rate':pop.R_NATURAL_CHG_2023,'population_change':pop.POP_ESTIMATE_2023-pop.CENSUS_2020_POP})
 identifiers=names.join(pop[['Rural_Urban_Continuum_Code_2023','Economic_typology_2015']].rename(columns={'Rural_Urban_Continuum_Code_2023':'RUCC','Economic_typology_2015':'economic_typology'}),how='outer')
 tables={'county_identifiers':identifiers,'socioeconomic_current':current,'socioeconomic_historical':historical,'health_outcomes':health,'demographic_dynamics':dynamics}
 universe=set().union(*(set(t.index) for t in tables.values()));ex=[];keep=[]
 for fips in sorted(universe):
  reasons=['missing_'+name for name,t in tables.items() if fips not in t.index or t.loc[fips].isna().any()]
  if reasons:ex.append({'FIPS':fips,'reason_code':';'.join(reasons)})
  else:keep.append(fips)
 tables={k:t.loc[keep].rename_axis('FIPS') for k,t in tables.items()};tables['exclusions']=pd.DataFrame(ex,columns=['FIPS','reason_code']).set_index('FIPS')
 return tables

def database(tables,out):
 with sqlite3.connect(out) as db:
  for name,t in tables.items():
   t.to_sql(name,db,if_exists='replace',index=True);db.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS idx_{name}_fips ON {name}(FIPS)')

def analyze(dbpath,geometry):
 with sqlite3.connect(dbpath) as db:
  d=pd.read_sql_query('SELECT i.*,c.*,h.*,s.unemployment_change,s.income_change,g.* FROM county_identifiers i JOIN socioeconomic_current c USING(FIPS) JOIN socioeconomic_historical s USING(FIPS) JOIN health_outcomes h USING(FIPS) JOIN demographic_dynamics g USING(FIPS)',db)
 d=d.loc[:,~d.columns.duplicated()].copy();d['income_10k']=d.income/10000;d['income_change_10k']=d.income_change/10000
 measures=list(pd.read_sql_query('SELECT * FROM health_outcomes LIMIT 1',sqlite3.connect(dbpath)).columns.drop('FIPS'))
 d['tercile']=pd.qcut(d.unemployment_change,3,labels=['T1','T2','T3']);matrix=[]
 for m in measures:
  groups=[d.loc[d.tercile.eq(t),m] for t in ['T1','T2','T3']];f,p=stats.f_oneway(*groups)
  matrix.append(dict(measure=m,T1=groups[0].mean(),T2=groups[1].mean(),T3=groups[2].mean(),F=f,p=p))
 static='poverty + income_10k + unemployment + education + population + C(RUCC)'
 dynamic=static+' + unemployment_change + income_change_10k + net_migration_rate'
 fits=[];coef=[];outliers=[];decomp=[];models={};state_res={}
 for outcome in OUTCOMES:
  a=smf.ols(outcome+' ~ '+static,d).fit();b=smf.ols(outcome+' ~ '+dynamic,d).fit();lr=2*(b.llf-a.llf);df=int(b.df_model-a.df_model);lp=stats.chi2.sf(lr,df);best=b if lp<.05 else a
  for label,m in [('static',a),('dynamic',b)]:
   models[outcome+'_'+label]=m
   fits.append(dict(outcome=outcome,model=label,n=int(m.nobs),r_squared=m.rsquared,AIC=m.aic,BIC=m.bic,log_likelihood=m.llf,LR=lr,df=df,p=lp,best='dynamic' if lp<.05 else 'static'))
   for term,val in m.params.items():coef.append(dict(outcome=outcome,model=label,term=term,coefficient=val,standard_error=m.bse[term],p=m.pvalues[term],ci_low=m.conf_int().loc[term,0],ci_high=m.conf_int().loc[term,1]))
  residual=best.resid;sd=residual.std(ddof=1);flag=d.loc[abs(residual)>2*sd,['FIPS','county','state']].copy();flag['outcome']=outcome;flag['predicted']=best.fittedvalues[flag.index];flag['observed']=d.loc[flag.index,outcome];flag['residual']=residual[flag.index];outliers.append(flag)
  state_res[outcome]=pd.DataFrame({'state':d.state_name,'residual':residual}).groupby('state').residual.mean()
  metro=d.RUCC.le(3).to_numpy();x=a.model.exog;gap=d.loc[metro,outcome].mean()-d.loc[~metro,outcome].mean();explained=(x[metro].mean(axis=0)-x[~metro].mean(axis=0))@a.params.to_numpy()
  decomp.append(dict(outcome=outcome,gap_metro_minus_nonmetro=gap,explained=explained,unexplained=gap-explained,metro_n=int(metro.sum()),nonmetro_n=int((~metro).sum())))
 features=json.loads(Path(geometry).read_text())['features'];shapes={f['properties']['name']:shape(f['geometry']) for f in features}
 spatial=[];rng=np.random.default_rng(2083)
 for outcome,s in state_res.items():
  names=sorted((set(s.index)&set(shapes))-{'Alaska','Hawaii','Puerto Rico'});w=np.array([[int(i!=j and shapes[i].intersects(shapes[j])) for j in names] for i in names],dtype=float)
  active=w.sum(axis=1)>0;names=[n for n,a in zip(names,active) if a];w=w[np.ix_(active,active)];w/=w.sum(axis=1)[:,None];z=s.loc[names].to_numpy();z-=z.mean();n=len(z)
  def moran(v):return n/w.sum()*(v@w@v)/(v@v)
  I=moran(z);expected=-1/(n-1);sims=np.array([moran(rng.permutation(z)) for _ in range(999)])
  spatial.append(dict(outcome=outcome,I=I,expected=expected,p=(1+sum(abs(sims-expected)>=abs(I-expected)))/1000,n=n,permutations=999))
 cov='income_10k + unemployment + education + population + C(RUCC)'
 ma=smf.ols('LPA ~ poverty + '+cov,d).fit();mb=smf.ols('OBESITY ~ poverty + LPA + '+cov,d).fit();total=smf.ols('OBESITY ~ poverty + '+cov,d).fit()
 xa,ya=ma.model.exog,ma.model.endog;xb,yb=mb.model.exog,mb.model.endog;ai=ma.model.exog_names.index('poverty');bi=mb.model.exog_names.index('LPA');boot=[]
 for _ in range(1000):
  ix=rng.integers(0,len(d),len(d));boot.append(np.linalg.lstsq(xa[ix],ya[ix],rcond=None)[0][ai]*np.linalg.lstsq(xb[ix],yb[ix],rcond=None)[0][bi])
 mediation=dict(a=ma.params['poverty'],b=mb.params['LPA'],direct=mb.params['poverty'],total=total.params['poverty'],indirect=ma.params['poverty']*mb.params['LPA'],ci_low=np.quantile(boot,.025),ci_high=np.quantile(boot,.975),bootstrap_n=1000)
 from statsmodels.stats.outliers_influence import variance_inflation_factor
 model=models['OBESITY_dynamic'];vif=pd.DataFrame([dict(term=t,VIF=variance_inflation_factor(model.model.exog,i)) for i,t in enumerate(model.model.exog_names) if t!='Intercept'])
 return dict(data=d,matrix=pd.DataFrame(matrix),decomposition=pd.DataFrame(decomp),outliers=pd.concat(outliers),fits=pd.DataFrame(fits),coefficients=pd.DataFrame(coef),spatial=pd.DataFrame(spatial),state_residuals=state_res,mediation=mediation,vif=vif,models=models)
