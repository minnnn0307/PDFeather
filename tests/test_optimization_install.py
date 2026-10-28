import os,sys,tempfile,unittest,hashlib
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt,QSettings,QPoint,QPointF,QEvent,Signal,QObject,QByteArray
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtNetwork import QNetworkReply
from main import Window
from preferences import Preferences
from scripts.smoke_fixture import create_pdf
from update_install import InstallerDownload,validate_asset
from updates import UpdateInfo
app=QApplication.instance() or QApplication([]);app.setProperty('offlineTests',True)
def settle():
 for _ in range(8):app.processEvents()
class Reply(QObject):
 readyRead=Signal();finished=Signal()
 def __init__(self,data):super().__init__();self.data=data
 def readAll(self):data=self.data;self.data=b'';return QByteArray(data)
 def attribute(self,*_):return 200
 def error(self):return QNetworkReply.NetworkError.NoError
 def abort(self):self.finished.emit()
class Manager:
 def __init__(self,reply):self.reply=reply
 def get(self,*_):return self.reply
class OptimizationInstallTests(unittest.TestCase):
 def test_size_hash_url_and_cancel(self):
  data=b'MZtest-installer';digest=hashlib.sha256(data).hexdigest()
  info=UpdateInfo('9.0.0','', 'https://github.com/minnnn0307/PDFeather/releases/download/v9.0.0/PDFeather-9.0.0-Setup.exe',digest,len(data))
  self.assertEqual(validate_asset(info),info.download_url)
  with self.assertRaises(ValueError):validate_asset(UpdateInfo('9.0.0','','https://evil.example/file',digest,len(data)))
  for bad,cancel in [(False,False),(True,False),(False,True)]:
   downloader=InstallerDownload();reply=Reply(data);downloader.manager=Manager(reply);results=[];errors=[]
   downloader.completed.connect(results.append);downloader.failed.connect(errors.append)
   selected=UpdateInfo(info.version,'',info.download_url,'0'*64 if bad else digest,len(data));downloader.start(selected)
   if cancel:downloader.cancel()
   else:reply.finished.emit()
   if bad or cancel:self.assertFalse(results);self.assertTrue(errors);self.assertFalse(downloader.path.exists())
   else:self.assertEqual(Path(results[0]).read_bytes(),data);self.assertIsNone(downloader.reply);downloader.cleanup()
 def test_explicit_popup_click_before_install(self):
  from PySide6.QtWidgets import QPushButton
  data=b'MZtest';info=UpdateInfo('9.0.0','https://github.com/minnnn0307/PDFeather/releases/tag/v9.0.0','https://github.com/minnnn0307/PDFeather/releases/download/v9.0.0/PDFeather-9.0.0-Setup.exe',hashlib.sha256(data).hexdigest(),len(data))
  with tempfile.TemporaryDirectory() as folder:
   w=Window(Preferences(QSettings(str(Path(folder)/'p.ini'),QSettings.Format.IniFormat)));w.show();settle()
   try:
    with patch('main.launch_installer') as launch:
     w.on_update_checked(info);settle();self.assertTrue(w.update_popup.isVisible());launch.assert_not_called()
     reply=Reply(data);w.installer_download.manager=Manager(reply)
     button=next(b for b in w.update_popup.findChildren(QPushButton) if b.text()=='업데이트 설치')
     button.click();launch.assert_not_called();reply.finished.emit();self.assertEqual(launch.call_count,1)
     w.installer_download.cleanup()
   finally:w.close()

 def test_optimization_and_side_snap(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'p.pdf';create_pdf(path,5);w=Window(Preferences(QSettings(str(Path(folder)/'p.ini'),QSettings.Format.IniFormat)));w.show();w.open(str(path));settle()
   try:
    w.settings_panel.controls['optimization'].setChecked(True);settle();self.assertEqual(w.doc.cache_limit,8*1024*1024);self.assertEqual(w.doc.pixel_limit,2_000_000)
    for i in range(5):w.doc.image(i,2)
    self.assertLessEqual(w.doc.cache_bytes,w.doc.cache_limit)
    w.settings_panel.controls['optimization'].setChecked(False);self.assertEqual(w.doc.cache_limit,64*1024*1024)
    bounds=w.screen().availableGeometry()
    for left in (True,False):
     end=QPoint(bounds.left() if left else bounds.right(),bounds.center().y());bar=w.titlebar
     bar.drag_origin=end-QPoint(20,20);bar.dragging=True
     event=QMouseEvent(QEvent.Type.MouseButtonRelease,QPointF(10,10),QPointF(end),Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier)
     bar.mouseReleaseEvent(event);settle();self.assertEqual(w.geometry().x(),bounds.left() if left else bounds.left()+bounds.width()//2)
     # Qt's minimum width remains authoritative on unusually narrow screens.
     self.assertEqual(w.width(),max(w.minimumWidth(),bounds.width()//2))
   finally:w.close()
