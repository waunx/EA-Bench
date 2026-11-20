"""JB08 complete coordinated response, dashboard, PDF and catalog checks."""
import json,csv,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
from dataclasses import asdict
from collections import Counter
from decimal import Decimal, InvalidOperation
from .author_english_jb08 import RELEASE
from .jb08_evidence import visible_expected,rows
from .jobbench import OfficialJudge,load_task
from .native import artifact_hashes,JobBenchAcceptance
SHEETS=['Profit Margin Analysis','Traffic-to-Sales Funnel','Underperformer Crosswalk']
def structural_checks(artifacts):
 import openpyxl
 import fitz
 root=Path(artifacts);hashes=artifact_hashes(root);books=list(root.glob('*.xlsx'));docs=list(root.glob('*.docx'));pdfs=list(root.glob('*.pdf'));p=root/'optimized_product_listings.csv'
 checks=dict(workbook=len(books)==1,word_package=len(docs)==1,pdf_audit=len(pdfs)==1,optimized_csv=p.is_file());details={}
 if len(books)==1:
  try:
   b=openpyxl.load_workbook(books[0],data_only=False);checks['three_named_sheets']=b.sheetnames and set(b.sheetnames)==set(SHEETS) and len(b.sheetnames)==3
   checks['nonempty_sheets']=all(sum(c.value is not None for row in s for c in row)>1 for s in b)
   checks['no_excel_errors']=not any(c.data_type=='e' or '#REF!' in str(c.value) for s in b for row in s for c in row)
  except Exception as e:checks['readable_workbook']=False;details['xlsx_error']=str(e)
 if len(docs)==1:
  try:
   with zipfile.ZipFile(docs[0]) as z:t=' '.join(ET.fromstring(z.read('word/document.xml')).itertext())
   checks['readable_word']=bool(t.strip())
  except Exception:checks['readable_word']=False
 if len(pdfs)==1:
  try:
   reader=fitz.open(pdfs[0]);checks['two_or_three_pages']=2<=len(reader)<=3;details['pdf_pages']=len(reader);checks['pdf_has_visible_content']=all(bool(page.get_text().strip() or page.get_images() or page.get_drawings()) for page in reader);details['pdf_text_characters']=sum(len(page.get_text()) for page in reader)
  except Exception as e:checks['readable_pdf']=False;details['pdf_error']=str(e)
 if p.is_file():
  try:
   source=rows(RELEASE/'variants/full/inputs/current_product_listings.csv');output=rows(p)
   checks['preserved_columns']=bool(output) and set(source[0])|{'Listing Change Justification'}<=set(output[0])
   identity=['Handle','Variant SKU','Option1 Value','Option2 Value','Option3 Value','Image Position']
   def row_identity(r):
    values=[r.get(k) for k in identity]
    try:
     if values[-1]:values[-1]=Decimal(values[-1])
    except InvalidOperation:pass
    return tuple(values)
   checks['preserved_catalog_rows']=Counter(row_identity(r) for r in output)==Counter(row_identity(r) for r in source)
   details['csv_rows']=len(output)
  except Exception as e:checks['readable_csv']=False;details['csv_error']=str(e)
 return dict(status='pass' if all(checks.values()) else 'fail',checks=checks,details=details,artifact_hashes=hashes)
CRITERIA=[
'Provide all four deliverables as requested: Word complaint package, three-sheet Excel dashboard, 2-3-page readable PDF audit and optimized_product_listings.csv preserving the catalog rows/variants. Cross-reference findings consistently across them rather than providing unrelated reports.',
'Respond professionally to all six open tickets with distinct customer-facing replies and internal Triage Notes: Margaret wrong item/exchange, David delayed shipment, Sarah defective bag/photos already stated attached, James missing promotion with correct cent rounding, Priya nonmatching lamp, Robert wholesale terms. Cite applicable named policy sections, propose permitted options and shipping/refund responsibilities, concrete next steps and realistic timelines; do not claim to have executed refunds, checked tracking or stock without evidence. Recognize the general 10% gesture differs from the quality-specific percentage. Apply the confirmed quality-photo rule; do not mechanically demand Sarah resend photos already reported attached.',
'Each Triage Note checks the complained item against actual catalog entries, identifies matches/absences, compares existing claims to complaint evidence, attempts a defensible sales/category lookup, and recommends correction/removal/escalation with justification. Sales IDs and furniture/office/technology product data do not identify margins for apparel/home-decor items merely by rough category. Explicit data gaps and escalation are valid; fabricated margin mappings are not. Do not fabricate missing complaint products as current catalog rows.',
'Profit Margin Analysis covers all 17 subcategories: total sales, total profit, weighted margin=sum(profit)/sum(sales), mean discount and clearly defined order count. Distinct-order counts or explicitly labeled transaction counts are acceptable. Use confirmed target profit consistently; no arithmetic rounding or percent-scale errors. Include interpretation of losses and promotion effects without unjustified causality.',
'Traffic-to-Sales Funnel includes each observed month by visitor type, session counts/denominators, average product-page engagement, bounce rate, page values and Revenue=true conversion. Use all 12,330 sessions, correct Boolean parsing, and do not manufacture missing months. Explain meaningful conversion drop-offs without treating observational association as causal.',
'Underperformer Crosswalk ranks 10 worst products by aggregated product profit margin rather than lowest raw total profit or arbitrary transactions. Show revenue/profit/margin, identifiers and actual listing match status; absent matches must be explicit. Product ID aggregation and defensible documented equivalent aggregation are acceptable, including exact ties at the cutoff. Trace recommendations to the business without inventing a join to unrelated listed apparel.',
'PDF computes department and class rating/recommendation metrics from all 23,486 reviews, explaining missing categories/denominators. Rank eligible classes with at least 30 reviews by rating ascending, recommendation ascending, review count descending, class name ascending: Trend, Dresses, Blouses. Use actual review text to support recurrent themes and distinguish class-level evidence from specific SKU proof. Compare overlapping catalog types, quote actual listing language and review evidence, and give prioritized catalog recommendations linked to customer pain points. Do not overstate the sample excerpts supplied to the judge as exhaustive frequency evidence.',
'CSV preserves source columns and all 43 rows, including continuation/image/variant identity. Rewrite substantive product Body (HTML) descriptions with truthful SEO-relevant language, moderate unsupported softness/quality/feature claims, and provide useful fit/care guidance without inventing measurements, composition percentages or capabilities. Complete SEO and Google Shopping fields wherever facts or justified editorial assignments permit. For an unknown factual identifier such as manufacturer MPN, explicitly flag verification needed and do not invent a manufacturer identifier; do not claim the resulting draft is feed-ready if required factual fields remain unresolved. Preserve prices, inventory and variant options unless a documented source justifies changing them.',
'Listing Change Justification explains each modification with traceable ticket IDs, review class/theme evidence or sales findings. Do not attribute unrelated external apparel reviews to a specific catalog SKU or add an absent lamp as if present. Customer remedies, internal recommendations, PDF priorities and edited copy must agree. Scope out cancelled unfulfilled sales, generic goodwill excerpts and other merchants policies; altered source scope would require reassessment.',
'Only facts actually supplied to the agent through files or recorded clarification count as confirmed. Private world values are what-if grading context, not agent evidence. Accept honest provisional scenarios in appropriate analysis criteria, but do not reward unsupported guesses at hidden facts. Source-grounded alternative remedies or classifications are acceptable when justified and policy-consistent.'
]
def check(artifacts,private_root,variant='full',world=None,clarification_records=None,**config):
 root=Path(private_root);root.mkdir(parents=True,exist_ok=True);structure=structural_checks(artifacts)
 if structure['status']!='pass':return dict(case='JB08',status='fail',structural=structure,original=dict(status='not_run'),completion=dict(status='not_run'))
 source,_,original=load_task('JB08');ev=visible_expected(variant,clarification_records)
 unconfirmed=set(ev['clarification_audit']['unconfirmed_keys'])
 (root/'source_evidence.json').write_text(json.dumps(ev,indent=2,default=str)+'\n')
 completion=[dict(rubric=f'JB08 requirement {i+1}',weight=1,criterion=[criterion,CRITERIA[-1], 'Evaluate source-supported conditional outcomes on their merits; an unresolved fact alone is not failure. Evidence and independent calculations: '+json.dumps(ev,default=str)]) for i,criterion in enumerate(CRITERIA)]
 combined=original+completion;rp=root/'rubrics.json';rp.write_text(json.dumps(dict(rubrics=combined),indent=2)+'\n')
 judge=OfficialJudge(rp,root/'judge',**config);JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,combined,judge)({},{})
 raw=json.loads((judge.last_run/'details.json').read_text());score=lambda rubrics,data:asdict(JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,rubrics,judge)._score(data,structure['artifact_hashes']))
 native=score(original,raw['rubrics'][:len(original)]);active=score(completion,[dict(r,index=r['index']-len(original)) for r in raw['rubrics'][len(original):]])
 return dict(case='JB08',variant=variant,status='pass' if active['status']=='passed' else 'fail',structural=structure,original=native,completion=active,clarification_complete=not unconfirmed,unconfirmed_fields=sorted(unconfirmed),judge_run=str(judge.last_run),scope='Original rubric score and branch-aware full-task artifact score are separate. No native environment replay.')
