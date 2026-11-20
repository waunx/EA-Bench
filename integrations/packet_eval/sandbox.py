"""Only one packet and writable outputs are visible to shell."""
from pathlib import Path
import subprocess,os,signal
BWRAP='bwrap'
def execute(packet,workspace,command,timeout=120):
    packet=Path(packet).resolve();workspace=Path(workspace).resolve();workspace.mkdir(parents=True,exist_ok=True)
    (workspace/'inputs').mkdir(exist_ok=True);(workspace/'prompt.md').touch(exist_ok=True)
    argv=[BWRAP,'--unshare-all','--die-with-parent','--new-session','--ro-bind','/usr','/usr','--symlink','usr/bin','/bin','--symlink','usr/lib','/lib','--symlink','usr/lib64','/lib64','--dev','/dev','--tmpfs','/tmp','--bind',str(workspace),'/workspace','--ro-bind',str(packet/'inputs'),'/workspace/inputs','--ro-bind',str(packet/'prompt.md'),'/workspace/prompt.md','--chdir','/workspace','--clearenv']
    for key,value in dict(PATH='/usr/local/bin:/usr/bin:/bin',HOME='/tmp',LANG='C.UTF-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLCONFIGDIR='/tmp/mpl').items():argv+=['--setenv',key,value]
    argv+=['/bin/bash','--noprofile','--norc','-c',command]
    with (workspace/'.shell_stdout').open('w+b') as out,(workspace/'.shell_stderr').open('w+b') as err:
        process=subprocess.Popen(argv,stdout=out,stderr=err,start_new_session=True)
        try:code=process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL);process.wait();code=124
        out.seek(0);stdout=out.read(24001).decode(errors='replace')
        err.seek(0);stderr=err.read(8001).decode(errors='replace')
    return dict(exit_code=code,stdout=stdout[:24000],stderr=stderr[:8000],truncated=len(stdout)>24000 or len(stderr)>8000)
