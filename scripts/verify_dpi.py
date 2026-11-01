"""Exercise the native Windows Qt backend and self-only monitor re-enumeration."""
import sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings,QTimer
from PySide6.QtWidgets import QApplication
from main import Window
from preferences import Preferences
from windows_dpi import native_monitor_scale,refresh_monitor_data

def main():
    app=QApplication([]);app.setProperty('offlineTests',True)
    if app.platformName()!='windows':raise RuntimeError('This check requires the native Windows backend')
    with tempfile.TemporaryDirectory() as folder:
        w=Window(Preferences(QSettings(str(Path(folder)/'p.ini'),QSettings.Format.IniFormat)),enable_updates=False);w.show()
        def check():
            try:
                expected=native_monitor_scale(w)
                assert expected is not None,'Native monitor DPI query failed'
                assert refresh_monitor_data(w),'Qt monitor re-enumeration failed'
                for _ in range(4):app.processEvents()
                assert abs(w.devicePixelRatioF()-expected)<.01,(expected,w.devicePixelRatioF())
                r=w.display_recovery;r.native_message(0x218,4);r.native_message(0x218,18)
                for _ in range(6):r.dpi_timer.stop();r.reconcile_dpi();app.processEvents()
                r.timer.stop();r.refresh()
                assert abs(w.devicePixelRatioF()-expected)<.01
                print(f'Native Windows monitor DPI / Qt DPR verified: {expected:g}',flush=True);code=0
            except Exception:
                import traceback;traceback.print_exc();code=1
            w.close_all();app.exit(code)
        QTimer.singleShot(100,check)
        return app.exec()
if __name__=='__main__':sys.exit(main())
