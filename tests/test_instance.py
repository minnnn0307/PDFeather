import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys,unittest,json,tempfile,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from instance import encode_paths,validate_paths
from scripts.verify_instance import verify

class InstanceTests(unittest.TestCase):
    def test_packet_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            path=str(Path(temp)/'한글 문서.PDF')
            self.assertEqual(json.loads(encode_paths([path]))['paths'],[str(Path(path).resolve())])
        for paths in [['relative.pdf'],['https://host/file.pdf'],['/tmp/not.exe'],['/tmp/no.pdf\0'],{},[None]]:
            with self.assertRaises(ValueError): validate_paths(paths)

    def test_departing_owner_is_retried_after_write_failure(self):
        from unittest.mock import Mock,patch
        from PySide6.QtCore import QCoreApplication
        from instance import SingleInstance
        app=QCoreApplication.instance() or QCoreApplication([])
        with tempfile.TemporaryDirectory() as folder:
            instance=SingleInstance(name='unit-exit-race',directory=folder)
            instance.lock=Mock();instance.lock.tryLock.side_effect=[False,True]
            instance.server=Mock();instance.server.listen.return_value=True
            socket=Mock();socket.waitForConnected.return_value=True;socket.write.return_value=-1;socket.bytesToWrite.return_value=0
            with patch('instance.QLocalSocket',return_value=socket),patch('instance.QLocalServer.removeServer'):
                self.assertTrue(instance.start_or_forward([]))
            self.assertTrue(instance.owner);self.assertEqual(instance.lock.tryLock.call_count,2);instance.close()

    def test_real_process_forwarding_and_crash_recovery(self):
        if os.name!='nt':
            from PySide6.QtNetwork import QLocalServer
            from PySide6.QtCore import QCoreApplication
            app=QCoreApplication.instance() or QCoreApplication([])
            probe=QLocalServer(); name='pdfeather-probe-'+uuid.uuid4().hex
            if not probe.listen(name): self.skipTest('Local socket creation is unavailable in this sandbox: '+probe.errorString())
            probe.close(); QLocalServer.removeServer(name)
        verify([sys.executable,str(Path(__file__).resolve().parents[1]/'main.py')])

if __name__=='__main__': unittest.main()
