"""Isolated printing: no printer driver or preview rendering on the UI thread."""
import math
from pathlib import Path
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPageSize, QPageLayout, QColor, QPen
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo
from layout import grid, placement, print_cells, print_placement


def make_printer(settings, output=None, preview=False):
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    if output:
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(output))
    else:
        printer.setPrinterName(settings['device'])
    printer.setResolution(110 if preview else 300)
    printer.setPageSize(QPageSize(getattr(QPageSize.PageSizeId, settings['paper'])))
    printer.setPageOrientation(QPageLayout.Orientation.Landscape if settings['landscape'] else QPageLayout.Orientation.Portrait)
    printer.setDuplex([QPrinter.DuplexMode.DuplexNone, QPrinter.DuplexMode.DuplexLongSide, QPrinter.DuplexMode.DuplexShortSide][settings['duplex']])
    printer.setCopyCount(1 if preview else settings['copies'])
    printer.setDocName(Path(settings['path']).name)
    printer.setFullPage(True)
    sheet=printer.pageLayout().fullRect(QPageLayout.Unit.Millimeter)
    print_cells((sheet.width(),sheet.height()),settings.get("margins",[10.,10.,10.,10.]),settings["nup"],settings.get("gap",2.),printer.resolution())
    return printer


def paint_document(doc, printer, settings, progress=None):
    selected = settings['selected']
    n = settings['nup']; cols, rows = grid(n)
    sheet=printer.pageLayout().fullRect(QPageLayout.Unit.Millimeter)
    cells=print_cells((sheet.width(),sheet.height()),settings.get("margins",[10.,10.,10.,10.]),n,settings.get("gap",2.),printer.resolution())
    painter = QPainter()
    if not painter.begin(printer): raise RuntimeError('인쇄 장치를 열 수 없습니다.')
    try:
        for offset in range(0, len(selected), n):
            if offset and not printer.newPage(): raise RuntimeError('다음 인쇄 페이지를 만들 수 없습니다.')
            for pos, index in enumerate(selected[offset:offset+n]):
                cell=QRectF(*cells[pos])
                target = QRectF(*print_placement(doc.sizes[index], (cell.x(),cell.y(),cell.width(),cell.height()), printer.resolution(), settings.get('percent'),settings.get('scale_basis','fit' if settings.get('percent') is None else 'actual')))
                painter.save(); painter.setClipRect(cell)
                painter.drawImage(target, doc.image(index, min(300/72, target.width()/doc.sizes[index][0]), cached=False))
                painter.restore()
            if progress: progress(offset//n+1, math.ceil(len(selected)/n))
    finally:
        painter.end()


def run_job(connection, kind, settings, directory):
    # Spawn gives PDFium a private document and prevents driver stalls from freezing Qt.
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    doc = None
    try:
        if kind == 'devices':
            connection.send(('devices', QPrinterInfo.availablePrinterNames(), QPrinterInfo.defaultPrinterName()))
            return
        from main import Document
        doc = Document(settings['path'], settings.get('password'))
        if kind == 'preview':
            settings = dict(settings)
            start = settings['sheet']*settings['nup']
            settings['selected'] = settings['selected'][start:start+settings['nup']]
            path = str(Path(directory)/'preview.pdf')
            printer = make_printer(settings, path, preview=True)
            paint_document(doc, printer, settings)
            preview = Document(path)
            try:
                image=preview.image(0,1.4,cached=False)
                # Preview-only guides; never included in physical output.
                sheet=printer.pageLayout().fullRect(QPageLayout.Unit.Millimeter)
                guide_cells=print_cells((sheet.width(),sheet.height()),settings.get('margins',[10.,10.,10.,10.]),settings['nup'],settings.get('gap',2.),25.4)
                guide=QPainter(image); guide.setPen(QPen(QColor('#7c9caa'),1,Qt.PenStyle.DashLine))
                for x,y,w,h in guide_cells: guide.drawRect(QRectF(x*image.width()/sheet.width(),y*image.height()/sheet.height(),w*image.width()/sheet.width(),h*image.height()/sheet.height()))
                guide.end(); image.save(str(Path(directory)/'preview.png'))
            finally: preview.close()
            connection.send(('preview', str(Path(directory)/'preview.png')))
        else:
            printer = make_printer(settings)
            paint_document(doc, printer, settings, lambda a,b: connection.send(('progress', a,b)))
            connection.send(('done',))
    except Exception as exc:
        connection.send(('error', str(exc)))
    finally:
        if doc: doc.close()
        connection.close()
