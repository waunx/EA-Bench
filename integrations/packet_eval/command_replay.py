"""Count executed commands by offline, isolated replay; never query a model."""
import argparse
import ast
from bisect import bisect_right
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT/'evaluation')]
from ea_bench.client import parse_json
from integrations.packet_audit.common import folder, read, sha, write
from integrations.packet_audit.aggregate import attach
from integrations.packet_eval.sandbox import BWRAP
VERSION = 'executed_commands_v2'
MARKER = re.compile(r'^\++EA_CMD\t(\d+\.\d+)\t(\d+)\t', re.M)


def command_name(command):
    lexer = shlex.shlex(command, posix=True)
    lexer.whitespace_split = True
    name = lexer.get_token()
    if not name or name in {'for','select','while','until','if','then','fi','do','done','[[','(('}:
        return None
    if re.match(r'^[A-Za-z_][A-Za-z_0-9]*(?:\[.*\])?=', name):
        return None
    if name in {'exec','builtin'}:
        name = lexer.get_token()
        if not name or name.startswith('-'): raise ValueError('Unsupported command wrapper')
    return os.path.basename(name)


def parse_xtrace(text):
    matches = list(MARKER.finditer(text))
    rows = []
    for i, match in enumerate(matches):
        command = text[match.end():matches[i+1].start() if i+1<len(matches) else len(text)].rstrip()
        rows.append(dict(time=float(match[1]), pid=int(match[2]), command=command,
                         name=command_name(command)))
    return rows


def parse_processes(text):
    pending, parents, executions, attempts = {}, {}, [], {}
    for line in text.splitlines():
        match = re.match(r'^(\d+)\s+(\d+\.\d+)\s+(.*)$', line)
        if not match: raise ValueError('Unrecognized process trace')
        pid, stamp, call = int(match[1]), float(match[2]), match[3]
        if '<unfinished ...>' in call:
            pending[pid] = (stamp, call.replace('<unfinished ...>', ''))
            continue
        if call.startswith('<... '):
            if pid not in pending: raise ValueError('Missing syscall start')
            stamp, start = pending.pop(pid)
            call = start + call.split('resumed>', 1)[1]
        if call.startswith(('clone(', 'clone3(', 'fork(', 'vfork(')):
            child = re.search(r'= (\d+)\s*$', call)
            if child and int(child[1])>0: parents[int(child[1])] = pid
        if call.startswith('execve('):
            args = re.match(r'execve\(("(?:\\.|[^"\\])*"), \[("(?:\\.|[^"\\])*")', call)
            if not args: raise ValueError('Unsupported execve trace')
            event = dict(pid=pid, time=stamp, path=json.loads(args[1]),
                         name=os.path.basename(json.loads(args[2])), succeeded=bool(re.search(r'= 0\s*$',call)))
            previous = attempts.get(pid)
            if previous and previous['name'] != event['name']:
                executions.append(attempts.pop(pid))
            elif previous:
                event['time'] = previous['time']
            if event['succeeded']:
                attempts.pop(pid, None)
                if executions and event['name'] in {'sh','dash','bash'}:
                    argv = re.match(r'execve\("(?:\\.|[^"\\])*", (\[.*\]), ',call)
                    values = ast.literal_eval(argv[1]) if argv else []
                    if '-c' in values: event['shell_body'] = values[values.index('-c')+1]
                executions.append(event)
            else:
                attempts[pid] = event
        if call.startswith(('exit(', 'exit_group(')) and pid in attempts:
            executions.append(attempts.pop(pid))
    if not executions or executions[0]['path'] != '/bin/bash':
        raise ValueError('Missing traced shell startup')
    executions.extend(attempts.values())
    return parents, executions[1:]


def count_commands(shell_text, process_text):
    shell = parse_xtrace(shell_text)
    parents, executions = parse_processes(process_text)
    indexed = defaultdict(list)
    for i, row in enumerate(shell): indexed[row['pid']].append((row['time'], i))
    matched, extra = set(), []
    for event in executions:
        pid, seen, match = event['pid'], set(), None
        while pid not in seen:
            seen.add(pid)
            entries = indexed.get(pid, [])
            pos = bisect_right(entries, (event['time'], float('inf'))) - 1
            if pos >= 0:
                index = entries[pos][1]
                if shell[index]['name'] == event['name'] and index not in matched:
                    match = index
                    break
            if pid not in parents: break
            pid = parents[pid]
        if match is None: extra.append(event)
        else: matched.add(match)
    commands = [r for r in shell if r['name'] is not None]
    for event in executions:
        body = event.get('shell_body')
        if body is None: continue
        if re.search(r'[;&|()\n]', body):
            raise ValueError('Uninstrumented compound child shell requires review')
        name = command_name(body)
        descendants = []
        for candidate in executions:
            if candidate is event: continue
            pid, seen = candidate['pid'], set()
            while pid not in seen:
                seen.add(pid)
                if pid == event['pid']:
                    descendants.append(candidate)
                    break
                if pid not in parents: break
                pid = parents[pid]
        if name and not any(c['name']==name for c in descendants):
            extra.append(dict(pid=event['pid'],time=event['time'],name=name,
                              command=body,source='simple_child_shell_without_exec'))
    return dict(command_count=len(commands)+len(extra), shell_commands=commands,
                subprocess_commands=extra, control_records=len(shell)-len(commands))


def execute_traced(packet, workspace, command, output, timeout=120):
    packet, workspace, output = map(lambda p:Path(p).resolve(), (packet,workspace,output))
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace/'inputs').mkdir(exist_ok=True)
    (workspace/'prompt.md').touch(exist_ok=True)
    output.mkdir(parents=True, exist_ok=False)
    (output/'env.sh').write_text("exec 9>> /__ea_trace/commands.log\nBASH_XTRACEFD=9\nPS4='+EA_CMD\t${EPOCHREALTIME}\t${BASHPID}\t'\nset -x\n")
    argv = [BWRAP,'--unshare-all','--die-with-parent','--new-session',
            '--ro-bind','/usr','/usr','--symlink','usr/bin','/bin',
            '--symlink','usr/lib','/lib','--symlink','usr/lib64','/lib64',
            '--dev','/dev','--tmpfs','/tmp','--bind',str(workspace),'/workspace',
            '--ro-bind',str(packet/'inputs'),'/workspace/inputs',
            '--ro-bind',str(packet/'prompt.md'),'/workspace/prompt.md',
            '--bind',str(output),'/__ea_trace','--chdir','/workspace','--clearenv']
    env = dict(PATH='/usr/local/bin:/usr/bin:/bin',HOME='/tmp',LANG='C.UTF-8',
               OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLCONFIGDIR='/tmp/mpl',
               BASH_ENV='/__ea_trace/env.sh')
    for key, value in env.items(): argv += ['--setenv',key,value]
    argv += ['/usr/bin/strace','-f','-qq','-ttt','-s','65535','-e','trace=process',
             '-o','/__ea_trace/process.log','/bin/bash','--noprofile','--norc','-c',command]
    with (workspace/'.shell_stdout').open('w+b') as out, (workspace/'.shell_stderr').open('w+b') as err:
        process = subprocess.Popen(argv,stdout=out,stderr=err,start_new_session=True)
        try: code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL)
            process.wait()
            code = 124
        out.seek(0); stdout = out.read(24001).decode(errors='replace')
        err.seek(0); stderr = err.read(8001).decode(errors='replace')
    reply = dict(exit_code=code,stdout=stdout[:24000],stderr=stderr[:8000],
                 truncated=len(stdout)>24000 or len(stderr)>8000)
    write(output/'reply.json', reply)
    shell_text = (output/'commands.log').read_text() if (output/'commands.log').exists() else ''
    process_text = (output/'process.log').read_text() if (output/'process.log').exists() else ''
    counts = count_commands(shell_text, process_text)
    write(output/'counts.json', counts)
    return reply, counts


def shell_rounds(path):
    result, pending = [], None
    for line in path.read_text().splitlines():
        turn = json.loads(line)
        if turn['role'] == 'assistant':
            try: action = parse_json(turn['content'])
            except (ValueError,TypeError): action = {}
            pending = action.get('command') if isinstance(action,dict) and action.get('tool')=='shell' else None
        elif turn['role']=='tool' and pending is not None:
            if 'exit_code' in turn['content']:
                result.append((pending, turn['content']))
            pending = None
    return result


def replay_one(run, item, model, destination):
    source = folder(run, model, item['id'])
    metrics = read(source/'metrics.json')
    rounds = shell_rounds(source/'dialogue.jsonl')
    assert len(rounds)==metrics['shell_calls'], item['id']
    destination.mkdir(parents=True, exist_ok=False)
    rows = []
    for index, (command, expected) in enumerate(rounds, 1):
        reply, counts = execute_traced(run/'packets'/item['case']/item['variant'],
            destination/'workspace', command, destination/f'command-{index:02d}')
        rows.append(dict(index=index,command_count=counts['command_count'],
                         expected_exit_code=expected['exit_code'],exit_code=reply['exit_code'],
                         exit_match=reply['exit_code']==expected['exit_code'],
                         stdout_match=reply['stdout']==expected['stdout'],
                         stderr_match=reply['stderr']==expected['stderr'],
                         truncated=reply['truncated']))
    complete = all(r['exit_match'] and r['stdout_match'] for r in rows)
    result = dict(model=model,id=item['id'],version=VERSION,
        status='counted' if complete else 'needs_review',
        metrics_sha256=sha(source/'metrics.json'), trace_sha256=sha(source/'dialogue.jsonl'),
        shell_wrappers=len(rounds), commands=sum(r['command_count'] for r in rows),
        user_rounds=metrics['user_rounds'], submit_calls=int(metrics['status']=='submitted'),
        command_tool_calls=sum(r['command_count'] for r in rows)+metrics['user_rounds']+int(metrics['status']=='submitted'),
        rounds=rows)
    write(destination/'result.json', result)
    return result


def self_test():
    import tempfile
    with tempfile.TemporaryDirectory(prefix='ea-command-selftest-') as tmp:
        root = Path(tmp)
        packet = root/'packet'
        (packet/'inputs').mkdir(parents=True)
        (packet/'prompt.md').write_text('Test packet')
        for name in ['a','b','c']: (packet/'inputs'/name).write_text(name+'\n')
        examples = [
            ('cat inputs/a inputs/b', 1),
            ('cat inputs/a; cat inputs/b', 2),
            ('cat inputs/a | head -1', 2),
            ('for f in inputs/*; do echo "$f"; cat "$f"; done', 6),
            ('false && echo skipped', 1),
            ('true || echo skipped', 1),
            ('x=$(echo ok); echo "$x"', 2),
            ("python3 - <<'PY'\nprint('a;b|c')\nPY", 1),
            ("python3 -c 'import subprocess; subprocess.run([\"echo\", \"ok\"])'", 2),
            ("find inputs -type f -exec cat {} \\;", 4),
            ('does_not_exist; echo recovered', 2),
            ("python3 -c 'import subprocess; subprocess.run([\"ea_missing_child\"])'", 2),
            ("python3 -c 'import os; os.system(\"ea_missing_child\")'", 3),
        ]
        for i, (command, expected) in enumerate(examples):
            _, result = execute_traced(packet, root/'workspace', command, root/f'case-{i}', 15)
            assert result['command_count']==expected, (command,result)
        print('Passed', len(examples), 'isolated command-count checks', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--run', type=Path, default=ROOT/'evaluation/runs/packet-eval-20260930-low8-mc')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    if args.self_test: return self_test()
    if not args.output: parser.error('--output is required')
    if not 1<=args.workers<=8: parser.error('workers must be 1..8')
    run, output = args.run.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    plan = read(run/'plan.json')
    jobs = []
    for item in plan['items']:
        for model in plan['config']['models']:
            source = folder(run, model, item['id'])
            row = dict(read(source/'metrics.json',{}), model=model)
            attach(run, item, source, row)
            if row.get('audit_status')=='complete' and row.get('grounded_success'):
                jobs.append((item, model))
    if args.limit: jobs = jobs[:args.limit]
    checked = set()
    for item, _ in jobs:
        if item['id'] in checked: continue
        checked.add(item['id'])
        packet = run/'packets'/item['case']/item['variant']
        for name, digest in item['files'].items():
            assert sha(packet/name)==digest, (item['id'], name)
    write(output/'selection.json', dict(run=str(run),version=VERSION,
        implementation_sha256=sha(Path(__file__)), model_calls=0,
        items=[dict(id=item['id'],model=model) for item,model in jobs]))
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(replay_one,run,item,model,output/model/item['id']):(item,model)
                   for item,model in jobs}
        for future in as_completed(futures):
            item, model = futures[future]
            try: result = future.result()
            except Exception as exc:
                result = dict(id=item['id'],model=model,status='error',error=type(exc).__name__+': '+str(exc))
                write(output/model/item['id']/'result.json',result)
            results.append(result)
            write(output/'summary.json',dict(version=VERSION,planned=len(jobs),completed=len(results),model_calls=0,rows=results))
            if len(results)%10==0 or result['status']=='error':
                print(len(results),'/',len(jobs),result['model'],result['id'],result['status'],flush=True)
    print('Finished',len(results),'offline records; model calls 0',flush=True)


if __name__=='__main__': main()
