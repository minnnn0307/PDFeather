import os,sys,tempfile,unittest
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings,QPoint
from PySide6.QtWidgets import QApplication
from main import Window
from preferences import Preferences
app=QApplication.instance() or QApplication([]);app.setProperty('offlineTests',True)
def settle():
    for _ in range(6):app.processEvents()
class WindowFrameTests(unittest.TestCase):
    def test_rounding_resize_cache_and_maximize(self):
        with tempfile.TemporaryDirectory() as folder:
            w=Window(Preferences(QSettings(str(Path(folder)/'p.ini'),QSettings.Format.IniFormat)));w.show();settle()
            try:
                w.canvas.grab();key=w.canvas.welcome_image.cacheKey()
                for width,height in [(700,460),(710,467),(720,474),(1100,700)]:
                    w.resize(width,height);settle();w.canvas.grab()
                    self.assertEqual(w.canvas.welcome_image.cacheKey(),key)
                    self.assertEqual(w.canvas.size(),w.scroll.viewport().size())
                    self.assertFalse(w.mask().isEmpty());self.assertFalse(w.mask().contains(QPoint(0,0)))
                    self.assertTrue(w.mask().contains(QPoint(w.width()//2,1)))
                    self.assertEqual(w.frame_outline.geometry(),w.rect())
                w.showMaximized();settle();self.assertTrue(w.mask().isEmpty())
                w.showNormal();settle();self.assertFalse(w.mask().isEmpty())
                w.apply_theme('light');settle();w.canvas.grab();self.assertNotEqual(w.canvas.welcome_image.cacheKey(),key)
            finally:w.close()
