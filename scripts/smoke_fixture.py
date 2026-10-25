"""Create a local PDF fixture for frozen executable smoke checks."""
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtGui import QPainter
app=QApplication([])
path=Path(sys.argv[1]); path.parent.mkdir(parents=True,exist_ok=True)
printer=QPrinter(); printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat); printer.setOutputFileName(str(path.resolve()))
painter=QPainter(printer)
for i in range(4):
    if i: printer.newPage()
    painter.drawText(100,100,f'PDFeather print preview test {i+1}')
painter.end()
