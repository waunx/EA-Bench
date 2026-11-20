"""Private JB01 full-analysis reference; never mounted for an evaluated agent."""
from pathlib import Path
import hashlib,json,itertools
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm

REGIONS={
    'Northeast':'CT ME MA NH RI VT NJ NY PA',
    'Midwest':'IL IN MI OH WI IA KS MN MO NE ND SD',
    'South':'DE FL GA MD NC SC VA DC WV AL KY MS TN AR LA OK TX',
    'West':'AZ CO ID MT NV NM UT WY AK CA HI OR WA'}
REGION={s:region for region,codes in REGIONS.items() for s in codes.split()}
COVARIATES=['obesity','poverty','education','income','unemployment']
class Unresolved(ValueError):pass

def read_csv(path):return pd.read_csv(path,dtype=str,keep_default_na=False,encoding='utf-8-sig')
def resolve(raw,key,claims,answers):
    if raw not in ['',None]:return float(raw)
    records=[r for r in claims if r['fact']==key]
    if records:
        top=max(r['revision'] for r in records);values={r['value'] for r in records if r['revision']==top}
        if len(values)==1:return float(next(iter(values)))
    if key not in answers:raise Unresolved(key)
    return float(answers[key])

def prepare(input_dir,reference_dir,answers):
    inp,ref=Path(input_dir),Path(reference_dir)
    claims=json.loads((inp/'source_records.json').read_text()) if (inp/'source_records.json').exists() else []
    life=read_csv(inp/'state_life_expectancy.csv');obesity=read_csv(inp/'state_obesity_data.csv');demo=read_csv(inp/'state_demographics.csv')
    for filename,frame in [('county_supplement.json','life'),('stratified_obesity.json','obesity')]:
        if (inp/filename).exists():
            supplement=pd.DataFrame([json.loads((inp/filename).read_text())])
            if frame=='life':life=pd.concat([life,supplement],ignore_index=True).fillna('')
            else:obesity=pd.concat([obesity,supplement],ignore_index=True).fillna('')
    life=life[life.County.isin(['','(blank)']) & life['Census Tract Number'].eq('')].copy()
    obs=obesity[obesity.YearStart.eq('2023') & obesity.Stratification1.eq('Total')].copy()
    if life.State.duplicated().any() or obs.LocationDesc.duplicated().any():raise Unresolved('Duplicate state-level source')
    y=dict(zip(life.State,life['Life Expectancy']));x=dict(zip(obs.LocationDesc,obs.Data_Value))
    z=dict(zip(demo.State,demo["Education.Bachelor's Degree or Higher"]))
    for values,key in [(y,'life'),(x,'obesity'),(z,'education')]:values['Alabama']=resolve(values['Alabama'],key,claims,answers)
    if (inp/'education_copy.json').exists():
        replica=json.loads((inp/'education_copy.json').read_text())
        if replica['bachelor_percent']!=z['Alabama']:raise Unresolved('Education replica disagreement')
    states=sorted(set(y)&set(x)&set(z));clean=pd.DataFrame([dict(state=s,life=float(y[s]),obesity=float(x[s]),education=float(z[s])) for s in states])
    p=read_csv(ref/'state_poverty_2023.csv');p['fips_num']=pd.to_numeric(p.FIPS_Code)
    p=p[(p.fips_num>0)&(p.fips_num%1000==0)]
    p=p[p.Attribute.isin(['PCTPOVALL_2023','MEDHHINC_2023'])].pivot(index=['FIPS_Code','Stabr','Area_Name'],columns='Attribute',values='Value').reset_index()
    p=p.rename(columns={'Area_Name':'state','Stabr':'abbr','PCTPOVALL_2023':'poverty','MEDHHINC_2023':'income'})
    p['fips']=p.FIPS_Code.astype(int).astype(str).str.zfill(5)
    clean=clean.merge(p[['state','abbr','fips','poverty','income']],on='state',how='left',validate='one_to_one')
    u=read_csv(ref/'state_unemployment_2023.csv');u['fips_num']=pd.to_numeric(u.FIPS_Code)
    u=u[(u.fips_num>0)&(u.fips_num%1000==0)&u.Attribute.eq('Unemployment_rate_2023')]
    clean=clean.merge(u[['State','Value']].rename(columns={'State':'abbr','Value':'unemployment'}),on='abbr',how='left',validate='one_to_one')
    v=pd.read_csv(ref/'covid_vax_final_snapshot.csv',usecols=['Date','Location','Series_Complete_Pop_Pct'])
    v['date']=pd.to_datetime(v.Date);v=v[v.date.dt.year.eq(2021)&v.date.dt.month.eq(12)&v.Location.isin(REGION)]
    snapshot=v.date.max();v=v[v.date.eq(snapshot)]
    clean=clean.merge(v[['Location','Series_Complete_Pop_Pct']].rename(columns={'Location':'abbr','Series_Complete_Pop_Pct':'vaccination'}),on='abbr',how='left',validate='one_to_one')
    clean['region']=clean.abbr.map(REGION);clean['obesity_year']=2023;clean['vaccination_date']=snapshot.date().isoformat()
    for c in ['life',*COVARIATES,'vaccination']:clean[c]=pd.to_numeric(clean[c],errors='raise')
    if clean.isna().any().any():raise ValueError('Missing cross-source value; requires an explicit data decision')
    for c in ['obesity','poverty','education','unemployment','vaccination']:
        if not clean[c].between(0,100).all():raise ValueError('Implausible percentage: '+c)
    if not clean.life.between(0,120).all() or not clean.income.gt(0).all():raise ValueError('Implausible life expectancy or income')
    sources={str(p.name):hashlib.sha256(p.read_bytes()).hexdigest() for folder in [inp,ref] for p in folder.iterdir() if p.is_file()}
    quality=dict(primary_obesity_year=2023,states=len(clean),excluded_outcome_states=sorted(set(y)-set(states)),vaccination_snapshot=snapshot.date().isoformat(),duplicate_state_rows=0,
        limitations=['Life-expectancy source vintage is not documented in the supplied file.','Education and other demographic fields are from an older mixed-vintage extract.','2021 vaccination is exploratory, not a temporally aligned causal adjustment.'],source_hashes=sources)
    return clean.sort_values('state').reset_index(drop=True),quality

def fit_model(data,predictors):
    design=sm.add_constant(data[predictors].astype(float),has_constant='add')
    return sm.OLS(data.life.astype(float),design).fit()

def coef_table(model,data,label):
    ci=model.conf_int();robust=model.get_robustcov_results(cov_type='HC3');rci=robust.conf_int();rows=[]
    for i,k in enumerate(model.params.index):
        beta=None if k=='const' else model.params[k]*data[k].std(ddof=1)/data.life.std(ddof=1)
        rows.append(dict(model=label,predictor=k,coefficient=model.params[k],se=model.bse[k],ci_low=ci.loc[k,0],ci_high=ci.loc[k,1],p=model.pvalues[k],standardized_beta=beta,hc3_ci_low=rci[i,0],hc3_ci_high=rci[i,1]))
    return pd.DataFrame(rows)

def analyze(clean):
    d=clean.copy();regional=pd.get_dummies(d.region,prefix='region',drop_first=True,dtype=float);d=pd.concat([d,regional],axis=1)
    specs={'M1_obesity':['obesity'],'M2_adjusted':COVARIATES,'M3_region_fixed':COVARIATES+list(regional),'M4_vaccination_exploratory':COVARIATES+['vaccination']}
    models={name:fit_model(d,cols) for name,cols in specs.items()}
    coefs=pd.concat([coef_table(m,d,k) for k,m in models.items()],ignore_index=True)
    fits=pd.DataFrame([dict(model=k,n=int(m.nobs),r2=m.rsquared,adjusted_r2=m.rsquared_adj,aic=m.aic,bic=m.bic,log_likelihood=m.llf) for k,m in models.items()])
    comparisons=[]
    for small,big in [('M1_obesity','M2_adjusted'),('M2_adjusted','M3_region_fixed'),('M2_adjusted','M4_vaccination_exploratory')]:
        a,b=models[small],models[big];lr=2*(b.llf-a.llf);df=int(b.df_model-a.df_model)
        comparisons.append(dict(smaller=small,larger=big,lr_statistic=lr,df=df,p=stats.chi2.sf(lr,df)))
    correlations=[];variables=['life',*COVARIATES,'vaccination'];n=len(d)
    for a,b in itertools.combinations(variables,2):
        r=float(d[a].corr(d[b]));z=np.arctanh(np.clip(r,-1+1e-12,1-1e-12));delta=stats.norm.ppf(.975)/np.sqrt(n-3)
        correlations.append(dict(variable_1=a,variable_2=b,n=n,r=r,ci_low=np.tanh(z-delta),ci_high=np.tanh(z+delta)))
    vifs=[]
    for name in COVARIATES:
        others=[c for c in COVARIATES if c!=name]
        aux=sm.OLS(d[name],sm.add_constant(d[others],has_constant='add')).fit()
        vifs.append(dict(predictor=name,vif=1/(1-aux.rsquared)))
    groups=[g.life.to_numpy() for _,g in d.groupby('region')];k=len(groups)
    grand=d.life.mean();ss_between=sum(len(g)*(g.mean()-grand)**2 for g in groups)
    ss_within=sum(((g-g.mean())**2).sum() for g in groups)
    msb=ss_between/(k-1);msw=ss_within/(n-k);effective_n=(n-sum(len(g)**2 for g in groups)/n)/(k-1)
    icc=(msb-msw)/(msb+(effective_n-1)*msw)
    clustering=dict(regions=k,states=n,ms_between=msb,ms_within=msw,effective_group_size=effective_n,icc_untruncated=icc,icc_nonnegative=max(0,icc))
    base=models['M2_adjusted'];influence=base.get_influence()
    diagnostics=pd.DataFrame(dict(state=d.state,fitted=base.fittedvalues,residual=base.resid,leverage=influence.hat_matrix_diag,cooks_d=influence.cooks_distance[0]))
    removed=diagnostics.sort_values(['leverage','state'],ascending=[False,True]).head(3).state.tolist()
    kept=d[~d.state.isin(removed)].copy();after=fit_model(kept,COVARIATES)
    sensitivity=pd.concat([coef_table(base,d,'before'),coef_table(after,kept,'after_top3_leverage_removal')],ignore_index=True)
    before_beta=float(base.params['obesity']);after_beta=float(after.params['obesity'])
    stability=dict(removed_states=removed,before_n=n,after_n=len(kept),relative_coefficient_change=abs((after_beta-before_beta)/before_beta),
        sign_change=bool(before_beta*after_beta<0),significance_change=bool((base.pvalues['obesity']<.05)!=(after.pvalues['obesity']<.05)))
    stability['substantive_change']=bool(stability['relative_coefficient_change']>.2 or stability['sign_change'] or stability['significance_change'])
    for model in models.values():
        independent=np.linalg.lstsq(model.model.exog,model.model.endog,rcond=None)[0]
        if not np.allclose(independent,model.params.to_numpy(),rtol=1e-8,atol=1e-8):raise AssertionError('Independent coefficient check failed')
    descriptives=d.groupby('region')[variables].agg(['count','mean','std']).stack(level=0).reset_index().rename(columns={'level_1':'variable'})
    return dict(clean=clean,descriptive=descriptives,correlations=pd.DataFrame(correlations),coefficients=coefs,fit=fits,
        lr_tests=pd.DataFrame(comparisons),vif=pd.DataFrame(vifs),clustering=clustering,diagnostics=diagnostics,
        sensitivity=sensitivity,stability=stability,models=models)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--inputs',required=True);parser.add_argument('--references',required=True)
    parser.add_argument('--answers');parser.add_argument('--output',required=True);args=parser.parse_args()
    answers=json.loads(Path(args.answers).read_text()) if args.answers else {}
    clean,quality=prepare(args.inputs,args.references,answers);result=analyze(clean);out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    for key,value in result.items():
        if isinstance(value,pd.DataFrame):value.to_csv(out/(key+'.csv'),index=False)
    for key,value in dict(quality=quality,clustering=result['clustering'],stability=result['stability']).items():
        (out/(key+'.json')).write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps(dict(states=len(clean),excluded=quality['excluded_outcome_states'],icc=result['clustering']['icc_untruncated'],stability=result['stability']),indent=2))
