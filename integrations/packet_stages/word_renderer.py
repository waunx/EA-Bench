"""Render actual DOCX in a network-free private LibreOffice namespace."""
from pathlib import Path
import hashlib,json,os,subprocess,tempfile,sys
BWRAP=Path('bwrap')
LO=Path('/')
def render(docx,output,timeout=120):
    docx=Path(docx).resolve();output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    if not docx.is_file() or docx.suffix.lower()!='.docx':raise ValueError('A DOCX file is required')
    with tempfile.TemporaryDirectory(prefix='ea-word-identity-') as temp:
        identity=Path(temp)/'passwd';identity.write_text(f'sandbox:x:{os.getuid()}:{os.getgid()}:Renderer:/tmp:/bin/sh\n')
        args=[str(BWRAP),'--unshare-all','--die-with-parent','--new-session','--ro-bind','/usr','/usr','--symlink','usr/bin','/bin','--symlink','usr/lib','/lib','--symlink','usr/lib64','/lib64','--dev','/dev','--tmpfs','/tmp','--dir','/etc','--ro-bind',str(identity),'/etc/passwd','--ro-bind','/etc/fonts','/etc/fonts','--ro-bind',str(docx),'/input/document.docx','--bind',str(output),'/output','--chdir','/output','--clearenv']
        env=dict(PATH='/usr/bin:/bin',LANG='C.UTF-8',LD_LIBRARY_PATH='/usr/lib/libreoffice/program:/usr/lib/x86_64-linux-gnu',URE_BOOTSTRAP='vnd.sun.star.pathname:/usr/lib/libreoffice/program/fundamentalrc',SAL_USE_VCLPLUGIN='svp',FONTCONFIG_PATH='/etc/fonts',XDG_CACHE_HOME='/tmp/cache',XDG_CONFIG_HOME='/tmp/config')
        for k,v in env.items():args+=['--setenv',k,v]
        version=subprocess.run(args+['/usr/lib/libreoffice/program/soffice.bin','--version'],capture_output=True,text=True,timeout=20)
        args+=['/bin/sh','-c','for attempt in 1 2 3; do /usr/lib/libreoffice/program/soffice.bin "$@"; code=$?; [ "$code" = 81 ] || exit "$code"; done; exit 81','writer','-env:UserInstallation=file:///tmp/lo-profile','--headless','--nologo','--nodefault','--norestore','--convert-to','pdf:writer_pdf_Export','--outdir','/output','/input/document.docx']
        result=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
    (output/'render.log').write_text(result.stdout+'\n'+result.stderr)
    pdf=output/'document.pdf'
    if result.returncode or not pdf.is_file():raise RuntimeError('Word rendering failed (exit '+str(result.returncode)+'): '+result.stderr[-1000:])
    extract_env=dict(os.environ)
    script='import json,sys,pymupdf; d=pymupdf.open(sys.argv[1]); print(json.dumps(dict(pages=len(d),text="\\n".join(p.get_text() for p in d),version=pymupdf.VersionBind))); d.close()'
    extraction=subprocess.run([sys.executable,'-c',script,str(pdf)],capture_output=True,text=True,env=extract_env,timeout=30)
    if extraction.returncode:raise RuntimeError('PDF extraction failed: '+extraction.stderr[-1000:])
    extracted=json.loads(extraction.stdout);pages=extracted['pages'];text=extracted['text']
    renderer=version.stdout.strip() if version.returncode==0 and version.stdout.strip() else 'LibreOffice version probe unavailable'
    report=dict(status='evaluated',pages=pages,source_sha256=hashlib.sha256(docx.read_bytes()).hexdigest(),rendered_sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),renderer=renderer+', headless svp',renderer_binary_sha256=hashlib.sha256((LO/'usr/lib/libreoffice/program/soffice.bin').read_bytes()).hexdigest(),version_probe_exit_code=version.returncode,pdf_extractor='PyMuPDF '+extracted['version'],text=text)
    (output/'render.json').write_text(json.dumps(report,indent=2)+'\n');return report
