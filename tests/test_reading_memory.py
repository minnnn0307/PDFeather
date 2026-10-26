import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys,tempfile,unittest,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from main import Window
from preferences import Preferences
from scripts.smoke_fixture import create_pdf

app=QApplication.instance() or QApplication([])
app.setProperty('offlineTests',True)
def settle():
    for _ in range(12): app.processEvents()

class ReadingMemoryTests(unittest.TestCase):
    def test_close_reopen_restart_and_disable(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'reading.pdf'; create_pdf(path,6)
            ini=str(Path(temp)/'settings.ini')
            def window():
                w=Window(Preferences(QSettings(ini,QSettings.Format.IniFormat))); w.show(); settle(); return w
            w=window()
            try:
                w.open(str(path)); settle(); w.mode.setCurrentIndex(1); w.set_zoom(1.75); settle()
                w.scroll.horizontalScrollBar().setValue(83); w.scroll.verticalScrollBar().setValue(2350); settle()
                expected=(w.current,w.zoom,w.scroll.horizontalScrollBar().value(),w.scroll.verticalScrollBar().value())
                self.assertGreater(expected[3],0)
                w.close_current_tab(); w.open(str(path)); settle()
                self.assertEqual((w.current,w.zoom,w.scroll.horizontalScrollBar().value(),w.scroll.verticalScrollBar().value()),expected)
                w.help(); self.assertEqual(w.settings_panel.categories.currentItem().text(),'도움말'); self.assertTrue(w.settings_dialog.isVisible()); w.settings_dialog.hide()
            finally: w.close(); settle()
            w=window()
            try:
                w.open(str(path)); settle()
                self.assertEqual((w.current,w.zoom,w.scroll.horizontalScrollBar().value(),w.scroll.verticalScrollBar().value()),expected)
                w.settings_panel.controls['remember_document'].setChecked(False)
                w.close_current_tab(); w.open(str(path)); settle()
                self.assertEqual(w.current,0); self.assertEqual(w.fit_mode,'page')
            finally: w.close(); settle()

    def test_modified_and_corrupt_records_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'changed.pdf'; create_pdf(path,3)
            prefs=Preferences(QSettings(str(Path(temp)/'settings.ini'),QSettings.Format.IniFormat))
            w=Window(prefs); w.show(); settle()
            try:
                w.open(str(path)); settle(); w.set_zoom(2.); settle(); w.close_current_tab()
                key=prefs.document_key(path); record=json.loads(prefs.storage.value(key))
                record['mtime']-=1; prefs.storage.setValue(key,json.dumps(record))
                w.open(str(path)); settle(); self.assertEqual(w.fit_mode,'page'); w.close_current_tab()
                prefs.storage.setValue(key,'bad json'); w.open(str(path)); settle(); self.assertEqual(w.fit_mode,'page')
            finally: w.close(); settle()
