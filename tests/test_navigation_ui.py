import os,sys,tempfile,unittest
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt,QSettings,QPoint,QPointF,QEvent
from PySide6.QtGui import QMouseEvent,QWheelEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from main import Window
from preferences import Preferences
from scripts.smoke_fixture import create_pdf
app=QApplication.instance() or QApplication([]);app.setProperty('offlineTests',True)
def settle():
    for _ in range(12):app.processEvents()
class NavigationUITests(unittest.TestCase):
    def window(self,folder):
        w=Window(Preferences(QSettings(str(Path(folder)/'p.ini'),QSettings.Format.IniFormat)));w.show();settle();return w
    def test_resize_cursors_and_empty_center(self):
        with tempfile.TemporaryDirectory() as folder:
            w=self.window(folder)
            try:
                for size in [(650,420),(1400,900)]:
                    w.resize(*size);settle();self.assertEqual(w.canvas.size(),w.scroll.viewport().size())
                    self.assertEqual(w.scroll.verticalScrollBar().maximum(),0)
                for point,shape in [(QPoint(2,2),Qt.CursorShape.SizeFDiagCursor),(QPoint(w.width()-2,2),Qt.CursorShape.SizeBDiagCursor),(QPoint(2,w.height()-2),Qt.CursorShape.SizeBDiagCursor),(QPoint(w.width()-2,w.height()-2),Qt.CursorShape.SizeFDiagCursor)]:
                    event=QMouseEvent(QEvent.Type.MouseMove,QPointF(point),QPointF(w.mapToGlobal(point)),Qt.MouseButton.NoButton,Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier)
                    QApplication.sendEvent(w,event);self.assertIsNotNone(app.overrideCursor());self.assertEqual(app.overrideCursor().shape(),shape)
                point=QPoint(100,100);QApplication.sendEvent(w,QMouseEvent(QEvent.Type.MouseMove,QPointF(point),QPointF(w.mapToGlobal(point)),Qt.MouseButton.NoButton,Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier));self.assertIsNone(app.overrideCursor())
            finally:w.close_all()
    def test_scroll_setting_and_thumbnail_prefetch(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'pages.pdf';create_pdf(path,40);w=self.window(folder)
            try:
                w.open(str(path));settle();w.mode.setCurrentIndex(1);w.set_zoom(1);settle()
                w.settings_panel.controls['scroll_step'].setValue(240)
                self.assertEqual(Preferences(w.prefs.storage).get('scroll_step'),240)
                for area in (w.scroll,w.thumbs):
                    area.verticalScrollBar().setValue(0);target=area.viewport();event=QWheelEvent(QPointF(60,80),QPointF(target.mapToGlobal(QPoint(60,80))),QPoint(),QPoint(0,-120),Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
                    QApplication.sendEvent(target,event);self.assertEqual(area.verticalScrollBar().value(),240)
                w.thumbs.verticalScrollBar().setValue(0)
                for _ in range(60):w.render_thumbs()
                self.assertFalse(w.thumbs.item(8).icon().isNull(),'Nearby thumbnail should be ready before scrolling')
                self.assertLessEqual(len(w.thumb_lru),160)
                w.thumbs.verticalScrollBar().setValue(3000)
                for _ in range(60):w.render_thumbs()
                self.assertFalse(w.thumbs.item(0).icon().isNull(),'Recently viewed thumbnails should remain cached')
            finally:w.close_all()
