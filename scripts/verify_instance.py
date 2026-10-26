"""Exercise two real processes; the second must forward Unicode paths and exit."""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.smoke_fixture import create_pdf


def verify(command):
    with tempfile.TemporaryDirectory() as temp:
        folder=Path(temp); first=folder/'첫 문서.pdf'; second=folder/'second document.pdf'; status=folder/'status.json'
        create_pdf(first,2); create_pdf(second,3)
        env=dict(os.environ,QT_QPA_PLATFORM='offscreen')
        prefix=command+['--instance-test',str(status)]
        primary=subprocess.Popen(prefix+[str(first)],env=env)
        try:
            def read_until(count,timeout=25):
                deadline=time.monotonic()+timeout
                while time.monotonic()<deadline:
                    if primary.poll() is not None: raise RuntimeError('Primary instance exited: '+(status.read_text('utf-8') if status.exists() else 'no status'))
                    try:
                        data=json.loads(status.read_text('utf-8'))
                        if data['tabs']==count and data['pid']==primary.pid: return data
                    except (FileNotFoundError,json.JSONDecodeError,PermissionError): pass
                    time.sleep(.08)
                raise RuntimeError(f'Instance did not reach {count} tabs')
            read_until(1)
            forwarded=subprocess.run(prefix+[str(second)],env=env,timeout=15)
            if forwarded.returncode!=0: raise RuntimeError('Secondary instance failed')
            data=read_until(2)
            if {Path(p).name for p in data['paths']}!={first.name,second.name}: raise RuntimeError('Forwarded paths do not match')
            duplicate=subprocess.run(prefix+[str(first)],env=env,timeout=15)
            if duplicate.returncode!=0: raise RuntimeError('Duplicate forwarding failed')
            if read_until(2)['pid']!=primary.pid: raise RuntimeError('A second GUI replaced the first')
        finally:
            primary.terminate()
            try: primary.wait(timeout=5)
            except subprocess.TimeoutExpired: primary.kill(); primary.wait(timeout=5)
        # A killed owner must not leave a permanently blocked lock or socket.
        restarted=subprocess.Popen(prefix+[str(first)],env=env)
        try:
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                try:
                    data=json.loads(status.read_text('utf-8'))
                    if data['pid']==restarted.pid and data['tabs']==1: break
                except (FileNotFoundError,json.JSONDecodeError,PermissionError): pass
                time.sleep(.08)
            else: raise RuntimeError('Stale instance recovery failed')
        finally:
            restarted.terminate()
            try: restarted.wait(timeout=5)
            except subprocess.TimeoutExpired: restarted.kill(); restarted.wait(timeout=5)
    print('Single-instance forwarding, duplicate suppression, Unicode paths and crash recovery verified')

if __name__=='__main__': verify(sys.argv[1:])
