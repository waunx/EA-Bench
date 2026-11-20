"""Private full-row numerical evidence; no prescribed artifact cell layout."""
from pathlib import Path
import hashlib,json,sqlite3,math
import numpy as np
import pandas as pd
import scipy
from scipy import stats
LIKERT=['cc_belief','cc_worry','carbon_tax_support','renewable_invest_support','emission_regulation_support','intl_agreement_support','personal_action_willingness','trust_scientists','trust_government']
MODELS={'A':('carbon_tax_support',['cc_belief','cc_worry','political_ideology','education','trust_scientists','gdp_per_capita','climate_vulnerability_index']),'B':('personal_action_willingness',['cc_worry','trust_government','income_level','age','co2_per_capita'])}
ORDINAL={'education':{'Less than high school':1,'High school':2,'Some college':3,'Bachelor degree':4,'Graduate degree':5},'income_level':{'Low':1,'Medium':2,'High':3}}
def finite(x):
 try:
  v=float(x);return v if math.isfinite(v) else None
 except (ValueError,TypeError):return None
def table(c,name):
 c.row_factory=sqlite3.Row
 return [dict(r) for r in c.execute('select * from "'+name.replace('"','""')+'"')]
def evidence(database):
 p=Path(database);c=sqlite3.connect('file:'+str(p.resolve())+'?mode=ro',uri=True)
 names={r[0] for r in c.execute("select name from sqlite_master where type='table'")}
 if 'cleaned_responses' not in names:raise ValueError('No cleaned_responses table')
 rows=table(c,'cleaned_responses');metadata=table(c,'country_metadata') if 'country_metadata' in names else []
 joins=[];demographics={}
 for name in ['cleaned_respondents','respondents']:
  if name in names:
   for r in table(c,name):demographics.setdefault(r.get('respondent_id'),[]).append(r)
   joins.append(name);break
 macro={r.get('country'):r for r in metadata};enriched=[];unresolved=[]
 for r in rows:
  d=dict(r);matches=demographics.get(d.get('respondent_id'),[])
  if len(matches)==1:
   for k,v in matches[0].items():d.setdefault(k,v)
  elif len(matches)>1:unresolved.append(d.get('response_id'))
  for k,v in macro.get(d.get('country'),{}).items():d.setdefault(k,v)
  enriched.append(d)
 c.close();frame=pd.DataFrame(enriched)
 out=dict(reference_engine=dict(numpy=np.__version__,pandas=pd.__version__,scipy=scipy.__version__,sqlite=sqlite3.sqlite_version),database_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),rows=len(rows),full_cleaned_rows=rows,country_metadata=metadata,joined_demographic_table=joins,unresolved_demographic_joins=unresolved,descriptives={},correlations={},models={},limitations=[])
 if not rows:return out
 available=[v for v in LIKERT if v in frame]
 numeric=frame[available].apply(pd.to_numeric,errors='coerce').replace([np.inf,-np.inf],np.nan)
 groups={'Overall':frame.index}
 if 'country' in frame:
  groups.update({str(k):g.index for k,g in frame.groupby('country',dropna=True)})
 for group,index in groups.items():
  out['descriptives'][group]={}
  for v in available:
   s=numeric.loc[index,v].dropna()
   out['descriptives'][group][v]=dict(n=len(s),mean=finite(s.mean()),sample_sd=finite(s.std(ddof=1)),median=finite(s.median()))
 for mode,data in [('pairwise',numeric),('complete_case',numeric.dropna())]:
  corr=[]
  for i,a in enumerate(available):
   for b in available[i:]:
    pair=data[[a,b]].dropna();value=data[a].corr(data[b])
    corr.append(dict(a=a,b=b,n=len(pair),r=finite(value)))
  out['correlations'][mode]=corr
 for label,(outcome,predictors) in MODELS.items():
  missing=[x for x in [outcome]+predictors if x not in frame]
  if missing:
   out['models'][label]=dict(status='unavailable',missing_columns=missing);continue
  categorical=[x for x in predictors if x in ORDINAL and any(finite(v) is None for v in frame[x].dropna())]
  candidates=['as_recorded_numeric'] if not categorical else ['ordinal_reference','categorical_reference']
  refs=[]
  for candidate in candidates:
   work=frame[[outcome]+predictors].copy();mappings={}
   for col in [outcome]+predictors:
    if col in categorical:
     mappings[col]=ORDINAL[col]
     if candidate=='ordinal_reference':work[col]=work[col].map(ORDINAL[col])
    else:work[col]=pd.to_numeric(work[col],errors='coerce')
   work=work.replace([np.inf,-np.inf],np.nan).dropna()
   if candidate=='categorical_reference':work=pd.get_dummies(work,columns=categorical,drop_first=True,dtype=float)
   y=work[outcome].astype(float);x=work.drop(columns=outcome).astype(float);x.insert(0,'const',1.0)
   if len(work)<=x.shape[1]:
    refs.append(dict(candidate=candidate,status='insufficient_rows',n=len(work)));continue
   fit=ols_reference(y.to_numpy(),x.to_numpy(),list(x.columns))
   ids=frame.loc[work.index,'response_id'].tolist() if 'response_id' in frame else work.index.tolist()
   refs.append(dict(candidate=candidate,status='computed',encoding_assumptions=mappings,response_ids=ids,**fit))
  out['models'][label]=dict(outcome=outcome,predictors=predictors,references=refs)
 out['limitations']=['References use delivered finite rows, listwise per model, without extra imputation or filtering.','Ordinal and dummy-coded references are conditional alternatives, not required encoding choices. Compare only a reference matching the declared method.','Different documented transformations or sample policies require semantic reconciliation; a mismatch is not itself a failed gate.']
 return out

RECONCILIATION_RUBRIC=dict(rubric='Full-row statistical and cleaning reconciliation',weight=1,criterion=[
'Use the host full-row SQLite serialization and submitted correction flags/memo to review every record listed in source_anomalies and every change listed in source_changes. Invented response IDs and changed respondent links need source evidence; demographic joins must not multiply responses. Documented valid exclusions need not follow a fixed canonical cleaning policy.',
'All country and overall descriptive mean, SD, median and n and Pearson coefficients must be reproducible from delivered cleaned rows and declared encodings/missingness. Compare host references only when their sample and encoding assumptions match; reconcile other documented valid policies without forcing a reference policy.',
'Both OLS models must contain every requested predictor and report reproducible intercept, coefficients, standard errors, p-values, R-squared and n. Check transformations, sample membership and covariance conventions against matching host references. Ordinal and dummy-coded candidates are conditional, not required encodings; other justified methods need an auditable derivation from the delivered database.',
'Host row serializations and statistical references are evaluator-derived evidence only. Their presence cannot satisfy missing solver workbook tables or count as model-produced work.'])

def ols_reference(y,x,names):
 beta,_,rank,_=np.linalg.lstsq(x,y,rcond=None);n=len(y);df=n-rank
 residual=y-x@beta;pinv=np.linalg.pinv(x);bread=pinv@pinv.T;rss=float(residual@residual)
 tss=float((y-y.mean())@(y-y.mean()));hat=np.sum((x@bread)*x,axis=1)
 covariances={'nonrobust':bread*rss/df,'HC1':bread@(x.T@(x*(residual**2)[:,None]))@bread*n/df,'HC3':bread@(x.T@(x*(residual/np.maximum(1-hat,1e-12))[:,None]**2))@bread}
 inference={}
 for name,cov in covariances.items():
  se=np.sqrt(np.maximum(np.diag(cov),0));test=np.divide(beta,se,out=np.full_like(beta,np.nan),where=se>0)
  inference[name]=dict(standard_errors=dict(zip(names,map(finite,se))),p_values_t=dict(zip(names,map(finite,2*stats.t.sf(abs(test),df)))),p_values_normal=dict(zip(names,map(finite,2*stats.norm.sf(abs(test))))))
 return dict(n=n,rank=int(rank),residual_df=int(df),coefficients=dict(zip(names,map(finite,beta))),r_squared=finite(1-rss/tss) if tss>0 else None,inference=inference,method='OLS least squares with intercept; explicit covariance and t/normal alternatives')
RECONCILIATION_RUBRIC['criterion'] += [
'Crosswalk coverage must include every measured raw survey field (the nine Likert variables, cc_cause and media_consumption) and explain the treatment of demographic covariates used in analysis. Use the public codebook and ESS construct names exactly; explicitly mark absence of a suitable cross-study equivalent instead of inventing one.',
'Check all submitted country benchmark points against the host Meta/Yale study-country source rows, codebook and ESS Table 1. Reproduce local percentages with the declared cutpoints and denominators; compare units consistently. Every difference must be our percentage minus the benchmark, and every absolute difference strictly over 15 percentage points must appear in Divergence_Flags with a specific explanation.']
