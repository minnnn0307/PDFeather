"""Drop a real IPC connection while the previous owner exits; successor must take over."""
import hashlib,json,os,sys,tempfile,time,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QCoreApplication,QTimer
from instance import SingleInstance
from scripts.smoke_fixture import create_pdf

def verify(command):
    app=QCoreApplication.instance() or QCoreApplication([])
    with tempfile.TemporaryDirectory() as folder:
        folder=Path(folder);status=folder/'status.json';pdf=folder/'document.pdf';create_pdf(pdf,1)
        key='PDFeather-test-'+hashlib.sha256(str(status.resolve()).encode()).hexdigest()[:20]
        owner=SingleInstance(name=key,directory=folder/'ipc');assert owner.start_or_forward([])
        owner.server.newConnection.disconnect(owner.accept);dropped=[]
        def drop():
            while owner.server.hasPendingConnections():
                socket=owner.server.nextPendingConnection();socket.abort();socket.deleteLater();dropped.append(True)
            QTimer.singleShot(150,owner.close)
        owner.server.newConnection.connect(drop)
        child=subprocess.Popen(command+['--instance-test',str(status),str(pdf)],env={**os.environ,'QT_QPA_PLATFORM':'offscreen','PYINSTALLER_RESET_ENVIRONMENT':'1'})
        try:
            deadline=time.monotonic()+25
            while time.monotonic()<deadline:
                app.processEvents();time.sleep(.01)
                if status.exists():
                    try:data=json.loads(status.read_text('utf-8'))
                    except (ValueError,PermissionError):continue
                    if 'error' in data:raise RuntimeError(data['error'])
                    if data.get('pid')==child.pid and data.get('tabs')==1:
                        assert dropped;print('Shutdown IPC race recovered; successor opened PDF as primary');return
                if child.poll() is not None:raise RuntimeError('Successor exited during shutdown race')
            raise RuntimeError('Timed out recovering from shutdown race')
        finally:
            owner.close();child.terminate()
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
if __name__=='__main__':verify(sys.argv[1:])
