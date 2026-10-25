import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layout import parse_pages, placement, grid
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
        with tempfile.TemporaryDirectory() as temp:
            source = str(Path(temp)/'input.pdf')
            printer = QPrinter(); printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat); printer.setOutputFileName(source)
            printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            painter = QPainter(printer)
            for i in range(5):
                if i: printer.newPage()
                painter.drawText(100,100,f'Page {i+1}')
            painter.end()
            window = Window(); window.open(source)
            self.assertEqual(len(window.doc.sizes), 5)
            image = window.doc.image(0,1)
            self.assertFalse(image.isNull())
            for mode, count in ((0,1),(1,5),(2,2),(3,5)):
                window.mode.setCurrentIndex(mode); window.go(0)
                self.assertEqual(len(window.canvas.rects),count)
            window.set_zoom(1.5); self.assertEqual(window.zoom,1.5)
            dialog = PrintWindow(window.doc,window)
            dialog.timer.stop()
            output = str(Path(temp)/'output.pdf')
            dialog.printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat); dialog.printer.setOutputFileName(output)
            dialog.nup.setCurrentText('2'); dialog.pages.setText('1-5'); dialog.configure(); dialog.paint(dialog.printer)
            result = Document(output)
            self.assertEqual(len(result.sizes),3); result.close()
            dialog.close(); window.close()

if __name__ == '__main__': unittest.main()
