import sys
import os
import math
import time
import tempfile
import multiprocessing
import ctypes
from collections import OrderedDict
from pathlib import Path
import pypdfium2 as pdfium
from PySide6.QtCore import Qt, QRectF, QSize, QTimer, QPoint, QPointF, QEvent
from PySide6.QtGui import QImage, QPainter, QColor, QIcon, QPixmap, QKeySequence, QShortcut, QPageLayout, QPageSize
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QScrollArea, QToolBar,
    QPushButton, QComboBox, QSpinBox, QLabel, QFileDialog, QMessageBox, QSplitter,
    QListWidget, QListWidgetItem, QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QInputDialog, QFrame, QSizeGrip, QTabWidget, QDoubleSpinBox, QGridLayout, QToolButton)
from layout import parse_pages, grid, placement, print_cells
from widgets import TitleBar, ThumbnailDelegate, tool, set_theme, icon
from preferences import Preferences, SettingsPanel
from branding import application_icon, logo_pixmap
from themes import PALETTES, stylesheet, apply_palette


STYLE = stylesheet('dark')

class Document:
    def __init__(self, path, password=None):
        self.pdf = pdfium.PdfDocument(path, password=password)
        if not len(self.pdf):
            self.pdf.close()
            raise ValueError('페이지가 없는 PDF입니다.')
        self.path = path
        self.password = password
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
        rows=[]
        for start in range(0,len(indices),2 if two else 1):
            row=indices[start:start+(2 if two else 1)]
            sizes=[(i,w.doc.sizes[i][0]*w.zoom,w.doc.sizes[i][1]*w.zoom) for i in row]
            rows.append(sizes)
        width=max([sum(v[1] for v in row)+(len(row)-1) for row in rows]+[w.scroll.viewport().width()])
        content_height=sum(max(v[2] for v in row) for row in rows)+(len(rows) if continuous else 0)
        canvas_height=max(w.scroll.viewport().height(),math.ceil(content_height))
        y=0. if continuous else max(0.,(canvas_height-content_height)/2)
        for row in rows:
            x=(width-sum(v[1] for v in row)-(len(row)-1))/2
            for i,pw,ph in row:
                self.rects.append((i,QRectF(x,y,pw,ph))); x+=pw+1
            y+=max(v[2] for v in row)+(1 if continuous else 0)
        self.resize(max(1,math.ceil(width)),max(w.scroll.viewport().height(),math.ceil(y)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor(self.window.theme['canvas']))
        w = self.window
        if not w.doc:
            painter.setPen(QColor(self.window.theme['muted']))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 'PDF 파일을 열거나 이 창으로 끌어 놓으세요\nCtrl+O')
            return
        try:
            for i, rect in self.rects:
                if rect.intersects(QRectF(event.rect())):
                    painter.fillRect(rect, Qt.GlobalColor.white)
                    painter.drawImage(rect, w.doc.image(i, w.zoom))
                    if w.mode.currentIndex() in (1,3):
                        painter.setPen(QColor('#9ca3af'))
                        painter.drawLine(QPointF(rect.left(),rect.bottom()),QPointF(rect.right(),rect.bottom()))
                    for match_no,(page_no,boxes) in enumerate(w.matches):
                        if page_no!=i: continue
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.setBrush(QColor(255,151,45,145) if match_no==w.match_index else QColor(255,220,40,100))
                        for l,b,r,t in boxes:
                            painter.drawRect(QRectF(rect.x()+l*w.zoom,rect.y()+(w.doc.sizes[i][1]-t)*w.zoom,(r-l)*w.zoom,(t-b)*w.zoom))
        except Exception as exc:
            painter.drawText(event.rect(), Qt.AlignmentFlag.AlignCenter, f'렌더링 오류: {exc}')


class PrintWindow(QDialog):
    def __init__(self, doc, parent):
        super().__init__(parent)
        self.doc=doc; self.process=None; self.connection=None; self.kind=None
        self.temp=tempfile.TemporaryDirectory(prefix='pdfeather-print-')
        self.setWindowTitle('PDFeather · 인쇄'); self.resize(1100,780)
        self.pages=QLineEdit(); self.pages.setPlaceholderText('전체 (예: 1-3,5)')
        self.orientation=QComboBox(); self.orientation.addItems(['세로','가로'])
        self.duplex=QComboBox(); self.duplex.addItems(['단면','양면 · 긴 쪽 넘김','양면 · 짧은 쪽 넘김'])
        self.nup=QComboBox(); self.nup.addItems(['1','2','4','6','9','16'])
        self.scale_mode=QComboBox(); self.scale_mode.addItems(['용지에 맞춤','실제 크기 (100%)','사용자 배율'])
        self.scale=QSpinBox(); self.scale.setRange(10,400); self.scale.setValue(100); self.scale.setSuffix('%')
        self.paper=QComboBox(); self.paper.addItems(['A4','A3','Letter','Legal'])
        prefs=parent.prefs
        self.paper.setCurrentText(prefs.get('print_paper')); self.duplex.setCurrentIndex(prefs.get('print_duplex'))
        self.margins={}
        for key in ('left','top','right','bottom'):
            spin=SettingsPanel.mm(); spin.setValue(prefs.get('margin_'+key)); self.margins[key]=spin
        self.gap=SettingsPanel.mm(); self.gap.setValue(prefs.get('print_gap'))
        self.devices=QComboBox(); self.devices.setPlaceholderText('프린터 조회 중…')
        self.copies=QSpinBox(); self.copies.setRange(1,999)
        self.sheet=QSpinBox(); self.sheet.setRange(1,1)
        self.sheets=QLabel('/ 1 면')
        self.error=QLabel(); self.error.setObjectName('errorText'); self.error.setWordWrap(True)
        self.state=QLabel('프린터 조회 중…'); self.state.setWordWrap(True)
        form=QFormLayout()
        for label,control in [('프린터',self.devices),('용지',self.paper),('페이지',self.pages),('방향',self.orientation),('양면',self.duplex),('한 면당 페이지',self.nup),('배율',self.scale_mode),('사용자 배율',self.scale),('매수',self.copies)]: form.addRow(label,control)
        margins_widget=QWidget(); mg=QGridLayout(margins_widget); mg.setContentsMargins(0,0,0,0)
        for i,(key,label) in enumerate([('left','왼쪽'),('top','위'),('right','오른쪽'),('bottom','아래')]):
            mg.addWidget(QLabel(label),i//2,(i%2)*2); mg.addWidget(self.margins[key],i//2,(i%2)*2+1)
        form.addRow('용지 여백',margins_widget); form.addRow('페이지 사이 간격',self.gap)
        form.addRow(QLabel('미리보기 점선: 인쇄 영역 (출력되지 않음)'))
        self.settings_widget=QWidget(); side=QVBoxLayout(self.settings_widget); side.addLayout(form)
        hint=QLabel('사용자 배율은 각 칸 중앙 기준이며\n칸 밖은 잘립니다. 양면과 0 mm 무테 출력은\n프린터 지원이 필요합니다.'); hint.setWordWrap(True); side.addWidget(hint)
        self.submit_button=QPushButton('인쇄'); self.submit_button.clicked.connect(self.submit); side.addWidget(self.submit_button)
        retry=QPushButton('프린터 다시 조회'); retry.clicked.connect(lambda:self.start_job('devices',{}) if self.kind!='print' else None); side.addWidget(retry)
        self.cancel_button=QPushButton('작업 중단'); self.cancel_button.clicked.connect(self.cancel_job); side.addWidget(self.cancel_button)
        side.addWidget(self.state); side.addWidget(self.error); side.addStretch()
        self.preview_label=QLabel('미리보기 준비 중…'); self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_area=QScrollArea(); self.preview_area.setWidgetResizable(True); self.preview_area.setWidget(self.preview_label)
        preview_box=QWidget(); preview_layout=QVBoxLayout(preview_box); preview_layout.setContentsMargins(0,0,0,0)
        nav=QHBoxLayout(); nav.addStretch(); nav.addWidget(tool('prev','이전 용지',lambda:self.sheet.setValue(self.sheet.value()-1))); nav.addWidget(self.sheet); nav.addWidget(self.sheets); nav.addWidget(tool('next','다음 용지',lambda:self.sheet.setValue(self.sheet.value()+1))); nav.addStretch()
        preview_layout.addLayout(nav); preview_layout.addWidget(self.preview_area)
        root=QHBoxLayout(self); settings_scroll=QScrollArea(); settings_scroll.setWidgetResizable(True); settings_scroll.setWidget(self.settings_widget); settings_scroll.setMinimumWidth(370); root.addWidget(settings_scroll,0); root.addWidget(preview_box,1)
        self.timer=QTimer(self); self.timer.setSingleShot(True); self.timer.setInterval(300); self.timer.timeout.connect(self.refresh)
        self.poll_timer=QTimer(self); self.poll_timer.setInterval(70); self.poll_timer.timeout.connect(self.poll); self.poll_timer.start()
        for box in [self.orientation,self.duplex,self.nup,self.scale_mode,self.paper]: box.currentIndexChanged.connect(self.schedule)
        for control in [*self.margins.values(),self.gap]: control.valueChanged.connect(self.schedule)
        self.pages.textChanged.connect(self.schedule); self.scale.valueChanged.connect(self.schedule); self.sheet.valueChanged.connect(self.schedule)
        self.start_job('devices',{})

    def settings(self):
        selected=parse_pages(self.pages.text(),len(self.doc.sizes))
        count=math.ceil(len(selected)/int(self.nup.currentText()))
        self.sheet.blockSignals(True); self.sheet.setMaximum(count); self.sheet.blockSignals(False); self.sheets.setText(f'/ {count} 면')
        margins=[self.margins[key].value() for key in ('left','top','right','bottom')]
        size=QPageSize(getattr(QPageSize.PageSizeId,self.paper.currentText())).size(QPageSize.Unit.Millimeter)
        page_mm=(size.height(),size.width()) if self.orientation.currentIndex() else (size.width(),size.height())
        print_cells(page_mm,margins,int(self.nup.currentText()),self.gap.value(),72)
        return dict(margins=margins,gap=self.gap.value(),path=self.doc.path,password=self.doc.password,selected=selected,nup=int(self.nup.currentText()),
            percent=None if self.scale_mode.currentIndex()==0 else 100 if self.scale_mode.currentIndex()==1 else self.scale.value(),
            paper=self.paper.currentText(),landscape=bool(self.orientation.currentIndex()),duplex=self.duplex.currentIndex(),
            copies=self.copies.value(),device=self.devices.currentText(),sheet=self.sheet.value()-1)

    def schedule(self,*_):
        if self.kind=='print': return
        self.timer.start()

    def start_job(self,kind,settings):
        from printing import run_job
        self.stop_job()
        context=multiprocessing.get_context('spawn')
        receiver,sender=context.Pipe(duplex=False)
        self.connection=receiver; self.kind=kind
        self.process=context.Process(target=run_job,args=(sender,kind,settings,self.temp.name),daemon=True)
        self.process.start(); sender.close()
        self.started=time.monotonic()
        self.set_busy(kind=='print')

    def set_busy(self,busy):
        for control in [self.pages,self.orientation,self.duplex,self.nup,self.scale_mode,self.scale,self.paper,self.devices,self.copies,self.sheet,self.submit_button,self.gap,*self.margins.values()]: control.setEnabled(not busy)

    def stop_job(self):
        if self.process:
            if self.process.is_alive(): self.process.terminate()
            self.process.join(timeout=.2)
            if not self.process.is_alive(): self.process.close()
            self.process=None
        if self.connection: self.connection.close(); self.connection=None
        self.kind=None; self.set_busy(False)

    def refresh(self):
        if self.kind=='print': return
        if self.kind=='devices': return
        try:
            settings=self.settings(); self.error.clear(); self.state.setText('용지 미리보기 생성 중…'); self.preview_label.setText('미리보기 생성 중…')
            self.start_job('preview',settings)
        except Exception as exc: self.error.setText(str(exc))

    def poll(self):
        if not self.connection: return
        try:
            while self.connection.poll():
                message=self.connection.recv(); kind=message[0]
                if kind=='devices':
                    self.devices.clear(); self.devices.addItems(message[1]); self.devices.setCurrentText(message[2])
                    self.state.setText(''); self.stop_job(); self.refresh(); return
                if kind=='preview':
                    pix=QPixmap(message[1]); self.preview_label.setPixmap(pix.scaled(QSize(720,850),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
                    self.state.setText('미리보기 · 선택한 용지 1면'); self.stop_job(); return
                if kind=='progress': self.state.setText(f'인쇄 데이터 전송 중… {message[1]} / {message[2]} 면')
                if kind=='done':
                    self.stop_job(); self.settings_widget.setEnabled(True); self.submit_button.setEnabled(True); self.state.setText('프린터로 전송했습니다.'); return
                if kind=='error':
                    self.error.setText(message[1]); self.stop_job(); self.settings_widget.setEnabled(True); self.submit_button.setEnabled(True); return
        except (EOFError,OSError):
            self.error.setText('인쇄 작업이 종료되었습니다. 다시 시도하세요.'); self.stop_job(); self.submit_button.setEnabled(True); return
        if self.process and not self.process.is_alive():
            self.error.setText('인쇄 작업이 비정상 종료되었습니다.'); self.stop_job(); self.submit_button.setEnabled(True)
        elif self.kind=='devices' and time.monotonic()-self.started>12:
            self.stop_job(); self.state.setText('프린터 조회 시간이 초과되었습니다. 프린터 연결을 확인하세요.'); self.refresh()

    def submit(self):
        try:
            settings=self.settings()
            if not settings['device']: raise ValueError('사용 가능한 프린터가 없습니다.')
            self.timer.stop(); self.state.setText('프린터에 연결 중…'); self.start_job('print',settings)
        except Exception as exc: self.error.setText(str(exc))

    def cancel_job(self):
        printing=self.kind=='print'; self.stop_job(); self.timer.stop(); self.settings_widget.setEnabled(True); self.submit_button.setEnabled(True)
        self.state.setText('중단했습니다. 이미 전송된 작업은 Windows 인쇄 대기열에서 취소하세요.' if printing else '작업을 중단했습니다.')

    def done(self,result):
        self.timer.stop(); self.poll_timer.stop(); self.stop_job(); self.temp.cleanup(); super().done(result)


class Window(QMainWindow):
    def __init__(self, preferences=None):
        super().__init__()
        self.prefs=preferences if preferences is not None else Preferences()
        self.theme_name=self.prefs.get('theme'); self.theme=PALETTES[self.theme_name]
        set_theme(self.theme_name)
        self.doc=None; self.current=0; self.zoom=1.; self.fit_mode=None; self.last_flip=0
        self.matches=[]; self.match_index=-1; self.search_page=0; self.search_query=''; self.suppress_scroll=False
        self.setWindowFlags(Qt.WindowType.Window|Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle('PDFeather 1.1.0'); self.resize(1200,850); self.setMinimumSize(900,540); self.setAcceptDrops(True)
        shell=QWidget(); shell.setObjectName('shell'); root=QVBoxLayout(shell); root.setSpacing(0); root.setContentsMargins(0,0,0,0)
        self.titlebar=TitleBar(self); root.addWidget(self.titlebar)
        outer=root; self.tabs=QTabWidget(); outer.addWidget(self.tabs,1)
        reader=QWidget(); root=QVBoxLayout(reader); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        self.tabs.addTab(reader,'문서')
        toolbar=QWidget(); toolbar.setObjectName('toolbar'); bar=QHBoxLayout(toolbar); bar.setContentsMargins(10,7,12,7); bar.setSpacing(6)
        for name,tip,callback in [('sidebar','썸네일 표시 / 숨기기',self.toggle_sidebar),('open','파일 열기 · Ctrl+O',self.choose),('print','인쇄 · Ctrl+P',self.print_document),('search','찾기 · Ctrl+F',self.show_search)]: bar.addWidget(tool(name,tip,callback))
        bar.addSpacing(12)
        self.mode=QComboBox(); self.mode.addItems(['단일','단일 스크롤','2페이지','2페이지 스크롤']); self.mode.setCurrentIndex(self.prefs.get('default_mode')); self.mode.currentIndexChanged.connect(self.change_mode)
        bar.addWidget(tool('fit','쪽 맞추기 · Ctrl+0',lambda:self.fit('page'))); bar.addWidget(tool('width','너비 맞추기 · Ctrl+1',lambda:self.fit('width')))
        bar.addStretch(); bar.addWidget(tool('info','PDF 정보',self.info)); bar.addWidget(tool('settings','설정',lambda:self.tabs.setCurrentIndex(1))); bar.addWidget(tool('help','도움말 · F1',self.help))
        root.addWidget(toolbar)
        self.search_bar=QWidget(); search_layout=QHBoxLayout(self.search_bar); search_layout.setContentsMargins(12,5,12,5)
        self.search_input=QLineEdit(); self.search_input.setPlaceholderText('문서에서 찾기 · Enter 다음 / Shift+Enter 이전')
        self.search_status=QLabel(''); search_layout.addWidget(self.search_input,1); search_layout.addWidget(self.search_status)
        search_layout.addWidget(tool('prev','이전 검색 결과',lambda:self.next_match(-1))); search_layout.addWidget(tool('next','다음 검색 결과',lambda:self.next_match(1))); search_layout.addWidget(tool('close','찾기 닫기 · Esc',self.hide_search))
        self.search_bar.hide(); root.addWidget(self.search_bar)
        self.search_debounce=QTimer(self); self.search_debounce.setSingleShot(True); self.search_debounce.setInterval(250); self.search_debounce.timeout.connect(self.begin_search)
        self.search_timer=QTimer(self); self.search_timer.setInterval(1); self.search_timer.timeout.connect(self.search_step)
        self.search_input.textChanged.connect(lambda *_:self.search_debounce.start()); self.search_input.returnPressed.connect(lambda:self.next_match(-1 if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier else 1))
        self.thumbs=QListWidget(); self.thumbs.setIconSize(QSize(130,165)); self.thumbs.setMinimumWidth(140); self.thumbs.setItemDelegate(ThumbnailDelegate(self.thumbs)); self.thumbs.currentRowChanged.connect(self.go)
        self.scroll=QScrollArea(); self.scroll.setFrameShape(QFrame.Shape.NoFrame); self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas=Canvas(self); self.scroll.setWidget(self.canvas)
        self.split=QSplitter(); self.split.setHandleWidth(1); self.split.addWidget(self.thumbs); self.split.addWidget(self.scroll); self.split.setSizes([164,1036]); root.addWidget(self.split,1)
        footer=QWidget(); footer.setObjectName('footer'); bottom=QHBoxLayout(footer); bottom.setContentsMargins(10,4,7,4)
        left=QWidget(); left.setMinimumWidth(320); bottom.addWidget(left,1)
        nav=QHBoxLayout(); nav.setSpacing(4)
        nav.addWidget(tool('prev','이전 페이지 · PageUp',lambda:self.turn(-1)))
        self.page=QSpinBox(); self.page.setRange(1,1); self.page.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons); self.page.setAlignment(Qt.AlignmentFlag.AlignCenter); self.page.setFixedWidth(58); self.page.valueChanged.connect(lambda v:self.go(v-1)); nav.addWidget(self.page)
        self.total=QLabel('/ 0'); nav.addWidget(self.total); nav.addWidget(tool('next','다음 페이지 · PageDown',lambda:self.turn(1)))
        bottom.addLayout(nav)
        right=QHBoxLayout(); right.setSpacing(2); right.addStretch(); right.addWidget(self.mode); right.addSpacing(8); right.addWidget(tool('minus','축소 · Ctrl+−',lambda:self.set_zoom(self.zoom/1.15)))
        self.zoom_box=QSpinBox(); self.zoom_box.setRange(10,500); self.zoom_box.setValue(100); self.zoom_box.setSuffix('%'); self.zoom_box.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons); self.zoom_box.setAlignment(Qt.AlignmentFlag.AlignCenter); self.zoom_box.setFixedWidth(66); self.zoom_box.valueChanged.connect(lambda v:self.set_zoom(v/100)); right.addWidget(self.zoom_box)
        right.addWidget(tool('plus','확대 · Ctrl++',lambda:self.set_zoom(self.zoom*1.15))); right.addWidget(QSizeGrip(self))
        rw=QWidget(); rw.setMinimumWidth(320); rw.setLayout(right); right.setContentsMargins(0,0,0,0); bottom.addWidget(rw,1)
        root.addWidget(footer)
        self.settings_panel=SettingsPanel(self.prefs); self.settings_panel.changed.connect(self.preference_changed)
        settings_scroll=QScrollArea(); settings_scroll.setWidgetResizable(True); settings_scroll.setWidget(self.settings_panel)
        self.tabs.addTab(settings_scroll,'설정'); self.setCentralWidget(shell)
        self.thumbs.setVisible(self.prefs.get('show_thumbnails'))
        if self.prefs.get('remember_geometry'):
            geometry=self.prefs.storage.value('window_geometry')
            if geometry is not None: self.restoreGeometry(geometry)
        self.scroll.verticalScrollBar().valueChanged.connect(self.scrolled)
        self.thumbs.verticalScrollBar().valueChanged.connect(self.queue_thumbs)
        self.thumb_timer=QTimer(self); self.thumb_timer.setSingleShot(True); self.thumb_timer.timeout.connect(self.render_thumbs)
        for key,callback in [(QKeySequence.StandardKey.Open,self.choose),(QKeySequence.StandardKey.Print,self.print_document),(QKeySequence.StandardKey.Find,self.show_search),('Escape',self.hide_search),('F1',self.help),('Ctrl+,',lambda:self.tabs.setCurrentIndex(1)),('F3',lambda:self.next_match(1)),('Shift+F3',lambda:self.next_match(-1)),('Ctrl+0',lambda:self.fit('page')),('Ctrl+1',lambda:self.fit('width')),('Ctrl+=',lambda:self.set_zoom(self.zoom*1.15)),('Ctrl+-',lambda:self.set_zoom(self.zoom/1.15)),('PgDown',lambda:self.turn(1)),('PgUp',lambda:self.turn(-1))]: QShortcut(QKeySequence(key),self,activated=callback)
        QApplication.instance().installEventFilter(self)
        self.canvas.arrange()
        self.apply_theme(self.theme_name)

    def apply_theme(self,name):
        self.theme_name=name; self.theme=PALETTES[name]; set_theme(name)
        apply_palette(QApplication.instance(),name)
        for button in self.findChildren(QToolButton):
            key=button.property('iconName')
            if key: button.setIcon(icon(key))
        self.titlebar.brand.setPixmap(logo_pixmap(28,name=='dark'))
        self.setWindowIcon(application_icon(name=='dark'))
        QApplication.instance().setWindowIcon(application_icon(name=='dark'))
        self.canvas.update(); self.thumbs.viewport().update()

    def preference_changed(self,key,value):
        if key=='theme': self.apply_theme(value)
        elif key=='show_thumbnails': self.thumbs.setVisible(value); QTimer.singleShot(0,self.refit)
        elif key=='default_mode': self.mode.setCurrentIndex(value)
        elif key=='default_fit' and self.doc:
            if value=='actual': self.set_zoom(1.)
            else: self.fit(value)

    def eventFilter(self,obj,event):
        if event.type()==QEvent.Type.Resize and obj==self.scroll.viewport():
            QTimer.singleShot(0,self.refit)
        if event.type()==QEvent.Type.MouseButtonPress and event.button()==Qt.MouseButton.LeftButton and not self.isMaximized() and isinstance(obj,QWidget) and obj.window()==self:
            pt=self.mapFromGlobal(event.globalPosition().toPoint()); edges=Qt.Edge(0)
            if pt.x()<5: edges|=Qt.Edge.LeftEdge
            if pt.x()>self.width()-5: edges|=Qt.Edge.RightEdge
            if pt.y()<5: edges|=Qt.Edge.TopEdge
            if pt.y()>self.height()-5: edges|=Qt.Edge.BottomEdge
            if edges and self.windowHandle() and self.windowHandle().startSystemResize(edges): return True
        if event.type()==QEvent.Type.Wheel and QApplication.activeModalWidget() is None and obj==self.scroll.viewport():
            delta=event.angleDelta().y() or event.pixelDelta().y()
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                factor=1+self.prefs.get('wheel_step')/100
                if delta: self.set_zoom(self.zoom*(factor if delta>0 else 1/factor),event.position().toPoint())
                event.accept(); return True
            if self.doc and self.prefs.get('edge_flip') and self.mode.currentIndex() in (0,2) and delta:
                sb=self.scroll.verticalScrollBar()
                direction=1 if delta<0 else -1
                at_edge=sb.value()>=sb.maximum() if direction>0 else sb.value()<=sb.minimum()
                if at_edge:
                    if time.monotonic()-self.last_flip>.3:
                        self.turn(direction); self.last_flip=time.monotonic()
                        sb.setValue(0 if direction>0 else sb.maximum())
                    event.accept(); return True
        if event.type()==QEvent.Type.KeyPress and obj==self.search_input and event.key()==Qt.Key.Key_Escape: self.hide_search(); return True
        return super().eventFilter(obj,event)

    def turn(self,direction):
        if not self.doc: return
        step=2 if self.mode.currentIndex()>=2 else 1
        self.go(max(0,min(len(self.doc.sizes)-1,self.current+direction*step)))
        if self.mode.currentIndex() in (0,2): self.scroll.verticalScrollBar().setValue(0 if direction>0 else self.scroll.verticalScrollBar().maximum())

    def toggle_sidebar(self):
        self.thumbs.setVisible(self.thumbs.isHidden())
        QTimer.singleShot(0,self.refit)

    def refit(self):
        if self.fit_mode: self.fit(self.fit_mode)
        else: self.canvas.arrange()
        self.queue_thumbs()

    def fit(self,kind):
        if not self.doc: return
        index=(self.current//2)*2 if self.mode.currentIndex()>=2 else self.current
        sizes=self.doc.sizes[index:index+(2 if self.mode.currentIndex()>=2 else 1)]
        width=sum(s[0] for s in sizes); height=max(s[1] for s in sizes)
        available=self.scroll.viewport().size()
        factor=(available.width()-2)/width
        if kind=='page': factor=min(factor,(available.height()-2)/height)
        self.set_zoom(factor,keep_fit=True); self.fit_mode=kind
        rect=next((r for i,r in self.canvas.rects if i==index),None)
        if rect:
            self.suppress_scroll=True
            self.scroll.verticalScrollBar().setValue(round(rect.top()))
            self.scroll.horizontalScrollBar().setValue(max(0,round(rect.center().x()-available.width()/2)))
            self.suppress_scroll=False

    def show_search(self):
        self.tabs.setCurrentIndex(0); self.search_bar.show(); self.search_input.setFocus(); self.search_input.selectAll()

    def hide_search(self):
        self.search_bar.hide(); self.search_timer.stop(); self.search_debounce.stop(); self.matches=[]; self.match_index=-1; self.canvas.update(); self.scroll.setFocus()

    def begin_search(self):
        self.search_timer.stop(); self.matches=[]; self.match_index=-1; self.search_page=0; self.search_query=self.search_input.text().strip()
        self.canvas.update()
        if not self.doc or not self.search_query: self.search_status.setText(''); return
        self.search_status.setText('검색 중…'); self.search_timer.start()

    def search_step(self):
        if not self.doc or self.search_page>=len(self.doc.sizes):
            self.search_timer.stop(); self.update_search_status(); return
        index=self.search_page; self.search_page+=1
        page=self.doc.pdf[index]; text=None; search=None
        try:
            text=page.get_textpage(); search=text.search(self.search_query)
            while len(self.matches)<10000:
                occurrence=search.get_next()
                if occurrence is None: break
                start,count=occurrence
                rectangles=[]
                # Use PDFium's display transform for rotated/cropped pages too.
                width,height=self.doc.sizes[index]
                for j in range(text.count_rects(start,count)):
                    l,b,r,t=text.get_rect(j); points=[]
                    for x,y in ((l,b),(l,t),(r,b),(r,t)):
                        dx,dy=ctypes.c_int(),ctypes.c_int()
                        pdfium.raw.FPDF_PageToDevice(page,0,0,round(width*10),round(height*10),0,x,y,ctypes.byref(dx),ctypes.byref(dy))
                        points.append((dx.value/10,dy.value/10))
                    rectangles.append((min(v[0] for v in points),height-max(v[1] for v in points),max(v[0] for v in points),height-min(v[1] for v in points)))
                self.matches.append((index,rectangles))
            if len(self.matches)>=10000: self.search_timer.stop()
        except Exception as exc:
            self.search_status.setText(f'검색 오류: {exc}'); self.search_timer.stop(); return
        finally:
            if search: search.close()
            if text: text.close()
            page.close()
        if self.matches and self.match_index<0: self.match_index=0; self.reveal_match()
        self.update_search_status(); self.canvas.update()

    def update_search_status(self):
        suffix=' · 검색 중' if self.search_timer.isActive() else ''
        if len(self.matches)>=10000: suffix=' · 최대 10,000개'
        self.search_status.setText(f'{self.match_index+1 if self.matches else 0} / {len(self.matches)}{suffix}' if self.matches else ('검색 중…' if self.search_timer.isActive() else '결과 없음 · 스캔 문서는 OCR 필요'))

    def next_match(self,direction):
        if not self.matches: return
        self.match_index=(self.match_index+direction)%len(self.matches); self.reveal_match(); self.update_search_status()

    def reveal_match(self):
        index,boxes=self.matches[self.match_index]; self.go(index)
        rect=next((r for i,r in self.canvas.rects if i==index),None)
        if rect and boxes:
            l,b,r,t=boxes[0]; point=QPoint(round(rect.x()+(l+r)*self.zoom/2),round(rect.y()+(self.doc.sizes[index][1]-(b+t)/2)*self.zoom))
            self.scroll.ensureVisible(point.x(),point.y(),50,80)
        self.canvas.update()

    def help(self):
        QMessageBox.information(self,'PDFeather · 도움말','Ctrl+O  파일 열기\nCtrl+P  인쇄\nCtrl+F  찾기\nCtrl+,  설정\nEnter / F3  다음 결과\nShift+Enter / Shift+F3  이전 결과\nEsc  찾기 닫기\nCtrl+휠  포인터 기준 확대·축소\nCtrl++ / Ctrl+−  확대·축소\nCtrl+0  쪽 맞추기\nCtrl+1  너비 맞추기\nPageUp / PageDown  이전·다음 페이지\n\n단일 / 2페이지 보기: 맨 아래에서 휠을 더 내리면 다음 페이지, 맨 위에서 올리면 이전 페이지\n제목 표시줄: 끌어서 이동, 두 번 클릭으로 최대화 / 복원\n창 가장자리와 오른쪽 아래에서 크기 조절')

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
        self.search_timer.stop(); self.search_debounce.stop(); self.matches=[]; self.match_index=-1
        old = self.doc; self.doc = new
        if old: old.close()
        self.current = 0; self.thumbs.blockSignals(True); self.thumbs.clear()
        for i in range(len(new.sizes)):
            item = QListWidgetItem(str(i+1)); item.setSizeHint(QSize(140, 185)); self.thumbs.addItem(item)
        self.thumbs.blockSignals(False)
        self.page.setMaximum(len(new.sizes)); self.total.setText(f' / {len(new.sizes)}  ')
        self.mode.setCurrentIndex(self.prefs.get('default_mode'))
        self.tabs.setCurrentIndex(0)
        self.setWindowTitle(f'{Path(path).name} — PDFeather 1.1.0'); self.canvas.arrange(); self.go(0)
        fit=self.prefs.get('default_fit')
        if fit=='actual': self.set_zoom(1.)
        else: self.fit(fit)
        self.queue_thumbs()
        if self.search_bar.isVisible(): self.begin_search()

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

    def set_zoom(self, zoom, anchor=None, keep_fit=False):
        zoom=max(.1,min(5.,zoom))
        if not keep_fit: self.fit_mode=None
        if abs(zoom-self.zoom)<.0001: self.canvas.arrange(); return
        viewport=self.scroll.viewport()
        anchor=anchor or viewport.rect().center()
        canvas_point=self.canvas.mapFrom(viewport,anchor)
        # Store a point in PDF coordinates, independent of gutters and alignment.
        nearest=next((entry for entry in self.canvas.rects if entry[1].contains(canvas_point)),None) or min(self.canvas.rects,key=lambda entry:abs(entry[1].center().y()-canvas_point.y()),default=None)
        if nearest:
            index,rect=nearest
            px=(canvas_point.x()-rect.x())/self.zoom; py=(canvas_point.y()-rect.y())/self.zoom
        self.suppress_scroll=True
        self.zoom=zoom; self.zoom_box.blockSignals(True); self.zoom_box.setValue(round(zoom*100)); self.zoom_box.blockSignals(False)
        self.canvas.arrange()
        if nearest:
            rect=next((r for i,r in self.canvas.rects if i==index),None)
            if rect:
                self.scroll.horizontalScrollBar().setValue(round(rect.x()+px*zoom-anchor.x()))
                self.scroll.verticalScrollBar().setValue(round(rect.y()+py*zoom-anchor.y()))
        self.suppress_scroll=False; self.scrolled()

    def change_mode(self, *_):
        self.suppress_scroll=True; self.canvas.arrange(); self.suppress_scroll=False
        self.go(self.current)
        if self.fit_mode: self.fit(self.fit_mode)

    def go(self, index):
        if not self.doc or index<0: return
        self.suppress_scroll=True
        self.current=min(index,len(self.doc.sizes)-1)
        if self.mode.currentIndex() in (0,2): self.canvas.arrange()
        else:
            rect=next((r for i,r in self.canvas.rects if i==self.current),None)
            if rect: self.scroll.verticalScrollBar().setValue(round(rect.top()))
        self.suppress_scroll=False
        self.sync_page()
        if self.fit_mode and self.mode.currentIndex() in (0,2): self.fit(self.fit_mode)

    def sync_page(self):
        self.page.blockSignals(True); self.page.setValue(self.current+1); self.page.blockSignals(False)
        self.thumbs.blockSignals(True); self.thumbs.setCurrentRow(self.current); self.thumbs.blockSignals(False)
        self.queue_thumbs()

    def scrolled(self, *_):
        if self.doc and not self.suppress_scroll and self.mode.currentIndex() in (1,3):
            y = self.scroll.verticalScrollBar().value()+2
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
        if self.prefs.get('remember_geometry'): self.prefs.storage.setValue('window_geometry',self.saveGeometry()); self.prefs.storage.sync()
        self.search_timer.stop(); self.search_debounce.stop(); self.thumb_timer.stop()
        QApplication.instance().removeEventFilter(self)
        if self.doc: self.doc.close()
        super().closeEvent(event)


if __name__ == '__main__':
    multiprocessing.freeze_support()
    if sys.platform=='win32': ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('PDFeather.Reader')
    app = QApplication(sys.argv); app.setApplicationName('PDFeather'); app.setApplicationVersion('1.1.0'); app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    window=Window(); window.show()
    if len(sys.argv)>1 and sys.argv[1]=='--smoke-test':
        window.open(sys.argv[2])
        dialog=PrintWindow(window.doc,window); dialog.show()
        result_path=Path(sys.argv[3]); deadline=time.monotonic()+40
        check=QTimer(); check.setInterval(100)
        def smoke_check():
            pix=dialog.preview_label.pixmap()
            if pix and not pix.isNull():
                result_path.write_text('ok'); check.stop(); dialog.close(); window.close(); app.exit(0)
            elif time.monotonic()>deadline:
                result_path.write_text('failed: '+dialog.error.text()); check.stop(); dialog.close(); window.close(); app.exit(1)
        check.timeout.connect(smoke_check); check.start()
    elif len(sys.argv)>1: window.open(sys.argv[1])
    sys.exit(app.exec())
