import os,sys,tempfile,unittest
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings,QRectF,Qt,QPoint,QPointF,QEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from main import Window
from preferences import Preferences
from scripts.smoke_fixture import create_pdf
app=QApplication.instance() or QApplication([]);app.setProperty('offlineTests',True)
def settle():
 for _ in range(12):app.processEvents()
class ResumeRegionReopenTests(unittest.TestCase):
 def make(self,folder):
  w=Window(Preferences(QSettings(str(Path(folder)/'p.ini'),QSettings.Format.IniFormat)),enable_updates=False);w.show()
  path=Path(folder)/'test.pdf';create_pdf(path,3);w.open(str(path));settle();w.display_recovery.timer.stop();return w
 def test_reopen_restores_session_even_without_reading_history(self):
  with tempfile.TemporaryDirectory() as folder:
   w=self.make(folder);w.prefs.set('remember_document',False)
   try:
    w.mode.setCurrentIndex(1);w.set_zoom(2.17);w.go(1);settle();w.scroll.verticalScrollBar().setValue(w.scroll.verticalScrollBar().value()+37)
    expected=(w.zoom,w.scroll.verticalScrollBar().value(),w.current)
    old=w.doc;w.close_tab(0);self.assertIsNone(w.doc);self.assertTrue(w.file_tabs.can_reopen)
    w.reopen_closed_tab();settle();self.assertIsNot(w.doc,old);self.assertEqual(w.file_tabs.count(),1)
    self.assertEqual((w.zoom,w.scroll.verticalScrollBar().value(),w.current),expected);self.assertFalse(w.file_tabs.can_reopen)
   finally:w.close_all()
 def test_region_drag_zoom_and_right_click_restore(self):
  with tempfile.TemporaryDirectory() as folder:
   w=self.make(folder)
   try:
    w.set_zoom(1.);settle();w.set_selection_tool('zoom_region');before=(w.zoom,w.fit_mode,w.scroll.horizontalScrollBar().value(),w.scroll.verticalScrollBar().value())
    rect=w.canvas.rects[0][1];center=rect.center();a=center-QPointF(80,60);b=center+QPointF(80,60)
    for kind,point,buttons in [(QEvent.Type.MouseButtonPress,a,Qt.MouseButton.LeftButton),(QEvent.Type.MouseMove,b,Qt.MouseButton.LeftButton),(QEvent.Type.MouseButtonRelease,b,Qt.MouseButton.NoButton)]:
     event=QMouseEvent(kind,point,QPointF(w.canvas.mapToGlobal(point.toPoint())),Qt.MouseButton.NoButton if kind==QEvent.Type.MouseMove else Qt.MouseButton.LeftButton,buttons,Qt.KeyboardModifier.NoModifier);app.sendEvent(w.canvas,event)
    settle();self.assertGreater(w.zoom,before[0]);self.assertIsNone(w.canvas.capture_rect)
    # Selected PDF point is at the viewport centre after zoom.
    newrect=w.canvas.rects[0][1];target=QPointF(newrect.x()+rect.width()/2*w.zoom,newrect.y()+rect.height()/2*w.zoom)
    actual=w.canvas.mapFrom(w.scroll.viewport(),w.scroll.viewport().rect().center());self.assertLess(abs(actual.x()-target.x()),3);self.assertLess(abs(actual.y()-target.y()),3)
    from PySide6.QtGui import QContextMenuEvent
    event=QContextMenuEvent(QContextMenuEvent.Reason.Mouse,QPoint(100,100),w.canvas.mapToGlobal(QPoint(100,100)));app.sendEvent(w.canvas,event)
    self.assertEqual((w.zoom,w.fit_mode,w.scroll.horizontalScrollBar().value(),w.scroll.verticalScrollBar().value()),before)
   finally:w.close_all()
 def test_resume_rebuilds_geometry_and_caches_without_resetting_zoom(self):
  with tempfile.TemporaryDirectory() as folder:
   w=self.make(folder)
   try:
    w.set_zoom(2.17);w.go(1);settle();before=(w.zoom,w.current,w.scroll.verticalScrollBar().value())
    # Mimic stale pre-resume widget geometry and a pending native wake event.
    w.display_recovery.native_message(0x218,4)
    w.canvas.resize(20,20);w.doc.cache['obsolete']='sentinel';w.doc.cache_bytes=999
    w.display_recovery.native_message(0x218,18);self.assertTrue(w.display_recovery.timer.isActive());w.display_recovery.timer.stop();w.display_recovery.refresh()
    self.assertNotIn('obsolete',w.doc.cache);self.assertGreater(w.canvas.width(),20);self.assertEqual((w.zoom,w.current,w.scroll.verticalScrollBar().value()),before)
    self.assertEqual(w.frame_outline.size(),w.size());self.assertEqual(w.thumbs.count(),3)
   finally:w.close_all()
