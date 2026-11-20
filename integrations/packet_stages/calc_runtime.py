"""Host launcher for a recorded LibreOffice/UNO runtime; no vendor edits."""
import hashlib,json,os,signal,subprocess,tempfile
from pathlib import Path
from .english_packet import ROOT
RUNTIME=Path('/tmp/ea-pinned-calc/root')
VALIDATION=Path('/tmp/ea-pinned-calc/validation.json')
WORKER=ROOT/'vendor/jobbench/eval/jobbench_eval/calc_worker.py'
ENTRY=Path(__file__).with_name('calc_worker_entry.py')
ENGINE='libreoffice-24.2.7.2-ubuntu24.04.6-reconstructed-20261012'

def calculate(path,cells,timeout=90,*,require_validation=True):
    if require_validation:
        if not VALIDATION.exists() or json.loads(VALIDATION.read_text()).get('status')!='passed':
            raise RuntimeError('Reconstructed calculation runtime is not validated')
    with tempfile.TemporaryDirectory(prefix='ea-calc-input-') as temp:
        source=Path(temp)/'input.xlsx';source.write_bytes(Path(path).read_bytes())
        identity=Path(temp)/'passwd'
        identity.write_text(f'sandbox:x:{os.getuid()}:{os.getgid()}:Calc:/tmp:/bin/sh\n')
        launcher=Path(temp)/'soffice'
        launcher.write_bytes(Path(__file__).with_name('calc_soffice_launcher.py').read_bytes())
        launcher.chmod(0o755)
        args=['bwrap','--unshare-all','--die-with-parent','--new-session',
            '--ro-bind',str(RUNTIME),'/', '--tmpfs','/tmp','--dev','/dev','--dir','/proc',
            '--ro-bind',str(WORKER),'/calc_worker.py','--ro-bind',str(ENTRY),'/worker_entry.py',
            '--ro-bind',str(source),'/input.xlsx','--ro-bind',str(identity),'/etc/passwd',
            '--ro-bind',str(launcher),'/usr/lib/libreoffice/program/soffice',
            '--clearenv','--setenv','PATH','/usr/bin:/bin',
            '--setenv','LANG','C.UTF-8','--chdir','/tmp','/usr/bin/python3','/worker_entry.py','/input.xlsx']
        process=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            text=True,start_new_session=True,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
        try:stdout,stderr=process.communicate(json.dumps({'cells':cells}),timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL);process.communicate()
            raise RuntimeError('Excel calculation exceeded its time limit')
        if process.returncode:raise RuntimeError('Excel calculation failed: '+(stdout+'\n'+stderr)[-1800:])
        result=json.loads(stdout)
        if result.get('engine')!=ENGINE or result.get('status')!='recalculated':raise RuntimeError('Invalid calculation result')
        for sheet,addresses in cells.items():
            for address in addresses:
                value=result['cells'][sheet][address]
                if not isinstance(value,dict) or not {'value','display','error_code'}<=value.keys():raise RuntimeError('Missing cell evidence')
        result['runtime_scope']='Pinned LibreOffice/UNO package version; supporting packages reconstructed from official archive, not identical to the original dated snapshot.'
        return result
