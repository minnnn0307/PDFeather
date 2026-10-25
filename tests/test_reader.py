import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout import parse_pages, placement, grid
from scripts.smoke_fixture import create_pdf
from PySide6.QtWidgets import QApplication
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtGui import QPainter, QPageSize
from main import Document, Window, PrintWindow

app = QApplication.instance() or QApplication([])

class Tests(unittest.TestCase):
    def test_ranges(self):
        self.assertEqual(parse_pages('1-3,5,2', 5), [0,1,2,4])
        self.assertEqual(parse_pages('', 2), [0,1])
        for value in ('0', '4', '3-1', 'a', '1-', '1,,2'):
            with self.assertRaises(ValueError): parse_pages(value, 3)

    def test_layout(self):
        self.assertEqual(placement((100,200),(0,0,400,400),72), (100,0,200,400))
        self.assertEqual(placement((100,200),(0,0,400,400),72,100), (150,100,100,200))
        for n in (1,2,4,6,9,16):
            cols, rows = grid(n); self.assertEqual(cols*rows,n)

    def test_document_modes_and_print(self):
        with tempfile.TemporaryDirectory() as temp, ExitStack() as cleanup:
            source = str(Path(temp)/'input.pdf')
            create_pdf(source,5)
            window = Window(); cleanup.callback(window.close); window.open(source)
            self.assertEqual(len(window.doc.sizes), 5)
            image = window.doc.image(0,1)
            self.assertFalse(image.isNull())
            for mode, count in ((0,1),(1,5),(2,2),(3,5)):
                window.mode.setCurrentIndex(mode); window.go(0)
                self.assertEqual(len(window.canvas.rects),count)
            window.set_zoom(1.5); self.assertEqual(window.zoom,1.5)
            from printing import make_printer, paint_document
            settings=dict(path=source,selected=list(range(5)),nup=2,percent=None,paper='A4',landscape=False,duplex=0,copies=1,device='',sheet=0)
            output=str(Path(temp)/'output.pdf')
            output_printer=make_printer(settings,output)
            paint_document(window.doc,output_printer,settings)
            result=Document(output)
            self.assertEqual(len(result.sizes),3); result.close()
            window.show(); app.processEvents()
            window.mode.setCurrentIndex(1); window.set_zoom(2.0)
            window.scroll.horizontalScrollBar().setValue(100)
            window.scroll.verticalScrollBar().setValue(300)
            from PySide6.QtCore import QPoint, QPointF, Qt, QTimer
            anchor=QPoint(250,220)
            before=window.canvas.mapFrom(window.scroll.viewport(),anchor)
            old_rect=window.canvas.rects[0][1]
            pdf_point=((before.x()-old_rect.x())/window.zoom,(before.y()-old_rect.y())/window.zoom)
            window.set_zoom(2.3,anchor)
            after=window.canvas.mapFrom(window.scroll.viewport(),anchor); rect=window.canvas.rects[0][1]
            self.assertAlmostEqual((after.x()-rect.x())/window.zoom,pdf_point[0],delta=1)
            self.assertAlmostEqual((after.y()-rect.y())/window.zoom,pdf_point[1],delta=1)
            window.mode.setCurrentIndex(0); window.go(0)
            window.scroll.verticalScrollBar().setValue(window.scroll.verticalScrollBar().maximum())
            from PySide6.QtGui import QWheelEvent
            event=QWheelEvent(QPointF(100,100),QPointF(window.scroll.viewport().mapToGlobal(QPoint(100,100))),QPoint(),QPoint(0,-120),Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
            QApplication.sendEvent(window.scroll.viewport(),event)
            self.assertEqual(window.current,1)
            window.show_search(); window.search_input.setText('Page'); window.search_debounce.stop(); window.begin_search()
            for _ in range(6): window.search_step()
            self.assertEqual(len(window.matches),5,window.search_status.text())
            window.next_match(1); self.assertEqual(window.match_index,1)
            # The print dialog must return immediately and keep its event loop alive.
            import time
            started=time.monotonic(); dialog=PrintWindow(window.doc,window); cleanup.callback(dialog.close); dialog.show()
            self.assertLess(time.monotonic()-started,3)
            ticks=[]; heartbeat=QTimer(); heartbeat.setInterval(5); heartbeat.timeout.connect(lambda:ticks.append(1)); heartbeat.start()
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                app.processEvents(); time.sleep(.01)
                if dialog.preview_label.pixmap() and not dialog.preview_label.pixmap().isNull(): break
            heartbeat.stop()
            self.assertGreater(len(ticks),3)
            self.assertTrue(dialog.preview_label.pixmap() and not dialog.preview_label.pixmap().isNull(),dialog.error.text())
            dialog.close(); window.close()

if __name__ == '__main__': unittest.main()
