import sys
import os
import math
from collections import OrderedDict
from pathlib import Path
import pypdfium2 as pdfium
from PySide6.QtCore import Qt, QRectF, QSize, QTimer
from PySide6.QtGui import QImage, QPainter, QColor, QIcon, QPixmap, QKeySequence, QShortcut, QPageLayout, QPageSize
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QScrollArea, QToolBar,
    QPushButton, QComboBox, QSpinBox, QLabel, QFileDialog, QMessageBox, QSplitter,
    QListWidget, QListWidgetItem, QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QInputDialog)
from PySide6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewWidget, QPrinterInfo
from layout import parse_pages, grid, placement


class Document:
    def __init__(self, path, password=None):
        self.pdf = pdfium.PdfDocument(path, password=password)
        if not len(self.pdf):
            self.pdf.close()
            raise ValueError('페이지가 없는 PDF입니다.')
        self.path = path
        self.sizes = [self.pdf.get_page_size(i) for i in range(len(self.pdf))]
        self.cache = OrderedDict()
        self.cache_bytes = 0

    def image(self, index, scale, cached=True):
        # Bound each bitmap to 16 megapixels, and total screen cache to 64 MiB.
        w, h = self.sizes[index]
        scale = min(scale, math.sqrt(16_000_000 / (w*h)))
        key = (index, round(scale, 3))
        if cached and key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        page = self.pdf[index]
        try:
            bitmap = page.render(scale=scale, rev_byteorder=True)
            try:
                image = QImage(bitmap.buffer, bitmap.width, bitmap.height, bitmap.stride,
                               QImage.Format.Format_RGB888 if bitmap.n_channels == 3 else QImage.Format.Format_RGBA8888).copy()
            finally:
                bitmap.close()
        finally:
            page.close()
        if cached:
            self.cache[key] = image
            self.cache_bytes += image.sizeInBytes()
            while self.cache_bytes > 64*1024*1024 and self.cache:
                _, old = self.cache.popitem(last=False)
                self.cache_bytes -= old.sizeInBytes()
        return image

    def close(self):
        self.cache.clear()
        self.pdf.close()


class Canvas(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.rects = []

    def arrange(self):
        w = self.window
        self.rects = []
        if not w.doc:
            self.resize(700, 700)
            self.update()
            return
        two = w.mode.currentIndex() >= 2
        continuous = w.mode.currentIndex() in (1, 3)
        indices = list(range(len(w.doc.sizes))) if continuous else list(range((w.current//2)*2 if two else w.current, min(len(w.doc.sizes), (w.current//2)*2+2 if two else w.current+1)))
        y, max_width = 24., 0.
        for start in range(0, len(indices), 2 if two else 1):
            row = indices[start:start+(2 if two else 1)]
            sizes = [(i, w.doc.sizes[i][0]*w.zoom, w.doc.sizes[i][1]*w.zoom) for i in row]
            row_width = sum(s[1] for s in sizes) + 20*(len(row)-1)
            x = 24.
            for i, width, height in sizes:
                self.rects.append((i, QRectF(x, y, width, height)))
                x += width + 20
            y += max(s[2] for s in sizes) + 24
            max_width = max(max_width, row_width+48)
        self.resize(max(1, math.ceil(max_width)), max(1, math.ceil(y)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor('#e7e9ed'))
        w = self.window
        if not w.doc:
            painter.setPen(QColor('#566176'))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 'PDF 파일을 열거나 이 창으로 끌어 놓으세요\nCtrl+O')
            return
        try:
            for i, rect in self.rects:
                if rect.intersects(QRectF(event.rect())):
                    painter.fillRect(rect, Qt.GlobalColor.white)
                    painter.drawImage(rect, w.doc.image(i, w.zoom))
        except Exception as exc:
            painter.drawText(event.rect(), Qt.AlignmentFlag.AlignCenter, f'렌더링 오류: {exc}')


class PrintWindow(QDialog):
    def __init__(self, doc, parent):
        super().__init__(parent)
        self.doc = doc
        self.setWindowTitle('인쇄 · 미리보기')
        self.resize(1100, 760)
        self.printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        self.printer.setResolution(300)
        self.printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        self.printer.setDocName(Path(doc.path).name)
        self.pages = QLineEdit()
        self.pages.setPlaceholderText('전체 (예: 1-3,5)')
        self.orientation = QComboBox(); self.orientation.addItems(['세로', '가로'])
        self.duplex = QComboBox(); self.duplex.addItems(['단면', '양면 · 긴 쪽 넘김', '양면 · 짧은 쪽 넘김'])
        self.nup = QComboBox(); self.nup.addItems(['1', '2', '4', '6', '9', '16'])
        self.scale_mode = QComboBox(); self.scale_mode.addItems(['용지에 맞춤', '실제 크기 (100%)', '사용자 배율'])
        self.scale = QSpinBox(); self.scale.setRange(10, 400); self.scale.setValue(100); self.scale.setSuffix('%')
        self.paper = QComboBox(); self.paper.addItems(['A4', 'A3', 'Letter', 'Legal'])
        self.devices = QComboBox(); self.devices.addItems(QPrinterInfo.availablePrinterNames())
        self.copies = QSpinBox(); self.copies.setRange(1, 999)
        self.error = QLabel(); self.error.setWordWrap(True); self.error.setStyleSheet('color:#b42318')
        form = QFormLayout()
        for label, control in [('프린터', self.devices), ('용지', self.paper), ('페이지', self.pages), ('방향', self.orientation), ('양면', self.duplex), ('한 면당 페이지', self.nup), ('배율', self.scale_mode), ('사용자 배율', self.scale), ('매수', self.copies)]:
            form.addRow(label, control)
        settings = QWidget(); side = QVBoxLayout(settings); side.addLayout(form)
        side.addWidget(QLabel('사용자 배율은 각 칸의 중앙을 기준으로 적용됩니다.\n칸을 벗어나는 부분은 잘립니다.\n양면은 프린터 지원이 필요합니다.'))
        refresh = QPushButton('미리보기 갱신'); refresh.clicked.connect(self.refresh)
        native = QPushButton('프린터 속성…'); native.clicked.connect(self.native_settings)
        submit = QPushButton('인쇄'); submit.clicked.connect(self.submit)
        side.addWidget(refresh); side.addWidget(native); side.addWidget(submit); side.addWidget(self.error); side.addStretch()
        self.preview = QPrintPreviewWidget(self.printer, self)
        self.preview.paintRequested.connect(self.paint_preview)
        root = QHBoxLayout(self); root.addWidget(settings, 0); root.addWidget(self.preview, 1)
        self.timer = QTimer(self); self.timer.setSingleShot(True); self.timer.setInterval(300); self.timer.timeout.connect(self.refresh)
        for box in [self.orientation, self.duplex, self.nup, self.scale_mode, self.paper, self.devices]:
            box.currentIndexChanged.connect(lambda *_: self.timer.start())
        self.pages.textChanged.connect(lambda *_: self.timer.start())
        self.scale.valueChanged.connect(lambda *_: self.timer.start())
        QTimer.singleShot(0, self.refresh)

    def configure(self):
        self.selected = parse_pages(self.pages.text(), len(self.doc.sizes))
        if self.devices.currentText(): self.printer.setPrinterName(self.devices.currentText())
        self.printer.setPageSize(QPageSize(getattr(QPageSize.PageSizeId, self.paper.currentText())))
        self.printer.setPageOrientation(QPageLayout.Orientation.Landscape if self.orientation.currentIndex() else QPageLayout.Orientation.Portrait)
        self.printer.setDuplex([QPrinter.DuplexMode.DuplexNone, QPrinter.DuplexMode.DuplexLongSide, QPrinter.DuplexMode.DuplexShortSide][self.duplex.currentIndex()])
        self.printer.setCopyCount(self.copies.value())
        self.printer.setFullPage(False)

    def refresh(self):
        try:
            self.configure(); self.error.clear(); self.preview.updatePreview()
        except Exception as exc: self.error.setText(str(exc))

    def paint_preview(self, printer):
        try: self.paint(printer)
        except Exception as exc: self.error.setText(str(exc))

    def native_settings(self):
        try: self.configure()
        except ValueError as exc: self.error.setText(str(exc)); return
        dialog = QPrintDialog(self.printer, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.devices.setCurrentText(self.printer.printerName())
            self.orientation.setCurrentIndex(int(self.printer.pageLayout().orientation() == QPageLayout.Orientation.Landscape))
            modes = [QPrinter.DuplexMode.DuplexNone, QPrinter.DuplexMode.DuplexLongSide, QPrinter.DuplexMode.DuplexShortSide]
            if self.printer.duplex() in modes: self.duplex.setCurrentIndex(modes.index(self.printer.duplex()))
            self.copies.setValue(self.printer.copyCount())
            self.refresh()

    def submit(self):
        try:
            self.configure()
            if not self.devices.currentText(): raise ValueError('사용 가능한 프린터가 없습니다.')
            self.paint(self.printer)
        except Exception as exc: self.error.setText(str(exc)); return
        self.accept()

    def paint(self, printer):
        selected = parse_pages(self.pages.text(), len(self.doc.sizes))
        n = int(self.nup.currentText()); cols, rows = grid(n)
        area = printer.pageRect(QPrinter.Unit.DevicePixel)
        cw, ch = area.width()/cols, area.height()/rows
        percent = None if self.scale_mode.currentIndex() == 0 else 100 if self.scale_mode.currentIndex() == 1 else self.scale.value()
        painter = QPainter()
        if not painter.begin(printer): raise RuntimeError('인쇄 장치를 열 수 없습니다.')
        try:
            for offset in range(0, len(selected), n):
                if offset and not printer.newPage(): raise RuntimeError('다음 인쇄 페이지를 만들 수 없습니다.')
                for pos, index in enumerate(selected[offset:offset+n]):
                    cell = QRectF((pos%cols)*cw, (pos//cols)*ch, cw, ch).adjusted(8, 8, -8, -8)
                    target = QRectF(*placement(self.doc.sizes[index], (cell.x(),cell.y(),cell.width(),cell.height()), printer.resolution(), percent))
                    scale = min(4.167, target.width()/self.doc.sizes[index][0])
                    painter.save(); painter.setClipRect(cell)
                    painter.drawImage(target, self.doc.image(index, scale, cached=False)); painter.restore()
        finally: painter.end()


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.doc = None; self.current = 0; self.zoom = 1.0
        self.setWindowTitle('Feather PDF'); self.resize(1200, 850); self.setAcceptDrops(True)
        bar = QToolBar(); bar.setMovable(False); self.addToolBar(bar)
        def button(text, callback):
            b = QPushButton(text); b.clicked.connect(callback); bar.addWidget(b); return b
        button('파일 열기', self.choose)
        button('−', lambda: self.set_zoom(self.zoom/1.15))
        self.zoom_box = QSpinBox(); self.zoom_box.setRange(10, 500); self.zoom_box.setSuffix('%'); self.zoom_box.setValue(100)
        self.zoom_box.valueChanged.connect(lambda v: self.set_zoom(v/100)); bar.addWidget(self.zoom_box)
        button('+', lambda: self.set_zoom(self.zoom*1.15))
        self.mode = QComboBox(); self.mode.addItems(['단일', '단일 스크롤', '2페이지', '2페이지 스크롤']); self.mode.setCurrentIndex(1)
        self.mode.currentIndexChanged.connect(self.change_mode); bar.addWidget(self.mode)
        button('이전', lambda: self.go(self.current-(2 if self.mode.currentIndex()>=2 else 1)))
        self.page = QSpinBox(); self.page.setRange(1,1); self.page.valueChanged.connect(lambda v: self.go(v-1)); bar.addWidget(self.page)
        self.total = QLabel(' / 0  '); bar.addWidget(self.total)
        button('다음', lambda: self.go(self.current+(2 if self.mode.currentIndex()>=2 else 1)))
        button('PDF 정보', self.info); button('인쇄', self.print_document)
        self.thumbs = QListWidget(); self.thumbs.setIconSize(QSize(112, 150)); self.thumbs.setMinimumWidth(150)
        self.thumbs.currentRowChanged.connect(self.go)
        self.scroll = QScrollArea(); self.scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.canvas = Canvas(self); self.scroll.setWidget(self.canvas)
        split = QSplitter(); split.addWidget(self.thumbs); split.addWidget(self.scroll); split.setSizes([170, 1030]); self.setCentralWidget(split)
        self.scroll.verticalScrollBar().valueChanged.connect(self.scrolled)
        self.thumbs.verticalScrollBar().valueChanged.connect(self.queue_thumbs)
        self.thumb_timer = QTimer(self); self.thumb_timer.setSingleShot(True); self.thumb_timer.timeout.connect(self.render_thumbs)
        self.statusBar().showMessage('오프라인 PDF 리더 · Ctrl+휠 확대/축소 · Ctrl+O 열기 · Ctrl+P 인쇄')
        QShortcut(QKeySequence.StandardKey.Open, self, activated=self.choose)
        QShortcut(QKeySequence.StandardKey.Print, self, activated=self.print_document)
        QApplication.instance().installEventFilter(self)
        self.canvas.arrange()

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.Wheel and event.modifiers() & Qt.KeyboardModifier.ControlModifier and self.isActiveWindow() and QApplication.activeModalWidget() is None:
            delta = event.angleDelta().y()
            if delta: self.set_zoom(self.zoom * (1.15 if delta>0 else 1/1.15))
            event.accept(); return True
        return super().eventFilter(obj, event)

    def choose(self):
        path, _ = QFileDialog.getOpenFileName(self, 'PDF 열기', '', 'PDF (*.pdf)')
        if path: self.open(path)

    def open(self, path):
        try:
            try: new = Document(path)
            except pdfium.PdfiumError:
                password, ok = QInputDialog.getText(self, 'PDF 열기', '암호화된 PDF라면 비밀번호를 입력하세요.', QLineEdit.EchoMode.Password)
                if not ok: return
                new = Document(path, password)
        except Exception as exc: QMessageBox.warning(self, '열기 실패', str(exc)); return
        old = self.doc; self.doc = new
        if old: old.close()
        self.current = 0; self.thumbs.blockSignals(True); self.thumbs.clear()
        for i in range(len(new.sizes)):
            item = QListWidgetItem(f'{i+1} 페이지'); item.setSizeHint(QSize(130, 175)); self.thumbs.addItem(item)
        self.thumbs.blockSignals(False)
        self.page.setMaximum(len(new.sizes)); self.total.setText(f' / {len(new.sizes)}  ')
        self.setWindowTitle(f'{Path(path).name} — Feather PDF'); self.canvas.arrange(); self.go(0); self.queue_thumbs()

    def queue_thumbs(self, *_): self.thumb_timer.start(30)

    def render_thumbs(self):
        if not self.doc: return
        visible = self.thumbs.viewport().rect()
        for i in range(self.thumbs.count()):
            item = self.thumbs.item(i)
            if item.icon().isNull() and self.thumbs.visualItemRect(item).intersects(visible):
                try: item.setIcon(QIcon(QPixmap.fromImage(self.doc.image(i, 112/self.doc.sizes[i][0], cached=False))))
                except Exception: item.setText(f'{i+1} · 미리보기 실패')
                self.thumb_timer.start(1); return
        # Keep only nearby thumbnail icons in memory.
        top = self.thumbs.indexAt(visible.topLeft()).row()
        for i in range(self.thumbs.count()):
            if abs(i-max(0,top))>30: self.thumbs.item(i).setIcon(QIcon())

    def set_zoom(self, zoom):
        zoom = round(max(.1, min(5., zoom)), 2)
        if zoom == self.zoom: return
        ratio = zoom/self.zoom; sb = self.scroll.verticalScrollBar(); position = sb.value()*ratio
        self.zoom = zoom; self.zoom_box.blockSignals(True); self.zoom_box.setValue(round(zoom*100)); self.zoom_box.blockSignals(False)
        self.canvas.arrange(); sb.setValue(round(position))

    def change_mode(self, *_):
        self.canvas.arrange(); self.go(self.current)

    def go(self, index):
        if not self.doc or index<0: return
        self.current = min(index, len(self.doc.sizes)-1)
        if self.mode.currentIndex() in (0,2): self.canvas.arrange()
        else:
            rect = next((r for i,r in self.canvas.rects if i==self.current), None)
            if rect: self.scroll.verticalScrollBar().setValue(round(rect.top()-24))
        self.sync_page()

    def sync_page(self):
        self.page.blockSignals(True); self.page.setValue(self.current+1); self.page.blockSignals(False)
        self.thumbs.blockSignals(True); self.thumbs.setCurrentRow(self.current); self.thumbs.blockSignals(False)
        self.queue_thumbs()

    def scrolled(self, *_):
        if self.doc and self.mode.currentIndex() in (1,3):
            y = self.scroll.verticalScrollBar().value()+30
            for i, rect in self.canvas.rects:
                if rect.bottom()>=y:
                    if self.current!=i: self.current=i; self.sync_page()
                    break

    def info(self):
        if not self.doc: return
        metadata = self.doc.pdf.get_metadata_dict()
        text = f'파일: {self.doc.path}\n크기: {os.path.getsize(self.doc.path):,} 바이트\n페이지: {len(self.doc.sizes)}\n현재 페이지: {self.doc.sizes[self.current][0]:.1f} × {self.doc.sizes[self.current][1]:.1f} pt\n'
        text += '\n'.join(f'{key}: {value}' for key,value in metadata.items() if value)
        box = QMessageBox(self); box.setWindowTitle('PDF 정보'); box.setTextFormat(Qt.TextFormat.PlainText); box.setText(text); box.exec()

    def print_document(self):
        if self.doc:
            try: PrintWindow(self.doc, self).exec()
            except Exception as exc: QMessageBox.warning(self, '인쇄 오류', str(exc))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(u.isLocalFile() and u.toLocalFile().lower().endswith('.pdf') for u in event.mimeData().urls()): event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if url.isLocalFile() and url.toLocalFile().lower().endswith('.pdf'): self.open(url.toLocalFile()); break

    def closeEvent(self, event):
        if self.doc: self.doc.close()
        super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication(sys.argv); app.setApplicationName('Feather PDF'); app.setStyle('Fusion')
    app.setStyleSheet('QToolBar { spacing:6px; padding:8px; background:#fff; border-bottom:1px solid #ddd; } QPushButton { padding:6px 10px; } QComboBox,QSpinBox { padding:5px; } QListWidget { background:#f7f8fa; border:0; }')
    window = Window(); window.show()
    if len(sys.argv)>1: window.open(sys.argv[1])
    sys.exit(app.exec())
