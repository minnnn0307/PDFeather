import os,sys,tempfile,unittest
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt,QSettings,QPoint,QPointF,QEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from main import Window
from preferences import Preferences
from scripts.smoke_fixture import create_pdf
app=QApplication.instance() or QApplication([]);app.setProperty('offlineTests',True)
def settle():
 for _ in range(10):app.processEvents()
class CloseAndSnapTests(unittest.TestCase):
 def make(self,folder):
  w=Window(Preferences(QSettings(str(Path(folder)/'p.ini'),QSettings.Format.IniFormat)));w.show()
  for index in range(2):
   path=Path(folder)/f'{index}.pdf';create_pdf(path,1);w.open(str(path))
  settle();return w
 def test_close_prompt_cancel_current_and_remember_all(self):
  with tempfile.TemporaryDirectory() as folder:
   w=self.make(folder)
   try:
    w.close();settle();self.assertTrue(w.isVisible());self.assertTrue(w.close_popup.isVisible());self.assertEqual(w.file_tabs.count(),2)
    w.close_popup.close_button.click();settle();self.assertTrue(w.isVisible());self.assertEqual(w.file_tabs.count(),2)
    w.close();settle();w.close_current_button.click();settle();self.assertTrue(w.isVisible());self.assertEqual(w.file_tabs.count(),1)
    w.open(str(Path(folder)/'1.pdf' if w.file_tabs.tabText(0)=='0.pdf' else Path(folder)/'0.pdf'));settle();self.assertEqual(w.file_tabs.count(),2)
    w.close();settle();w.close_always_check.setChecked(True);w.close_all_button.click();settle();self.assertFalse(w.isVisible());self.assertTrue(w.prefs.get('close_all_tabs'))
   finally:w.close_all()
   next_window=self.make(folder)
   try:
    next_window.close();settle();self.assertFalse(next_window.isVisible());self.assertIsNone(getattr(next_window,'close_popup',None))
   finally:next_window.close_all()
 def test_side_snap_restores_original_size_on_drag(self):
  with tempfile.TemporaryDirectory() as folder:
   w=self.make(folder);w.resize(760,570);settle();original=w.size();bar=w.titlebar;bounds=w.screen().availableGeometry()
   def send(kind,point,buttons):
    event=QMouseEvent(kind,QPointF(bar.mapFromGlobal(point)),QPointF(point),Qt.MouseButton.NoButton if kind==QEvent.Type.MouseMove else Qt.MouseButton.LeftButton,buttons,Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(bar,event);settle()
   try:
    for left in (True,False):
     start=bar.mapToGlobal(QPoint(100,20));edge=QPoint(bounds.left() if left else bounds.right(),bounds.center().y())
     send(QEvent.Type.MouseButtonPress,start,Qt.MouseButton.LeftButton);send(QEvent.Type.MouseMove,edge,Qt.MouseButton.LeftButton);send(QEvent.Type.MouseButtonRelease,edge,Qt.MouseButton.NoButton)
     self.assertIsNotNone(bar.snap_restore)
     start=bar.mapToGlobal(QPoint(100,20));end=QPoint(bounds.center().x(),bounds.top()+140)
     send(QEvent.Type.MouseButtonPress,start,Qt.MouseButton.LeftButton);send(QEvent.Type.MouseMove,end,Qt.MouseButton.LeftButton);send(QEvent.Type.MouseButtonRelease,end,Qt.MouseButton.NoButton)
     self.assertEqual(w.size(),original);self.assertIsNone(bar.snap_restore);self.assertLess(abs(w.mapFromGlobal(end).y()-20),2)
   finally:w.close_all()
