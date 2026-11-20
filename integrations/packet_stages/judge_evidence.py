"""Count completed original-rubric feedback from saved official-judge evidence."""
import json
from pathlib import Path
from .jobbench import load_task

def collect(case,private):
    _,_,original=load_task(case);completed=[];original_runs=[]
    for path in sorted(Path(private).rglob('details.json')):
        folder=path.parent;extraction=folder/'extraction.json'
        if not extraction.exists():continue
        data=json.loads(path.read_text());rows=data.get('rubrics',[])
        if json.loads(extraction.read_text()).get('status')!='complete' or data.get('error') or not rows:continue
        valid=True
        for row in rows:
            log=folder/'debug'/('original_rubric_'+str(row['index'])+'.log')
            if not log.exists() or 'API Exit Code: 0' not in log.read_text().split('\n\n',1)[0].splitlines():valid=False;break
        if not valid:continue
        completed.append(str(folder))
        matches=len(rows)>=len(original)
        for spec,row in zip(original,rows):
            expected=spec['criterion'];expected=[expected] if isinstance(expected,str) else expected
            observed=[r.get('criterion') for r in row.get('result',{}).get('criteria_results',[])]
            if spec['rubric']!=row.get('rubric') or spec['weight']!=row.get('weight') or expected!=observed:matches=False
        if matches:original_runs.append(str(folder))
    return dict(original_rubric_judge_runs=len(original_runs),completed_judge_runs=len(completed),
        original_rubric_evidence=original_runs,all_judge_evidence=completed,native_environment_replays=0,
        scope='Verified extraction and API execution; original criterion text must match. This is rubric feedback, not native environment replay.')
