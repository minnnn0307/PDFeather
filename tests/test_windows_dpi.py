import os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from main import Window
from preferences import Preferences
app=QApplication.instance() or QApplication([]);app.setProperty('offlineTests',True)
class WindowsDpiTests(unittest.TestCase):
 def test_late_monitor_dpi_is_requeried_even_after_initial_matching_scale(self):
  with tempfile.TemporaryDirectory() as folder:
   w=Window(Preferences(QSettings(str(Path(folder)/'p.ini'),QSettings.Format.IniFormat)),enable_updates=False)
   recovery=w.display_recovery;scale=[1.]
   try:
    with patch('display_recovery.native_monitor_scale',side_effect=[1.,2.,2.,2.,2.,2.]),patch.object(w,'devicePixelRatioF',side_effect=lambda:scale[0]),patch('display_recovery.refresh_monitor_data') as refresh:
     recovery.native_message(0x218,18);self.assertTrue(recovery.dpi_timer.isActive())
     recovery.dpi_timer.stop();recovery.reconcile_dpi();self.assertEqual(recovery.dpi_observation,(1.,1.,1.));self.assertTrue(recovery.dpi_timer.isActive())
     def rescan(owner):scale[0]=2.;return True
     refresh.side_effect=rescan
     for _ in range(5):recovery.dpi_timer.stop();recovery.reconcile_dpi()
     self.assertEqual(recovery.dpi_observation,(2.,2.,2.));self.assertEqual(refresh.call_count,6);self.assertFalse(recovery.dpi_timer.isActive());self.assertEqual(w.zoom,1.)
   finally:w.close_all()
 def test_monitor_change_starts_reconciliation_and_close_cancels_it(self):
  with tempfile.TemporaryDirectory() as folder:
   w=Window(Preferences(QSettings(str(Path(folder)/'p.ini'),QSettings.Format.IniFormat)),enable_updates=False);r=w.display_recovery
   self.assertFalse(r.dpi_timer.isActive());r.begin_dpi_recovery();self.assertTrue(r.dpi_timer.isActive());w.close_all();self.assertFalse(r.dpi_timer.isActive())
