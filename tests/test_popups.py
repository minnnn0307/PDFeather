import os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt,QPoint,QSize,QSettings
from PySide6.QtWidgets import QApplication,QSizeGrip
from main import Window,PrintWindow
from popups import resize_edges
from preferences import Preferences
from scripts.smoke_fixture import create_pdf
app=QApplication.instance() or QApplication([])
app.setProperty('offlineTests',True)
def settle():
    for _ in range(8): app.processEvents()
class Messages:
    def __init__(self,*messages): self.items=list(messages)
    def poll(self): return bool(self.items)
    def recv(self): return self.items.pop(0)
    def close(self): pass
class PopupTests(unittest.TestCase):
    def test_four_corners_and_small_window(self):
        for point,edges in [(QPoint(1,1),Qt.Edge.LeftEdge|Qt.Edge.TopEdge),(QPoint(538,1),Qt.Edge.RightEdge|Qt.Edge.TopEdge),(QPoint(1,358),Qt.Edge.LeftEdge|Qt.Edge.BottomEdge),(QPoint(538,358),Qt.Edge.RightEdge|Qt.Edge.BottomEdge)]:
            self.assertEqual(resize_edges(point,QSize(540,360)),edges)
        self.assertEqual(resize_edges(QPoint(200,200),QSize(540,360)),Qt.Edge(0))
        with tempfile.TemporaryDirectory() as folder:
            w=Window(Preferences(QSettings(str(Path(folder)/'settings.ini'),QSettings.Format.IniFormat)));w.show();w.resize(540,360);settle()
            try:
                self.assertEqual(w.size(),QSize(540,360));self.assertFalse(w.findChildren(QSizeGrip))
                from PySide6.QtCore import QEvent
                from PySide6.QtGui import QMouseEvent
                from unittest.mock import Mock
                handle=Mock();handle.startSystemResize.return_value=True
                with patch.object(w,'windowHandle',return_value=handle):
                    for point in [QPoint(1,1),QPoint(538,1),QPoint(1,358),QPoint(538,358)]:
                        event=QMouseEvent(QEvent.Type.MouseButtonPress,point,w.mapToGlobal(point),Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
                        QApplication.sendEvent(w,event)
                    self.assertEqual(handle.startSystemResize.call_count,4)
                w.show_settings();settle();sheet=w.settings_dialog
                self.assertTrue(sheet.scrim.isVisible());self.assertTrue(sheet.isModal())
                self.assertLess((sheet.geometry().center()-w.mapToGlobal(w.rect().center())).manhattanLength(),4)
                self.assertLessEqual(sheet.width(),w.width());sheet.close();settle();self.assertFalse(sheet.scrim.isVisible())
            finally:w.close_all()
    def test_print_progress_error_cancel_and_completion(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'one.pdf';create_pdf(source,2)
            w=Window(Preferences(QSettings(str(Path(folder)/'settings.ini'),QSettings.Format.IniFormat)));w.show();w.open(str(source));settle()
            with patch.object(PrintWindow,'start_job',lambda self,kind,settings:setattr(self,'kind',kind)):
                p=PrintWindow(w.doc,w);p.poll_timer.stop();p.show();settle();p.devices.addItem('Test printer');p.devices.setCurrentIndex(0)
                try:
                    p.submit();settle();self.assertEqual(p.kind,'print',p.error.text());self.assertFalse(p.setup_content.isVisible());self.assertTrue(p.progress_content.isVisible());self.assertLess(p.width(),600)
                    p.reject();self.assertTrue(p.isVisible())
                    p.connection=Messages(('progress',1,2));p.poll();self.assertEqual(p.progress_bar.value(),1)
                    p.connection=Messages(('error','Test failure'));p.poll();settle();self.assertTrue(p.setup_content.isVisible());self.assertIn('Test failure',p.error.text())
                    p.submit();p.cancel_job();settle();self.assertTrue(p.setup_content.isVisible())
                    p.submit();p.connection=Messages(('done',));p.poll();settle();self.assertFalse(p.isVisible());self.assertFalse(p.scrim.isVisible());self.assertIsNone(p.process)
                finally:p.done(0);w.close_all()
