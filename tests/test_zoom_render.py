import os,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings,QTimer
from main import Window
from preferences import Preferences
from scripts.smoke_fixture import create_pdf
app=QApplication.instance() or QApplication([]);app.setProperty('offlineTests',True)
class ZoomRenderTests(unittest.TestCase):
 def test_rapid_zoom_skips_sync_render_and_delivers_latest_background_tile(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'p.pdf';create_pdf(path,3);w=Window(Preferences(QSettings(str(Path(folder)/'p.ini'),QSettings.Format.IniFormat)));w.show();w.open(str(path))
   for _ in range(10):app.processEvents()
   received=[];w.canvas.zoom_renderer.ready.connect(lambda key,image:received.append((key,image)))
   ticks=[];heartbeat=QTimer();heartbeat.setInterval(5);heartbeat.timeout.connect(lambda:ticks.append(time.monotonic()));heartbeat.start()
   try:
    with patch.object(w.doc,'tile',side_effect=AssertionError('Synchronous PDF rendering during zoom')):
     for zoom in (1.1,1.2,1.4,1.6):
      w.set_zoom(zoom,interactive=True);app.processEvents()
     self.assertTrue(w.canvas.zoom_idle.isActive());self.assertTrue(w.canvas.zoom_preview)
     deadline=time.monotonic()+15
     while not received and time.monotonic()<deadline:app.processEvents();time.sleep(.003)
     self.assertTrue(received,'No background tile delivered');self.assertGreater(len(ticks),3)
     self.assertEqual(w.zoom,1.6);self.assertEqual(received[0][0][2],round(w.doc.sizes[received[0][0][1]][0]*1.6*w.canvas.devicePixelRatioF()))
     self.assertFalse(received[0][1].isNull())
    process=w.canvas.zoom_renderer.process;w.close_all();self.assertIsNone(w.canvas.zoom_renderer.process)
   finally:heartbeat.stop();w.close_all()
