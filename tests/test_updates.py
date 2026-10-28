import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys,json,tempfile,unittest,ast
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QObject,Signal,QByteArray,QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtNetwork import QNetworkReply
from versioning import Version
from updates import find_update,UpdateChecker,UpdateInfo
from app_meta import VERSION,NAME,PUBLISHER_KO,PUBLISHER_EN,publisher_for_language
from scripts.build_metadata import build

app=QApplication.instance() or QApplication([])
app.setProperty('offlineTests',True)


def release(number,**kwargs):
    return dict(tag_name='v'+number,assets=[dict(name=f'PDFeather-{number}-Setup.exe',state='uploaded')],**kwargs)

class FakeReply(QObject):
    finished=Signal(); downloadProgress=Signal(int,int)
    def __init__(self,content,status=200,error=QNetworkReply.NetworkError.NoError):
        super().__init__(); self.content=content; self.status=status; self.failure=error
    def attribute(self,*_): return self.status
    def error(self): return self.failure
    def readAll(self): return QByteArray(self.content)
    def abort(self): self.failure=QNetworkReply.NetworkError.OperationCanceledError; self.finished.emit()

class FakeManager:
    def __init__(self,reply): self.reply=reply; self.requests=[]
    def get(self,request): self.requests.append(request); return self.reply

class UpdateTests(unittest.TestCase):
    def test_semver_precedence_and_validation(self):
        order=['1.0.0-alpha','1.0.0-alpha.1','1.0.0-alpha.beta','1.0.0-beta','1.0.0-beta.2','1.0.0-beta.11','1.0.0-rc.1','1.0.0','1.0.1','1.9.0','1.10.0','2.0.0']
        self.assertEqual(sorted(map(Version.parse,reversed(order))),list(map(Version.parse,order)))
        self.assertEqual(Version.parse('1.0.0+build.1'),Version.parse('v1.0.0+build.2'))
        for text in ('1.2','01.2.3','1.2.3-01','1.2.3-','1.2.3+','1.2.3.4','1.2.3 evil','1.2.٣'):
            with self.assertRaises(ValueError): Version.parse(text)

    def test_stable_release_selection_and_asset_requirements(self):
        data=[release('1.9.0'),release('1.10.0'),release('2.0.0-beta.1'),release('2.0.0',draft=True),release('3.0.0',prerelease=True),dict(tag_name='v4.0.0',assets=[])]
        self.assertEqual(find_update(data,'1.8.0'),UpdateInfo('1.10.0','https://github.com/minnnn0307/PDFeather/releases/tag/v1.10.0'))
        self.assertIsNone(find_update(data,'1.10.0'))
        self.assertIsNone(find_update([release('1.0.0')],'1.10.0'))
        with self.assertRaises(ValueError): find_update({'message':'API limit'})

    def test_async_result_error_timeout_and_cancel_without_network(self):
        checker=UpdateChecker(); reply=FakeReply(json.dumps([release('9.0.0')]).encode()); checker.manager=FakeManager(reply)
        results=[]; errors=[]; checker.completed.connect(results.append); checker.failed.connect(errors.append)
        self.assertTrue(checker.check()); self.assertTrue(checker.busy); self.assertFalse(checker.check()); self.assertFalse(results)
        QTimer.singleShot(0,reply.finished.emit); app.processEvents()
        self.assertFalse(checker.busy); self.assertEqual(results[0].version,'9.0.0'); self.assertFalse(errors)
        request=checker.manager.requests[0]
        self.assertTrue(request.url().toString().startswith('https://api.github.com/repos/minnnn0307/PDFeather/releases'))
        self.assertEqual(bytes(request.rawHeader('User-Agent')),f'PDFeather/{VERSION}'.encode())
        checker.manager=FakeManager(FakeReply(b'bad json')); checker.check(); checker.manager.reply.finished.emit(); self.assertTrue(errors)
        count=len(errors); checker.manager=FakeManager(FakeReply(b'')); checker.check(); checker.timeout(); self.assertFalse(checker.busy); self.assertEqual(len(errors),count+1)
        count=len(errors); checker.manager=FakeManager(FakeReply(b'')); checker.check(); checker.cancel(); self.assertFalse(checker.busy); self.assertEqual(len(errors),count)
        checker.deleteLater()

    def test_daily_check_preferences_and_dismissal(self):
        from main import Window
        from preferences import Preferences
        from PySide6.QtCore import QSettings
        with tempfile.TemporaryDirectory() as temp:
            prefs=Preferences(QSettings(str(Path(temp)/'settings.ini'),QSettings.Format.IniFormat))
            window=Window(prefs,enable_updates=False)
            try:
                window.enable_update_checks=True
                reply=FakeReply(json.dumps([release('9.0.0')]).encode()); manager=FakeManager(reply); window.update_checker.manager=manager
                window.check_updates(False); self.assertEqual(len(manager.requests),1); reply.finished.emit()
                self.assertTrue(window.update_popup.isVisible()); self.assertTrue(window.update_bar.isHidden())
                window.dismiss_update(); self.assertTrue(window.update_bar.isHidden())
                window.check_updates(False); self.assertEqual(len(manager.requests),1)
                reply=FakeReply(json.dumps([release('9.0.0')]).encode()); window.update_checker.manager=FakeManager(reply)
                prefs.set('auto_update',False); window.check_updates(False); self.assertFalse(window.update_checker.manager.requests)
                window.check_updates(True); reply.finished.emit(); self.assertTrue(window.update_popup.isVisible())
            finally: window.close()

    def test_identity_metadata_in_both_languages(self):
        self.assertEqual(publisher_for_language('ko-KR'),PUBLISHER_KO); self.assertEqual(publisher_for_language('en-US'),PUBLISHER_EN)
        with tempfile.TemporaryDirectory() as temp:
            build(temp); source=(Path(temp)/'installer/version_info.txt').read_text('ascii'); tree=ast.parse(source)
            tables={node.args[0].value:node.args[1] for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='StringTable'}
            for language,publisher in [('040904B0',PUBLISHER_EN),('041204B0',PUBLISHER_KO)]:
                values={item.args[0].value:item.args[1].value for item in tables[language].elts}
                self.assertEqual(values['CompanyName'],publisher); self.assertEqual(values['ProductName'],NAME); self.assertEqual(values['FileDescription'],NAME); self.assertEqual(values['ProductVersion'],VERSION)

if __name__=='__main__': unittest.main()
