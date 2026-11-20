"""Artifact execution sees one packet, fetched public references and dependencies."""
from pathlib import Path
import os,signal,subprocess,tempfile,shutil
BWRAP=Path(shutil.which('bwrap') or 'bwrap')
DEPENDENCIES=Path(os.environ.get('EA_BENCH_ANALYSIS_DEPS','/usr/local/lib/python3.11/site-packages'))
NOTEBOOK_COMPAT=Path('/tmp/ea-bench-notebook-compat')

def _execute(packet,workspace,command,*,identity_file,references=None,timeout=180):
    packet,workspace=Path(packet).resolve(),Path(workspace).resolve()
    if workspace==packet or workspace.is_relative_to(packet):raise ValueError('Workspace must be separate from immutable packet')
    for name in ['prompt.md','inputs']:
        if not (packet/name).exists():raise ValueError('Incomplete packet')
    workspace.mkdir(parents=True,exist_ok=True)
    for name in ['inputs','references','output']:(workspace/name).mkdir(exist_ok=True)
    (workspace/'prompt.md').touch(exist_ok=True)
    argv=[str(BWRAP),'--unshare-all','--die-with-parent','--new-session','--ro-bind','/usr','/usr',
        '--symlink','usr/bin','/bin','--symlink','usr/lib','/lib','--symlink','usr/lib64','/lib64',
        '--dev','/dev','--tmpfs','/tmp','--dir','/opt','--dir','/etc',
        '--ro-bind',str(identity_file),'/etc/passwd',
        '--bind',str(workspace),'/workspace','--ro-bind',str(packet/'inputs'),'/workspace/inputs',
        '--ro-bind',str(packet/'prompt.md'),'/workspace/prompt.md',
        '--ro-bind',str(DEPENDENCIES),'/opt/analysis-deps','--chdir','/workspace','--clearenv']
    if NOTEBOOK_COMPAT.is_dir():argv+=['--ro-bind',str(NOTEBOOK_COMPAT),'/opt/notebook-compat']
    if references is not None:argv+=['--ro-bind',str(Path(references).resolve()),'/workspace/references']
    env=dict(PATH='/usr/local/bin:/usr/bin:/bin',LANG='C.UTF-8',PYTHONPATH='/opt/notebook-compat:/opt/analysis-deps',
        OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLCONFIGDIR='/tmp/mpl',
        JUPYTER_RUNTIME_DIR='/tmp/jupyter-runtime',JUPYTER_CONFIG_DIR='/tmp/jupyter-config',IPYTHONDIR='/tmp/ipython',
        JUPYTER_DATA_DIR='/tmp/jupyter-data',JUPYTER_PATH='/opt/analysis-deps/share/jupyter')
    for key,value in env.items():argv+=['--setenv',key,value]
    argv+=['/bin/bash','--noprofile','--norc','-c',command]
    with (workspace/'.stdout').open('w+b') as out,(workspace/'.stderr').open('w+b') as err:
        process=subprocess.Popen(argv,stdout=out,stderr=err,start_new_session=True)
        try:code=process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL);process.wait();code=124
        out.seek(0);err.seek(0);stdout=out.read(32001).decode(errors='replace');stderr=err.read(16001).decode(errors='replace')
    return dict(exit_code=code,stdout=stdout[:32000],stderr=stderr[:16000],truncated=len(stdout)>32000 or len(stderr)>16000)

def execute(packet,workspace,command,*,references=None,timeout=180):
    # A synthetic account record supplies a sandbox home without mounting host users.
    with tempfile.TemporaryDirectory(prefix='ea-bench-identity-',dir='/tmp') as folder:
        identity_file=Path(folder)/'passwd'
        identity_file.write_text(f'sandbox:x:{os.getuid()}:{os.getgid()}:Isolated runtime:/tmp:/bin/sh\n')
        return _execute(packet,workspace,command,identity_file=identity_file,references=references,timeout=timeout)
