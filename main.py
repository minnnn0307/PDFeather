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
from PySide6.QtCore import Qt, QRectF, QSize, QTimer, QPoint, QPointF, QEvent, QUrl
from PySide6.QtGui import QImage, QFont, QFontMetrics, QCursor, QPainter, QColor, QIcon, QPixmap, QKeySequence, QShortcut, QPageLayout, QPageSize, QDesktopServices
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QScrollArea,
    QPushButton, QComboBox, QSpinBox, QLabel, QFileDialog, QMessageBox, QSplitter,
    QListWidget, QListWidgetItem, QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QInputDialog, QFrame, QProgressBar, QLayout, QSizePolicy, QBoxLayout, QDoubleSpinBox, QGridLayout, QToolButton, QTabBar, QButtonGroup, QStackedWidget)
from layout import parse_pages, grid, placement, print_cells
from widgets import TitleBar, ThumbnailDelegate, tool, set_theme, icon, CategorySections, ViewModePicker
from preferences import Preferences, SettingsPanel
from popups import PopupSheet, resize_edges
from window_frame import WindowFrame
from branding import application_icon, logo_pixmap
from themes import PALETTES, stylesheet, apply_palette
from rendering import visible_tiles
from selection import TextSelection
from capture import CaptureCollection,snapshot
from tabs import DocumentTab
from interaction import CanvasInteraction
from app_meta import NAME,VERSION
from updates import UpdateChecker
from update_install import InstallerDownload,launch_installer
from instance import SingleInstance
from zoom_render import ZoomRenderer


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
        self.cache_limit=64*1024*1024; self.pixel_limit=16_000_000

    def image(self, index, scale, cached=True):
        # Bound each bitmap to 16 megapixels, and total screen cache to 64 MiB.
        w, h = self.sizes[index]
        scale = min(scale, math.sqrt(self.pixel_limit / (w*h)))
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
            while self.cache_bytes > self.cache_limit and self.cache:
                _, old = self.cache.popitem(last=False)
                self.cache_bytes -= old.sizeInBytes()
        return image

    def remember(self,key,image):
        if key in self.cache:self.cache_bytes-=self.cache.pop(key).sizeInBytes()
        self.cache[key]=image; self.cache_bytes+=image.sizeInBytes()
        while self.cache_bytes>self.cache_limit and self.cache:
            _,old=self.cache.popitem(last=False); self.cache_bytes-=old.sizeInBytes()
        return image

    def tile(self,index,full_width,full_height,x,y,width,height):
        key=('tile',index,full_width,full_height,x,y,width,height)
        if key in self.cache:
            self.cache.move_to_end(key); return self.cache[key]
        if width>768 or height>768 or min(width,height)<1: raise ValueError('잘못된 타일 크기입니다.')
        page=self.pdf[index]
        try:
            # Guard pixels keep glyph rasterization and antialiasing consistent at tile edges.
            guard=64
            left=max(0,x-guard); top=max(0,y-guard)
            render_width=min(full_width,x+width+guard)-left
            render_height=min(full_height,y+height+guard)-top
            bitmap=pdfium.PdfBitmap.new_native(render_width,render_height,format=pdfium.raw.FPDFBitmap_BGR,rev_byteorder=True)
            try:
                bitmap.fill_rect((255,255,255,255),0,0,render_width,render_height)
                pdfium.raw.FPDF_RenderPageBitmap(bitmap,page,-left,-top,full_width,full_height,0,pdfium.raw.FPDF_ANNOT|pdfium.raw.FPDF_REVERSE_BYTE_ORDER)
                image=QImage(bitmap.buffer,render_width,render_height,bitmap.stride,QImage.Format.Format_RGB888).copy(x-left,y-top,width,height)
            finally: bitmap.close()
        finally: page.close()
        return self.remember(key,image)

    def close(self):
        self.cache.clear()
        self.pdf.close()


class Canvas(CanvasInteraction,QWidget):
    def __init__(self, window):
        super().__init__()
        self.reader = window
        self.rects = []
        self.init_interactions()
        self.zoom_preview=[];self.async_zoom=False;self.async_failed=False
        self.zoom_idle=QTimer(self);self.zoom_idle.setSingleShot(True);self.zoom_idle.setInterval(110);self.zoom_idle.timeout.connect(self.zoom_settled)
        self.zoom_renderer=ZoomRenderer(self);self.zoom_renderer.ready.connect(self.zoom_ready);self.zoom_renderer.failed.connect(self.zoom_error)

    # PySide requires virtual event overrides on the concrete QObject subclass.
    def mousePressEvent(self,event): CanvasInteraction.mousePressEvent(self,event)
    def mouseMoveEvent(self,event): CanvasInteraction.mouseMoveEvent(self,event)
    def mouseReleaseEvent(self,event): CanvasInteraction.mouseReleaseEvent(self,event)
    def keyPressEvent(self,event): CanvasInteraction.keyPressEvent(self,event)
    def contextMenuEvent(self,event): CanvasInteraction.contextMenuEvent(self,event)

    def reset_zoom_rendering(self):
        self.zoom_idle.stop();self.zoom_renderer.close();self.zoom_preview=[];self.async_zoom=False;self.async_failed=False

    def zoom_ready(self,key,image):
        if self.reader.doc:self.reader.doc.remember(key,image)
        self.update()
        if not self.zoom_renderer.requests:
            self.zoom_preview=[];self.reader.queue_thumbs()

    def zoom_error(self,message):
        self.zoom_renderer.close();self.async_failed=True;self.async_zoom=False;self.update()

    def zoom_settled(self):
        self.async_zoom=not self.reader.prefs.get('optimization') and not self.async_failed
        if not self.async_zoom:self.zoom_preview=[]
        self.update();self.reader.queue_thumbs()

    def begin_wheel_zoom(self):
        if not self.zoom_idle.isActive():
            self.zoom_preview=[];budget=0
            for key,image in list(self.reader.doc.cache.items()):
                if isinstance(key,tuple) and key[0]=='tile':
                    _,index,fw,fh,x,y,width,height=key
                    rect=next((r for i,r in self.rects if i==index),None)
                    if rect is None or fw!=math.ceil(rect.width()*self.devicePixelRatioF()) or fh!=math.ceil(rect.height()*self.devicePixelRatioF()):continue
                    target=QRectF(rect.x()+x/fw*rect.width(),rect.y()+y/fh*rect.height(),width/fw*rect.width(),height/fh*rect.height())
                    viewport=QRectF(self.mapFrom(self.reader.scroll.viewport(),QPoint()),self.reader.scroll.viewport().size())
                    if not target.intersects(viewport):continue
                    normalized=QRectF(x/fw,y/fh,width/fw,height/fh)
                elif isinstance(key,tuple) and isinstance(key[0],int):index=key[0];normalized=QRectF(0,0,1,1)
                else:continue
                preview=image.scaled(384,384,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.FastTransformation)
                budget+=preview.sizeInBytes()
                if budget>8*1024*1024:break
                self.zoom_preview.append((index,normalized,preview))
        self.zoom_renderer.invalidate();self.async_zoom=not self.reader.prefs.get('optimization') and not self.async_failed
        self.zoom_idle.start();self.reader.thumb_timer.stop()

    def paint_zoom_page(self,painter,index,rect):
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform,not self.zoom_idle.isActive())
        item=self.reader.thumbs.item(index)
        if item is not None and not item.icon().isNull():
            thumb=item.icon().pixmap(130,185);painter.drawPixmap(rect,thumb,QRectF(thumb.rect()))
        for page,normalized,image in self.zoom_preview:
            if page==index:
                painter.drawImage(QRectF(rect.x()+normalized.x()*rect.width(),rect.y()+normalized.y()*rect.height(),normalized.width()*rect.width(),normalized.height()*rect.height()),image)
        if self.zoom_idle.isActive():return
        w=self.reader;requests=[]
        viewport=QRectF(self.mapFrom(w.scroll.viewport(),QPoint()),w.scroll.viewport().size())
        if w.prefs.get('render_mode')=='tiles':
            for tile,target in visible_tiles(rect,viewport,self.devicePixelRatioF()):
                key=('tile',index,*tile)
                if key in w.doc.cache:
                    w.doc.cache.move_to_end(key);painter.drawImage(target,w.doc.cache[key])
                else:requests.append((key,(index,*tile)))
        else:
            scale=min(w.zoom*self.devicePixelRatioF(),math.sqrt(w.doc.pixel_limit/(w.doc.sizes[index][0]*w.doc.sizes[index][1])))
            key=(index,round(scale,3))
            if key in w.doc.cache:painter.drawImage(rect,w.doc.cache[key])
            else:requests.append((key,(index,scale)))
        self.zoom_requests.extend(requests)

    def arrange(self):
        w = self.reader
        self.rects = []
        if not w.doc:
            self.resize(w.scroll.viewport().size())
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
        y=0. if continuous and len(w.doc.sizes)>1 else max(0.,(canvas_height-content_height)/2)
        for row in rows:
            x=(width-sum(v[1] for v in row)-(len(row)-1))/2
            for i,pw,ph in row:
                self.rects.append((i,QRectF(x,y,pw,ph))); x+=pw+1
            y+=max(v[2] for v in row)+(1 if continuous else 0)
        self.resize(max(1,math.ceil(width)),max(w.scroll.viewport().height(),math.ceil(y)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor(self.reader.theme['canvas']))
        w = self.reader
        if not w.doc:
            key=(w.theme_name,self.devicePixelRatioF())
            if getattr(self,'welcome_key',None)!=key:
                dpr=key[1]; image=QPixmap(round(400*dpr),round(210*dpr));image.setDevicePixelRatio(dpr);image.fill(Qt.GlobalColor.transparent)
                ink=QPainter(image);ink.setRenderHint(QPainter.RenderHint.Antialiasing)
                font=QFont('Segoe UI',28,QFont.Weight.DemiBold);ink.setFont(font)
                width=82+QFontMetrics(font).horizontalAdvance('PDFeather');x=(400-width)/2
                ink.drawPixmap(round(x),0,logo_pixmap(64,w.theme_name=='dark',dpr))
                ink.setPen(QColor(w.theme['text']));ink.drawText(QRectF(x+82,0,width-82,64),Qt.AlignmentFlag.AlignVCenter,'PDFeather')
                ink.setFont(QFont('Segoe UI',11));ink.setPen(QColor(w.theme['muted']))
                ink.drawText(QRectF(8,84,384,48),Qt.AlignmentFlag.AlignCenter|Qt.TextFlag.TextWordWrap,'PDF 파일을 열거나 이 창으로 끌어 놓으세요')
                ink.setFont(QFont('Segoe UI',10));ink.drawText(QRectF(0,137,400,24),Qt.AlignmentFlag.AlignCenter,'Ctrl+O · 파일 열기');ink.end()
                self.welcome_key=key;self.welcome_image=image
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawPixmap(QRectF((self.width()-400)/2,(self.height()-180)/2,400,210),self.welcome_image,QRectF(self.welcome_image.rect()))
            return
        try:
            self.zoom_requests=[]
            for i, rect in self.rects:
                if rect.intersects(QRectF(event.rect())):
                    painter.fillRect(rect, Qt.GlobalColor.white)
                    if self.zoom_idle.isActive() or self.async_zoom:
                        self.paint_zoom_page(painter,i,rect)
                    elif w.prefs.get('render_mode')=='tiles':
                        # Only visible physical-pixel tiles are rendered; DPR is part of the cache key.
                        viewport_rect=QRectF(self.mapFrom(w.scroll.viewport(),QPoint(0,0)).x(),self.mapFrom(w.scroll.viewport(),QPoint(0,0)).y(),w.scroll.viewport().width(),w.scroll.viewport().height())
                        visible=QRectF(event.rect()).intersected(viewport_rect)
                        for tile,target in visible_tiles(rect,visible,min(1.,self.devicePixelRatioF()) if w.prefs.get('optimization') else self.devicePixelRatioF()):
                            painter.drawImage(target,w.doc.tile(i,*tile))
                    else:
                        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                        painter.drawImage(rect,w.doc.image(i,w.zoom*self.devicePixelRatioF()))
                    self.paint_selection(painter,i,rect)
                    if w.mode.currentIndex() in (1,3):
                        painter.setPen(QColor('#9ca3af'))
                        painter.drawLine(QPointF(rect.left(),rect.bottom()),QPointF(rect.right(),rect.bottom()))
                    for match_no,(page_no,boxes) in enumerate(w.matches):
                        if page_no!=i: continue
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.setBrush(QColor(255,151,45,145) if match_no==w.match_index else QColor(255,220,40,100))
                        for l,b,r,t in boxes:
                            painter.drawRect(QRectF(rect.x()+l*w.zoom,rect.y()+(w.doc.sizes[i][1]-t)*w.zoom,(r-l)*w.zoom,(t-b)*w.zoom))
            if self.async_zoom and not self.zoom_idle.isActive():self.zoom_renderer.offer(w.doc,self.zoom_requests)
            self.paint_drag(painter)
        except Exception as exc:
            painter.drawText(event.rect(), Qt.AlignmentFlag.AlignCenter, f'렌더링 오류: {exc}')


class PrintWindow(PopupSheet):
    def __init__(self, doc, parent):
        super().__init__(parent,'인쇄',QSize(1060,720))
        self.doc=doc; self.process=None; self.connection=None; self.kind=None
        self.temp=tempfile.TemporaryDirectory(prefix='pdfeather-print-')
        self.setWindowTitle('PDFeather · 인쇄')
        self.pages=QLineEdit(); self.pages.setPlaceholderText('전체 (예: 1-3,5)')
        self.orientation=QComboBox(); self.orientation.addItems(['세로','가로'])
        self.duplex=QComboBox(); self.duplex.addItems(['단면','양면 · 긴 쪽 넘김','양면 · 짧은 쪽 넘김'])
        self.nup=QComboBox(); self.nup.addItems(['1','2','4','6','9','16'])
        self.scale_mode=QComboBox(); self.scale_mode.addItems(['용지에 맞춤','실제 크기','사용자 맞춤'])
        self.scale=QSpinBox(); self.scale.setRange(10,400); self.scale.setValue(100); self.scale.setSuffix('%'); self.scale.setEnabled(False); self.custom_percent=100
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
        self.settings_widget=QWidget(); side=QVBoxLayout(self.settings_widget); side.setContentsMargins(16,18,16,16); side.setSpacing(12)
        title=QLabel('인쇄 옵션'); title.setObjectName('cardHeading'); side.addWidget(title)
        choices=QWidget(); choices.setObjectName('printCategories'); choice_layout=QGridLayout(choices); choice_layout.setContentsMargins(0,0,0,0); choice_layout.setSpacing(6)
        self.sections=QStackedWidget(); category_group=QButtonGroup(self); category_group.setExclusive(True)
        for index,label in enumerate(['프린터 · 범위','용지 · 배치','크기 · 배율','여백 · 간격']):
            button=QPushButton(label); button.setObjectName('categoryChip'); button.setCheckable(True); button.setChecked(index==0); category_group.addButton(button,index); choice_layout.addWidget(button,index//2,index%2)
        category_group.idClicked.connect(self.sections.setCurrentIndex); side.addWidget(choices); side.addWidget(self.sections,1)
        def section(title,rows):
            page=QWidget(); page.setObjectName('printSection'); layout=QVBoxLayout(page); layout.setContentsMargins(12,14,12,14); layout.setSpacing(12)
            form=QFormLayout(); form.setVerticalSpacing(12)
            for label,control in rows: form.addRow(label,control)
            layout.addLayout(form); layout.addStretch(); self.sections.addWidget(page)
            return form
        section('프린터 및 범위',[('프린터',self.devices),('페이지',self.pages),('매수',self.copies),('양면',self.duplex)])
        section('용지 및 배치',[('용지',self.paper),('방향',self.orientation),('한 면당 페이지',self.nup)])
        scale_form=section('크기 및 배율',[('크기 조정',self.scale_mode),('배율',self.scale)])
        hint=QLabel('용지에 맞춘 크기가 100%입니다.\n사용자 맞춤에서만 배율을 변경할 수 있습니다.\n실제 크기는 PDF 원본의 물리적 크기를 사용합니다.'); hint.setWordWrap(True); hint.setObjectName('mutedText'); scale_form.addRow(hint)
        margin_form=section('여백 및 간격',[(label,self.margins[key]) for key,label in [('left','왼쪽'),('right','오른쪽'),('top','위'),('bottom','아래')]]+[('모아찍기 간격',self.gap)])
        hint=QLabel('점선은 출력 영역 안내이며 인쇄되지 않습니다.\n0 mm 무테 출력은 프린터 지원이 필요합니다.'); hint.setWordWrap(True); hint.setObjectName('mutedText'); margin_form.addRow(hint)
        self.sections.setCurrentIndex(0)
        self.submit_button=QPushButton('인쇄'); self.submit_button.setObjectName('primaryButton'); self.submit_button.clicked.connect(self.submit)
        retry=QPushButton('프린터 다시 조회'); retry.clicked.connect(lambda:self.start_job('devices',{}) if self.kind!='print' else None)
        self.cancel_button=QPushButton('미리보기 중단'); self.cancel_button.clicked.connect(self.cancel_job)
        actions=QHBoxLayout(); actions.addWidget(retry); actions.addWidget(self.cancel_button); side.addLayout(actions)
        side.addWidget(self.state); side.addWidget(self.error); side.addWidget(self.submit_button)
        self.preview_label=QLabel('미리보기 준비 중…'); self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_area=QScrollArea(); self.preview_area.setWidgetResizable(True); self.preview_area.setWidget(self.preview_label)
        preview_box=QWidget(); preview_layout=QVBoxLayout(preview_box); preview_layout.setContentsMargins(0,0,0,0)
        nav=QHBoxLayout(); nav.addStretch(); nav.addWidget(tool('prev','이전 용지',lambda:self.sheet.setValue(self.sheet.value()-1))); nav.addWidget(self.sheet); nav.addWidget(self.sheets); nav.addWidget(tool('next','다음 용지',lambda:self.sheet.setValue(self.sheet.value()+1))); nav.addStretch()
        preview_layout.addLayout(nav); preview_layout.addWidget(self.preview_area)
        self.setup_content=QWidget(); self.body.addWidget(self.setup_content,1)
        root=QHBoxLayout(self.setup_content); root.setContentsMargins(0,0,0,0); root.setSpacing(12); self.settings_widget.setFixedWidth(310); self.options_scroll=QScrollArea(); self.options_scroll.setObjectName('settingsScroll'); self.options_scroll.setWidgetResizable(True); self.options_scroll.setWidget(self.settings_widget); self.options_scroll.setMinimumWidth(330); root.addWidget(self.options_scroll,0); root.addWidget(preview_box,1); self.preview_box=preview_box
        self.progress_content=QWidget(); self.progress_content.hide(); self.body.addWidget(self.progress_content,1)
        progress=QVBoxLayout(self.progress_content); progress.setContentsMargins(16,12,16,12); progress.setSpacing(18)
        heading=QLabel('프린터로 보내는 중'); heading.setObjectName('sectionTitle'); progress.addWidget(heading)
        self.progress_detail=QLabel('프린터에 연결하고 있습니다…'); self.progress_detail.setWordWrap(True); self.progress_detail.setObjectName('mutedText'); progress.addWidget(self.progress_detail)
        self.progress_bar=QProgressBar(); self.progress_bar.setRange(0,0); self.progress_bar.setTextVisible(False); self.progress_bar.setFixedHeight(6); progress.addWidget(self.progress_bar)
        note=QLabel('데이터 전송이 끝나면 이 창은 자동으로 닫힙니다.'); note.setObjectName('mutedText'); note.setWordWrap(True); progress.addWidget(note)
        cancel=QPushButton('전송 중단'); cancel.clicked.connect(self.cancel_job); progress.addWidget(cancel,0,Qt.AlignmentFlag.AlignRight)
        self.timer=QTimer(self); self.timer.setSingleShot(True); self.timer.setInterval(300); self.timer.timeout.connect(self.refresh)
        self.poll_timer=QTimer(self); self.poll_timer.setInterval(70); self.poll_timer.timeout.connect(self.poll); self.poll_timer.start()
        for box in [self.orientation,self.duplex,self.nup,self.paper]: box.currentIndexChanged.connect(self.schedule)
        for control in [*self.margins.values(),self.gap]: control.valueChanged.connect(self.schedule)
        self.pages.textChanged.connect(self.schedule); self.scale.valueChanged.connect(self.scale_edited); self.scale_mode.currentIndexChanged.connect(self.scale_changed); self.sheet.valueChanged.connect(self.schedule)
        self.start_job('devices',{})

    def place(self):
        if hasattr(self,'preview_box'):
            self.preview_box.setVisible(self.owner.width()>=800)
            self.settings_widget.setFixedWidth(310 if self.owner.width()>=800 else max(280,min(450,self.owner.width()-100)))
        super().place()

    def settings(self):
        selected=parse_pages(self.pages.text(),len(self.doc.sizes))
        count=math.ceil(len(selected)/int(self.nup.currentText()))
        self.sheet.blockSignals(True); self.sheet.setMaximum(count); self.sheet.blockSignals(False); self.sheets.setText(f'/ {count} 면')
        margins=[self.margins[key].value() for key in ('left','top','right','bottom')]
        size=QPageSize(getattr(QPageSize.PageSizeId,self.paper.currentText())).size(QPageSize.Unit.Millimeter)
        page_mm=(size.height(),size.width()) if self.orientation.currentIndex() else (size.width(),size.height())
        print_cells(page_mm,margins,int(self.nup.currentText()),self.gap.value(),72)
        return dict(margins=margins,gap=self.gap.value(),path=self.doc.path,password=self.doc.password,selected=selected,nup=int(self.nup.currentText()),
            scale_basis='actual' if self.scale_mode.currentIndex()==1 else 'fit',percent=self.scale.value() if self.scale_mode.currentIndex()==2 else 100,
            paper=self.paper.currentText(),landscape=bool(self.orientation.currentIndex()),duplex=self.duplex.currentIndex(),
            copies=self.copies.value(),device=self.devices.currentText(),sheet=self.sheet.value()-1)

    def scale_edited(self,value):
        if self.scale_mode.currentIndex()==2: self.custom_percent=value
        self.schedule()

    def scale_changed(self,*_):
        self.scale.blockSignals(True); self.scale.setValue(self.custom_percent if self.scale_mode.currentIndex()==2 else 100); self.scale.blockSignals(False)
        self.scale.setEnabled(self.kind!='print' and self.scale_mode.currentIndex()==2); self.schedule()

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
        self.scale.setEnabled(not busy and self.scale_mode.currentIndex()==2)

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
                    pix=QPixmap(message[1]); self.preview_label.setPixmap(pix.scaled(QSize(max(200,self.preview_area.viewport().width()-40),max(200,self.preview_area.viewport().height()-24)),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
                    self.state.setText('미리보기 · 선택한 용지 1면'); self.stop_job(); return
                if kind=='progress':
                    self.progress_detail.setText(f'인쇄 데이터 전송 중 · {message[1]} / {message[2]} 면'); self.progress_bar.setRange(0,message[2]); self.progress_bar.setValue(message[1])
                if kind=='done':
                    self.accept(); return
                if kind=='error':
                    self.print_error(message[1]); return
        except (EOFError,OSError):
            self.print_error('인쇄 작업이 종료되었습니다. 다시 시도하세요.'); return
        if self.process and not self.process.is_alive():
            self.print_error('인쇄 작업이 비정상 종료되었습니다.')
        elif self.kind=='devices' and time.monotonic()-self.started>12:
            self.stop_job(); self.state.setText('프린터 조회 시간이 초과되었습니다. 프린터 연결을 확인하세요.'); self.refresh()

    def submit(self):
        try:
            settings=self.settings()
            if not settings['device']: raise ValueError('사용 가능한 프린터가 없습니다.')
            self.timer.stop(); self.start_job('print',settings)
            self.setup_content.hide(); self.progress_content.show(); self.close_button.hide(); self.progress_bar.setRange(0,0)
            self.progress_detail.setText('프린터에 연결하고 있습니다…'); self.preferred=QSize(460,300); self.place()
        except Exception as exc: self.print_error(str(exc))

    def print_error(self,message):
        self.stop_job(); self.progress_content.hide(); self.setup_content.show(); self.close_button.show()
        self.preferred=QSize(1060,720); self.place(); self.error.setText(message)

    def reject(self):
        if self.kind=='print': return
        super().reject()

    def cancel_job(self):
        printing=self.kind=='print'; self.stop_job(); self.timer.stop(); self.settings_widget.setEnabled(True); self.submit_button.setEnabled(True)
        if printing: self.print_error('전송을 중단했습니다. 이미 전송된 작업은 Windows 인쇄 대기열에서 취소하세요.')
        self.state.setText('중단했습니다. 이미 전송된 작업은 Windows 인쇄 대기열에서 취소하세요.' if printing else '작업을 중단했습니다.')

    def done(self,result):
        self.timer.stop(); self.poll_timer.stop(); self.stop_job(); self.temp.cleanup(); super().done(result)


class Window(QMainWindow):
    def __init__(self, preferences=None, enable_updates=True):
        super().__init__()
        self.prefs=preferences if preferences is not None else Preferences()
        self.enable_update_checks=enable_updates and not bool(QApplication.instance().property('offlineTests')); self.update_info=None; self.update_manual=False
        self.theme_name=self.prefs.get('theme'); self.theme=PALETTES[self.theme_name]
        set_theme(self.theme_name)
        self.external_pending=[]; self.external_draining=False; self.external_activate=False
        self.external_timer=QTimer(self); self.external_timer.setSingleShot(True); self.external_timer.timeout.connect(self.drain_external_files)
        self.resize_cursor_active=False; self.thumb_lru=OrderedDict()
        self.active_tab=None; self.restoring_tab=False; self.selection=None; self.selection_tool='pointer'; self.captures=CaptureCollection()
        self.doc=None; self.current=0; self.zoom=1.; self.fit_mode=None; self.last_flip=0
        self.matches=[]; self.match_index=-1; self.search_page=0; self.search_query=''; self.suppress_scroll=False
        self.setWindowFlags(Qt.WindowType.Window|Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle('PDFeather'); self.resize(1200,850); self.setMinimumSize(540,360); self.setAcceptDrops(True)
        shell=QWidget(); shell.setObjectName('shell'); root=QVBoxLayout(shell); root.setSpacing(0); root.setContentsMargins(0,0,0,0)
        self.titlebar=TitleBar(self); root.addWidget(self.titlebar)
        self.update_bar=QWidget(); self.update_bar.setObjectName('captureBar'); update_row=QHBoxLayout(self.update_bar); update_row.setContentsMargins(12,6,12,6)
        self.update_label=QLabel(); update_row.addWidget(self.update_label,1)
        release=QPushButton('업데이트 보기'); release.clicked.connect(self.open_update_page); update_row.addWidget(release)
        dismiss=QPushButton('닫기'); dismiss.clicked.connect(self.dismiss_update); update_row.addWidget(dismiss); self.update_bar.hide(); root.addWidget(self.update_bar)
        self.file_tabs=self.titlebar.tabs
        self.file_tabs.currentChanged.connect(self.activate_tab); self.file_tabs.tabCloseRequested.connect(self.close_tab)
        toolbar=QWidget(); toolbar.setObjectName('toolbar'); bar=QHBoxLayout(toolbar); bar.setContentsMargins(10,7,12,7); bar.setSpacing(6)
        for name,tip,callback in [('sidebar','썸네일 표시 / 숨기기',self.toggle_sidebar),('open','파일 열기 · Ctrl+O',self.choose),('print','인쇄 · Ctrl+P',self.print_document),('search','찾기 · Ctrl+F',self.show_search)]: bar.addWidget(tool(name,tip,callback))
        bar.addSpacing(12)
        self.selection_buttons={}; self.selection_group=QButtonGroup(self); self.selection_group.setExclusive(True)
        for name,label,key in [('pointer','일반 포인터','pointer'),('hand','손 도구 · 드래그하여 화면 이동','hand'),('text','텍스트 선택 · 드래그 후 Ctrl+C','text'),('capture','영역 캡처 · 드래그하면 이미지 복사','capture'),('multi','다중캡처 · 선택한 영역들을 아래로 연결','multi')]:
            button=tool(name,label,lambda checked=False,value=key:self.set_selection_tool(value)); button.setCheckable(True); self.selection_group.addButton(button); self.selection_buttons[key]=button; bar.addWidget(button)
        self.selection_buttons['pointer'].setChecked(True)
        self.mode=ViewModePicker(); self.mode.addItems(['단일','단일 스크롤','2페이지','2페이지 스크롤']); self.mode.setCurrentIndex(self.prefs.get('default_mode')); self.mode.currentIndexChanged.connect(self.change_mode)
        bar.addStretch(); bar.addWidget(tool('info','PDF 정보',self.info)); bar.addWidget(tool('settings','설정',self.show_settings))
        root.addWidget(toolbar)
        self.capture_bar=QWidget(); self.capture_bar.setObjectName('captureBar'); capture_row=QHBoxLayout(self.capture_bar); capture_row.setContentsMargins(12,5,12,5); capture_row.setSpacing(8)
        self.capture_status=QLabel(''); capture_row.addWidget(self.capture_status,1)
        self.capture_preview=QPushButton('미리보기'); self.capture_preview.clicked.connect(self.preview_captures); capture_row.addWidget(self.capture_preview)
        self.capture_undo=QPushButton('마지막 취소'); self.capture_undo.clicked.connect(self.undo_capture); capture_row.addWidget(self.capture_undo)
        self.capture_clear=QPushButton('초기화'); self.capture_clear.clicked.connect(self.clear_captures); capture_row.addWidget(self.capture_clear)
        self.capture_copy=QPushButton('이어붙여 복사'); self.capture_copy.setObjectName('primaryButton'); self.capture_copy.clicked.connect(self.copy_captures); capture_row.addWidget(self.capture_copy)
        root.addWidget(self.capture_bar); self.capture_bar.hide()
        self.notice=QLabel(self); self.notice.setObjectName('noticeText'); self.notice.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents); self.notice.hide()
        self.notice_timer=QTimer(self); self.notice_timer.setSingleShot(True); self.notice_timer.timeout.connect(self.notice.hide)
        self.search_bar=QWidget(); search_layout=QHBoxLayout(self.search_bar); search_layout.setContentsMargins(12,5,12,5)
        self.search_input=QLineEdit(); self.search_input.setPlaceholderText('문서에서 찾기 · Enter 다음 / Shift+Enter 이전')
        self.search_status=QLabel(''); search_layout.addWidget(self.search_input,1); search_layout.addWidget(self.search_status)
        search_layout.addWidget(tool('prev','이전 검색 결과',lambda:self.next_match(-1))); search_layout.addWidget(tool('next','다음 검색 결과',lambda:self.next_match(1))); search_layout.addWidget(tool('close','찾기 닫기 · Esc',self.hide_search))
        self.search_bar.hide(); root.addWidget(self.search_bar)
        self.search_debounce=QTimer(self); self.search_debounce.setSingleShot(True); self.search_debounce.setInterval(250); self.search_debounce.timeout.connect(self.begin_search)
        self.search_timer=QTimer(self); self.search_timer.setInterval(1); self.search_timer.timeout.connect(self.search_step)
        self.search_input.textChanged.connect(lambda *_:self.search_debounce.start()); self.search_input.returnPressed.connect(lambda:self.next_match(-1 if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier else 1))
        self.thumbs=QListWidget(); self.thumbs.setIconSize(QSize(130,165)); self.thumbs.setMinimumWidth(140); self.thumbs.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel); self.thumbs.setItemDelegate(ThumbnailDelegate(self.thumbs)); self.thumbs.currentRowChanged.connect(self.go)
        self.scroll=QScrollArea(); self.scroll.setFrameShape(QFrame.Shape.NoFrame); self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas=Canvas(self); self.scroll.setWidget(self.canvas); self.notice.setParent(self.scroll.viewport())
        self.split=QSplitter(); self.split.setHandleWidth(1); self.split.addWidget(self.thumbs); self.split.addWidget(self.scroll); self.split.setSizes([164,1036]); root.addWidget(self.split,1)
        footer=QWidget(); footer.setObjectName('footer'); bottom=QHBoxLayout(footer); bottom.setContentsMargins(10,4,7,4)
        left=QWidget(); left.setMinimumWidth(0); bottom.addWidget(left,1); self.footer_spacer=left; self.footer_layout=bottom
        nav=QHBoxLayout(); nav.setSpacing(4)
        nav.addWidget(tool('prev','이전 페이지 · PageUp',lambda:self.turn(-1)))
        self.page=QSpinBox(); self.page.setRange(1,1); self.page.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons); self.page.setAlignment(Qt.AlignmentFlag.AlignCenter); self.page.setFixedWidth(58); self.page.valueChanged.connect(lambda v:self.go(v-1)); nav.addWidget(self.page)
        self.total=QLabel('/ 0'); nav.addWidget(self.total); nav.addWidget(tool('next','다음 페이지 · PageDown',lambda:self.turn(1)))
        nav_widget=QWidget(); nav_widget.setLayout(nav); bottom.addWidget(nav_widget,0,Qt.AlignmentFlag.AlignCenter)
        right=QHBoxLayout(); right.setSpacing(2); right.addStretch(); right.addWidget(self.mode); right.addSpacing(8); right.addWidget(tool('minus','축소 · Ctrl+−',lambda:self.set_zoom(self.zoom/1.15)))
        self.zoom_box=QSpinBox(); self.zoom_box.setRange(10,1000); self.zoom_box.setValue(100); self.zoom_box.setSuffix('%'); self.zoom_box.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons); self.zoom_box.setAlignment(Qt.AlignmentFlag.AlignCenter); self.zoom_box.setFixedWidth(66); self.zoom_box.valueChanged.connect(lambda v:self.set_zoom(v/100)); right.addWidget(self.zoom_box)
        right.addWidget(tool('plus','확대 · Ctrl++',lambda:self.set_zoom(self.zoom*1.15))); right.addSpacing(6); right.addWidget(tool('fit','쪽 맞추기 · Ctrl+0',lambda:self.fit('page'))); right.addWidget(tool('width','폭 맞추기 · Ctrl+1',lambda:self.fit('width')))
        rw=QWidget(); rw.setMinimumWidth(0); rw.setLayout(right); right.setContentsMargins(0,0,0,0); bottom.addWidget(rw,1)
        root.addWidget(footer)
        root.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        shell.setMinimumSize(0,0); self.setCentralWidget(shell)
        self.settings_dialog=PopupSheet(self,'설정',QSize(860,660))
        settings_layout=self.settings_dialog.body
        self.settings_panel=SettingsPanel(self.prefs); self.settings_panel.changed.connect(self.preference_changed); settings_layout.addWidget(self.settings_panel)
        actions=QHBoxLayout(); actions.setContentsMargins(18,6,18,12); actions.addStretch(); close=QPushButton('닫기'); close.clicked.connect(self.settings_dialog.close); actions.addWidget(close); settings_layout.addLayout(actions)
        self.thumbs.setVisible(self.prefs.get('show_thumbnails'))
        if self.prefs.get('remember_geometry'):
            geometry=self.prefs.storage.value('window_geometry')
            if geometry is not None: self.restoreGeometry(geometry)
        self.scroll.verticalScrollBar().valueChanged.connect(self.scrolled)
        self.thumbs.verticalScrollBar().valueChanged.connect(self.queue_thumbs)
        self.thumb_timer=QTimer(self); self.thumb_timer.setSingleShot(True); self.thumb_timer.timeout.connect(self.render_thumbs)
        for key,callback in [(QKeySequence.StandardKey.Open,self.choose),(QKeySequence.StandardKey.Print,self.print_document),(QKeySequence.StandardKey.Find,self.show_search),('Escape',self.hide_search),('F1',self.help),('Ctrl+,',self.show_settings),('Ctrl+W',self.close_current_tab),('Ctrl+Tab',lambda:self.cycle_tab(1)),('Ctrl+Shift+Tab',lambda:self.cycle_tab(-1)),('F3',lambda:self.next_match(1)),('Shift+F3',lambda:self.next_match(-1)),('Ctrl+0',lambda:self.fit('page')),('Ctrl+1',lambda:self.fit('width')),('Ctrl+=',lambda:self.set_zoom(self.zoom*1.15)),('Ctrl+-',lambda:self.set_zoom(self.zoom/1.15)),('PgDown',lambda:self.turn(1)),('PgUp',lambda:self.turn(-1))]: QShortcut(QKeySequence(key),self,activated=callback)
        QApplication.instance().installEventFilter(self)
        for widget in [self,*self.findChildren(QWidget)]: widget.setMouseTracking(True)
        self.canvas.arrange()
        self.frame_outline=WindowFrame(self); self.frame_outline.show(); self.frame_outline.sync()
        self.apply_theme(self.theme_name)
        self.update_checker=UpdateChecker(self); self.update_checker.completed.connect(self.on_update_checked); self.update_checker.failed.connect(self.on_update_failed)
        self.settings_panel.check_update_requested.connect(lambda:self.check_updates(True)); self.settings_panel.open_release_requested.connect(self.open_update_page)
        self.update_timer=QTimer(self); self.update_timer.setSingleShot(True); self.update_timer.setInterval(3000); self.update_timer.timeout.connect(lambda:self.check_updates(False))
        self.update_daily_timer=QTimer(self); self.update_daily_timer.setInterval(3600000); self.update_daily_timer.timeout.connect(lambda:self.check_updates(False))
        if self.enable_update_checks: self.update_timer.start(); self.update_daily_timer.start()

    def apply_theme(self,name):
        self.theme_name=name; self.theme=PALETTES[name]; set_theme(name)
        apply_palette(QApplication.instance(),name)
        for button in self.findChildren(QToolButton):
            key=button.property('iconName')
            if key: button.setIcon(icon(key))
        self.titlebar.brand.setPixmap(logo_pixmap(16,name=='dark',self.devicePixelRatioF()))
        self.setWindowIcon(application_icon(name=='dark'))
        QApplication.instance().setWindowIcon(application_icon(name=='dark'))
        self.mode.refresh_icons(); self.canvas.update(); self.thumbs.viewport().update()

    def set_selection_tool(self,name):
        self.canvas.cancel_drag(); self.selection_tool=name
        if self.selection: self.selection.clear()
        self.selection_buttons[name].setChecked(True)
        self.canvas.setCursor({'pointer':Qt.CursorShape.ArrowCursor,'hand':Qt.CursorShape.OpenHandCursor,'text':Qt.CursorShape.IBeamCursor}.get(name,Qt.CursorShape.CrossCursor))
        self.canvas.setFocus(); self.update_capture_bar()
        if name=='capture': self.show_message('영역을 드래그하면 이미지가 클립보드에 복사됩니다.')

    def show_message(self,text):
        self.notice.setText(text); self.notice.adjustSize()
        self.notice.move(max(8,(self.scroll.viewport().width()-self.notice.width())//2),12)
        self.notice.show(); self.notice.raise_(); self.notice_timer.start(3500)

    def update_capture_bar(self):
        count=len(self.captures.items); width,height=self.captures.size
        self.capture_status.setText(f'다중캡처 {count}개 · {width} × {height} px' if count else '다중캡처 · 영역 선택 → 스크롤 → 다시 선택 → 이어붙여 복사')
        for button in [self.capture_preview,self.capture_undo,self.capture_clear,self.capture_copy]: button.setEnabled(bool(count))
        self.capture_bar.setVisible(self.selection_tool=='multi' or bool(count))

    def capture_region(self,region):
        if not self.doc: return
        try:
            image=snapshot(self.doc,self.canvas.rects,region,self.canvas.devicePixelRatioF())
            if self.selection_tool=='multi':
                self.captures.add(image); self.update_capture_bar()
            else:
                QApplication.clipboard().setImage(image); self.show_message('선택한 영역을 이미지로 복사했습니다.')
        except Exception as exc: QMessageBox.warning(self,'캡처',str(exc))

    def undo_capture(self):
        self.captures.undo(); self.update_capture_bar()

    def clear_captures(self):
        self.captures.clear(); self.update_capture_bar()

    def copy_captures(self):
        try:
            image=self.captures.image(); QApplication.clipboard().setImage(image)
            self.show_message(f'{len(self.captures.items)}개 영역을 아래로 이어붙여 복사했습니다.')
        except Exception as exc: QMessageBox.warning(self,'다중캡처',str(exc))

    def preview_captures(self):
        if not self.captures.items: return
        try: image=self.captures.image()
        except Exception as exc: QMessageBox.warning(self,'다중캡처',str(exc)); return
        dialog=QDialog(self); dialog.setWindowTitle('다중캡처 미리보기'); dialog.resize(760,700)
        layout=QVBoxLayout(dialog); width,height=self.captures.size
        layout.addWidget(QLabel(f'{len(self.captures.items)}개 · {width} × {height} px · 캡처한 순서대로 연결'))
        label=QLabel(); label.setAlignment(Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignTop)
        pix=QPixmap.fromImage(image)
        if pix.width()>690: pix=pix.scaledToWidth(690,Qt.TransformationMode.SmoothTransformation)
        label.setPixmap(pix); area=QScrollArea(); area.setWidget(label); area.setWidgetResizable(True); layout.addWidget(area,1)
        actions=QHBoxLayout(); actions.addStretch(); copy=QPushButton('이어붙여 복사'); copy.clicked.connect(self.copy_captures); close=QPushButton('닫기'); close.clicked.connect(dialog.accept); actions.addWidget(copy); actions.addWidget(close); layout.addLayout(actions); dialog.exec()

    def copy_text(self):
        if not self.selection: return
        try:
            text=self.selection.text()
            if text: QApplication.clipboard().setText(text); self.show_message('선택한 텍스트를 복사했습니다.')
        except Exception as exc: QMessageBox.warning(self,'텍스트 복사',str(exc))

    def copy_content(self):
        if self.selection_tool=='multi' and self.captures.items: self.copy_captures()
        else: self.copy_text()

    def check_updates(self,manual=False):
        if not self.enable_update_checks: return
        if not manual:
            if not self.prefs.get('auto_update'): return
            try: last=int(self.prefs.storage.value('updates/last_attempt',0))
            except (ValueError,TypeError): last=0
            if 0<=time.time()-last<86400: return
        if self.update_checker.busy: return
        self.update_manual=manual
        self.prefs.storage.setValue('updates/last_attempt',int(time.time())); self.prefs.storage.sync()
        self.settings_panel.update_button.setEnabled(False); self.settings_panel.update_status.setText('업데이트 확인 중…')
        self.update_checker.check()

    def on_update_checked(self,info):
        self.settings_panel.update_button.setEnabled(True)
        if info is None:
            self.settings_panel.update_status.setText('새로운 공개 업데이트가 없습니다.'); self.settings_panel.release_button.hide(); self.update_bar.hide(); return
        self.update_info=info; self.settings_panel.release_button.show(); self.settings_panel.update_status.setText(f'새 버전 {info.version}을 사용할 수 있습니다.')
        dismissed=self.prefs.storage.value('updates/dismissed_version','')
        if self.update_manual or dismissed!=info.version:
            self.show_update_popup()

    def show_update_popup(self):
        if getattr(self,"closing",False):return
        if QApplication.activeModalWidget() is not None:
            QTimer.singleShot(1000,self.show_update_popup); return
        if getattr(self,'update_popup',None) is not None and self.update_popup.isVisible():return
        if not self.update_info:return
        popup=PopupSheet(self,'PDFeather 업데이트',QSize(480,340));self.update_popup=popup
        label=QLabel(f'새 버전 {self.update_info.version}');label.setObjectName('sectionTitle');popup.body.addWidget(label)
        detail=QLabel('지금 설치하면 PDFeather가 종료된 뒤 업데이트되고 다시 실행됩니다.');detail.setWordWrap(True);popup.body.addWidget(detail)
        bar=QProgressBar();bar.hide();popup.body.addWidget(bar)
        actions=QHBoxLayout();page=QPushButton('배포 페이지');page.clicked.connect(lambda:QDesktopServices.openUrl(QUrl(self.update_info.url)));actions.addWidget(page);later=QPushButton('나중에');later.clicked.connect(self.dismiss_update);actions.addWidget(later)
        install=QPushButton('업데이트 설치');install.setObjectName('primaryButton');actions.addWidget(install);popup.body.addLayout(actions)
        download=InstallerDownload(popup);self.installer_download=download
        def failed(message):
            detail.setText(message);bar.hide();install.setEnabled(True);later.setEnabled(True);popup.close_button.setEnabled(True)
        def ready(path):
            try:launch_installer(path)
            except Exception as exc:failed(str(exc));return
            popup.accept();self.close()
        def begin():
            if self.external_draining:return
            install.setEnabled(False);later.setEnabled(False);popup.close_button.setEnabled(False);bar.show();bar.setRange(0,100);detail.setText('업데이트를 내려받고 검증하고 있습니다…');download.start(self.update_info)
        download.progress.connect(lambda received,total:bar.setValue(round(received*100/total)))
        download.failed.connect(failed);download.completed.connect(ready);install.clicked.connect(begin)
        popup.finished.connect(lambda _:download.cancel() if download.reply else None)
        popup.show()

    def on_update_failed(self,message):
        self.settings_panel.update_button.setEnabled(True); self.settings_panel.update_status.setText(message)
        if self.update_manual: QMessageBox.information(self,'업데이트 확인',message)

    def dismiss_update(self):
        self.update_bar.hide()
        if getattr(self,'update_popup',None):self.update_popup.close()
        if self.update_info:
            self.prefs.storage.setValue('updates/dismissed_version',self.update_info.version); self.prefs.storage.sync()

    def open_update_page(self):
        if self.update_info:self.show_update_popup()

    def show_settings(self):
        self.settings_dialog.show(); self.settings_dialog.raise_(); self.settings_dialog.activateWindow()

    def configure_document(self,doc):
        lean=self.prefs.get('optimization');doc.cache_limit=(8 if lean else 64)*1024*1024;doc.pixel_limit=2_000_000 if lean else 16_000_000
        doc.cache.clear();doc.cache_bytes=0

    def preference_changed(self,key,value):
        if key=='theme': self.apply_theme(value)
        elif key=='auto_update' and hasattr(self,'update_checker'):
            if value and self.enable_update_checks: self.update_timer.start()
            elif not value and not self.update_manual: self.update_checker.cancel(); self.settings_panel.update_button.setEnabled(True)
        elif key=='optimization':
            self.canvas.reset_zoom_rendering()
            for i in range(self.file_tabs.count()): self.configure_document(self.file_tabs.tabData(i).doc)
            self.rebuild_thumbnails();self.queue_thumbs();self.canvas.update()
        elif key=='render_mode':
            if self.doc: self.doc.cache.clear(); self.doc.cache_bytes=0
            self.canvas.update()
        elif key=='show_thumbnails': self.thumbs.setVisible(value); QTimer.singleShot(0,self.refit)
        elif key=='default_mode': self.mode.setCurrentIndex(value)
        elif key=='default_fit' and self.doc:
            if value=='actual': self.set_zoom(1.)
            else: self.fit(value)

    def clear_resize_cursor(self):
        if self.resize_cursor_active:
            QApplication.restoreOverrideCursor(); self.resize_cursor_active=False

    def eventFilter(self,obj,event):
        if event.type() in (QEvent.Type.MouseMove,QEvent.Type.Enter) and isinstance(obj,QWidget):
            edges=Qt.Edge(0)
            if obj.window() is self and not self.isMaximized() and QApplication.activeModalWidget() is None:
                point=self.mapFromGlobal(event.globalPosition().toPoint() if hasattr(event,'globalPosition') else QCursor.pos())
                edges=resize_edges(point,self.size())
            if edges:
                horizontal=bool(edges & (Qt.Edge.LeftEdge|Qt.Edge.RightEdge)); vertical=bool(edges & (Qt.Edge.TopEdge|Qt.Edge.BottomEdge))
                if horizontal and vertical:
                    same=bool(edges & Qt.Edge.LeftEdge)==bool(edges & Qt.Edge.TopEdge)
                    shape=Qt.CursorShape.SizeFDiagCursor if same else Qt.CursorShape.SizeBDiagCursor
                else: shape=Qt.CursorShape.SizeHorCursor if horizontal else Qt.CursorShape.SizeVerCursor
                if self.resize_cursor_active: QApplication.changeOverrideCursor(QCursor(shape))
                else: QApplication.setOverrideCursor(QCursor(shape)); self.resize_cursor_active=True
            else: self.clear_resize_cursor()
        if obj is self and event.type() in (QEvent.Type.Leave,QEvent.Type.WindowDeactivate,QEvent.Type.WindowStateChange): self.clear_resize_cursor()
        if obj is self and event.type()==QEvent.Type.Resize and hasattr(self,'footer_layout'):
            compact=self.width()<850
            self.footer_spacer.setVisible(not compact)
            self.footer_layout.setDirection(QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight)
        if event.type()==QEvent.Type.DevicePixelRatioChange and obj==self:
            self.titlebar.brand.setPixmap(logo_pixmap(16,self.theme_name=='dark',self.devicePixelRatioF())); self.canvas.update()
        if event.type()==QEvent.Type.Resize and obj==self.scroll.viewport():
            if not self.doc:
                self.canvas.resize(event.size()); self.canvas.update()
            else: QTimer.singleShot(0,self.refit)
        if event.type()==QEvent.Type.MouseButtonPress and event.button()==Qt.MouseButton.LeftButton and not self.isMaximized() and isinstance(obj,QWidget) and obj.window()==self:
            pt=self.mapFromGlobal(event.globalPosition().toPoint()); edges=resize_edges(pt,self.size())
            if edges and self.windowHandle() and self.windowHandle().startSystemResize(edges): return True
        if event.type()==QEvent.Type.Wheel and QApplication.activeModalWidget() is None and obj in (self.scroll.viewport(),self.thumbs.viewport()) and not event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta=event.angleDelta().y()
            if delta and (obj is self.thumbs.viewport() or not (self.doc and self.prefs.get('edge_flip') and self.mode.currentIndex() in (0,2))):
                area=self.thumbs if obj is self.thumbs.viewport() else self.scroll
                bar=area.verticalScrollBar(); bar.setValue(bar.value()-round(delta/120*self.prefs.get('scroll_step')))
                event.accept(); return True
        if event.type()==QEvent.Type.Wheel and QApplication.activeModalWidget() is None and obj==self.scroll.viewport():
            delta=event.angleDelta().y() or event.pixelDelta().y()
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                factor=1+self.prefs.get('wheel_step')/100
                if delta: self.set_zoom(self.zoom*(factor if delta>0 else 1/factor),event.position().toPoint(),interactive=True)
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
            if event.angleDelta().y() and not event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                sb=self.scroll.verticalScrollBar(); sb.setValue(sb.value()-round(event.angleDelta().y()/120*self.prefs.get('scroll_step'))); event.accept(); return True
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
        if self.restoring_tab: return
        if self.fit_mode and self.doc: self.fit(self.fit_mode)
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
        self.search_bar.show(); self.search_input.setFocus(); self.search_input.selectAll()

    def hide_search(self):
        self.canvas.cancel_drag()
        if self.selection: self.selection.clear()
        self.search_bar.hide(); self.search_timer.stop(); self.search_debounce.stop(); self.matches=[]; self.match_index=-1; self.canvas.update(); self.canvas.setFocus()

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
        self.settings_panel.categories.setCurrentRow(self.settings_panel.help_index); self.show_settings()

    def receive_external_files(self,paths):
        self.external_pending.extend(paths); self.external_activate=True; self.external_timer.start(0)

    def drain_external_files(self):
        if self.external_draining or QApplication.activeModalWidget() is not None:
            self.external_timer.start(150); return
        if not self.external_activate: return
        self.external_draining=True; self.external_activate=False
        paths=self.external_pending; self.external_pending=[]
        try:
            self.settings_dialog.hide()
            for path in paths: self.open(path)
            if self.isMinimized(): self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
            self.show()
            self.raise_(); self.activateWindow()
            QTimer.singleShot(150,self.activateWindow)
        finally:
            self.external_draining=False
            if self.external_pending or self.external_activate: self.external_timer.start(0)

    def choose(self):
        paths, _ = QFileDialog.getOpenFileNames(self, 'PDF 열기', '', 'PDF (*.pdf)')
        for path in paths: self.open(path)

    def open(self,path):
        path=str(Path(path).resolve())
        for i in range(self.file_tabs.count()):
            state=self.file_tabs.tabData(i)
            if os.path.normcase(str(Path(state.doc.path).resolve()))==os.path.normcase(path):
                self.file_tabs.setCurrentIndex(i); return
        try:
            try: new=Document(path)
            except pdfium.PdfiumError:
                password,ok=QInputDialog.getText(self,'PDF 열기','암호화된 PDF라면 비밀번호를 입력하세요.',QLineEdit.EchoMode.Password)
                if not ok: return
                new=Document(path,password)
        except Exception as exc: QMessageBox.warning(self,'열기 실패',str(exc)); return
        state=DocumentTab(new,TextSelection(new),mode=self.prefs.get('default_mode'),fit_mode=None if self.prefs.get('default_fit')=='actual' else self.prefs.get('default_fit'))
        self.prefs.restore_document(state)
        self.file_tabs.blockSignals(True); index=self.file_tabs.addTab(Path(path).name); self.file_tabs.setTabData(index,state); self.file_tabs.setTabToolTip(index,path); self.file_tabs.setCurrentIndex(index); self.file_tabs.blockSignals(False)
        self.titlebar.sync_tabs(); self.activate_tab(index)

    def save_tab_state(self):
        state=self.active_tab
        if state is None: return
        state.current=self.current; state.zoom=self.zoom; state.fit_mode=self.fit_mode; state.mode=self.mode.currentIndex()
        state.scroll_x=self.scroll.horizontalScrollBar().value(); state.scroll_y=self.scroll.verticalScrollBar().value()
        state.search_query=self.search_query; state.search_input=self.search_input.text(); state.search_visible=not self.search_bar.isHidden(); state.search_page=self.search_page
        state.matches=self.matches; state.match_index=self.match_index

    def rebuild_thumbnails(self):
        self.thumb_lru.clear(); self.thumbs.blockSignals(True); self.thumbs.clear()
        if self.doc:
            for i in range(len(self.doc.sizes)):
                item=QListWidgetItem(str(i+1)); item.setSizeHint(QSize(140,185)); self.thumbs.addItem(item)
        self.thumbs.blockSignals(False)

    def activate_tab(self,index):
        self.canvas.reset_zoom_rendering()
        if index<0: return
        state=self.file_tabs.tabData(index)
        if state is None or state is self.active_tab: return
        self.save_tab_state(); self.canvas.cancel_drag(); self.search_timer.stop(); self.search_debounce.stop(); self.thumb_timer.stop()
        if self.doc: self.doc.cache.clear(); self.doc.cache_bytes=0
        self.restoring_tab=True; self.suppress_scroll=True
        self.active_tab=state; self.doc=state.doc; self.configure_document(self.doc); self.selection=state.selection; self.current=state.current; self.zoom=state.zoom; self.fit_mode=state.fit_mode
        self.mode.blockSignals(True); self.mode.setCurrentIndex(state.mode); self.mode.blockSignals(False)
        self.zoom_box.blockSignals(True); self.zoom_box.setValue(round(self.zoom*100)); self.zoom_box.blockSignals(False)
        self.matches=state.matches; self.match_index=state.match_index; self.search_query=state.search_query; self.search_page=state.search_page
        self.search_input.blockSignals(True); self.search_input.setText(state.search_input); self.search_input.blockSignals(False); self.search_bar.setVisible(state.search_visible)
        self.page.setMaximum(len(self.doc.sizes)); self.total.setText(f' / {len(self.doc.sizes)}  '); self.rebuild_thumbnails()
        self.setWindowTitle(f'{Path(self.doc.path).name} — PDFeather'); self.canvas.arrange(); self.sync_page()
        if self.fit_mode: self.fit(self.fit_mode)
        self.suppress_scroll=False
        def restore():
            if self.active_tab is not state: return
            self.suppress_scroll=True
            if state.initialized:
                self.scroll.horizontalScrollBar().setValue(state.scroll_x); self.scroll.verticalScrollBar().setValue(state.scroll_y)
            else:
                self.go(state.current); state.initialized=True
            self.suppress_scroll=False; self.restoring_tab=False; self.queue_thumbs(); self.canvas.setFocus()
            if state.search_visible and state.search_query and self.search_page<len(self.doc.sizes): self.search_timer.start()
            self.update_search_status() if state.search_query else self.search_status.clear()
        QTimer.singleShot(0,restore)

    def close_current_tab(self):
        if self.file_tabs.currentIndex()>=0: self.close_tab(self.file_tabs.currentIndex())

    def close_tab(self,index):
        self.canvas.reset_zoom_rendering()
        state=self.file_tabs.tabData(index)
        if state is None: return
        active=state is self.active_tab
        if active: self.save_tab_state()
        self.prefs.save_document(state)
        self.file_tabs.blockSignals(True); self.file_tabs.removeTab(index); self.file_tabs.blockSignals(False)
        if active:
            self.active_tab=None; self.doc=None; self.selection=None; self.canvas.cancel_drag(); self.search_timer.stop(); self.search_debounce.stop(); self.thumb_timer.stop()
        state.doc.close()
        if active and self.file_tabs.count(): self.activate_tab(self.file_tabs.currentIndex())
        elif not self.file_tabs.count():
            self.restoring_tab=False; self.matches=[]; self.match_index=-1; self.current=0; self.search_bar.hide(); self.titlebar.sync_tabs(); self.rebuild_thumbnails()
            self.page.setRange(1,1); self.total.setText('/ 0'); self.setWindowTitle('PDFeather'); self.canvas.arrange()

    def cycle_tab(self,direction):
        if self.file_tabs.count(): self.file_tabs.setCurrentIndex((self.file_tabs.currentIndex()+direction)%self.file_tabs.count())

    def queue_thumbs(self, *_):
        if not self.thumb_timer.isActive(): self.thumb_timer.start(0)

    def render_thumbs(self):
        if not self.doc or not self.thumbs.isVisible() or self.canvas.zoom_idle.isActive() or self.canvas.async_zoom and self.canvas.zoom_renderer.pending:return
        visible=self.thumbs.viewport().rect(); first=max(0,self.thumbs.indexAt(visible.topLeft()).row())
        last=self.thumbs.indexAt(visible.bottomLeft()).row()
        if last<first: last=min(self.thumbs.count()-1,first+visible.height()//185+1)
        padding=0 if self.prefs.get('optimization') else 12
        near=range(max(0,first-padding),min(self.thumbs.count(),last+padding+1))
        indices=sorted(near,key=lambda i:0 if first<=i<=last else min(abs(i-first),abs(i-last)))
        for i in range(first,last+1):
            if i in self.thumb_lru: self.thumb_lru.move_to_end(i)
        for i in indices:
            item=self.thumbs.item(i)
            if item.icon().isNull() and not item.data(Qt.ItemDataRole.UserRole+11):
                try:
                    item.setIcon(QIcon(QPixmap.fromImage(self.doc.image(i,112/self.doc.sizes[i][0],cached=False))))
                    item.setData(Qt.ItemDataRole.UserRole+10,0. if self.prefs.get('optimization') else time.monotonic()); self.thumb_lru[i]=True
                    if first<=i<=last and not self.prefs.get('optimization'):
                        for delay in (30,70,110,160): QTimer.singleShot(delay,self.thumbs.viewport().update)
                except Exception:
                    item.setData(Qt.ItemDataRole.UserRole+11,True); item.setToolTip('미리보기를 생성할 수 없습니다.')
                while len(self.thumb_lru)>(max(12,last-first+1) if self.prefs.get('optimization') else 160):
                    old,_=self.thumb_lru.popitem(last=False); self.thumbs.item(old).setIcon(QIcon())
                self.thumb_timer.start(1); return

    def set_zoom(self, zoom, anchor=None, keep_fit=False, interactive=False):
        zoom=max(.1,min(10.,zoom))
        if not keep_fit: self.fit_mode=None
        if self.canvas.dragging: self.canvas.cancel_drag()
        if abs(zoom-self.zoom)<.0001: self.canvas.arrange(); return
        if interactive and self.doc:self.canvas.begin_wheel_zoom()
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
            dialog=None
            try:
                dialog=PrintWindow(self.doc,self); dialog.exec()
            except Exception as exc: QMessageBox.warning(self, '인쇄 오류', str(exc))
            finally:
                if dialog is not None: dialog.deleteLater()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(u.isLocalFile() and u.toLocalFile().lower().endswith('.pdf') for u in event.mimeData().urls()): event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if url.isLocalFile() and url.toLocalFile().lower().endswith('.pdf'): self.open(url.toLocalFile())

    def closeEvent(self, event):
        self.canvas.reset_zoom_rendering()
        self.closing=True
        if getattr(self,"update_popup",None):self.update_popup.close()
        if getattr(self,'installer_download',None) and self.installer_download.reply:self.installer_download.cancel()
        self.clear_resize_cursor()
        self.save_tab_state()
        for i in range(self.file_tabs.count()): self.prefs.save_document(self.file_tabs.tabData(i))
        if self.prefs.get('remember_geometry'): self.prefs.storage.setValue('window_geometry',self.saveGeometry()); self.prefs.storage.sync()
        self.search_timer.stop(); self.search_debounce.stop(); self.thumb_timer.stop()
        QApplication.instance().removeEventFilter(self)
        self.external_timer.stop(); self.external_pending=[]
        self.update_timer.stop(); self.update_daily_timer.stop(); self.update_checker.cancel()
        self.canvas.cancel_drag(); self.notice_timer.stop(); self.settings_dialog.close(); self.captures.close()
        for i in range(self.file_tabs.count()): self.file_tabs.tabData(i).doc.close()
        self.doc=None; self.selection=None; self.active_tab=None; self.restoring_tab=False
        super().closeEvent(event)


if __name__ == '__main__':
    multiprocessing.freeze_support()
    if sys.platform=='win32': ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(NAME)
    app = QApplication(sys.argv); app.setApplicationName(NAME); app.setApplicationVersion(VERSION); app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    test_instance=len(sys.argv)>2 and sys.argv[1]=='--instance-test'
    smoke_mode=len(sys.argv)>1 and sys.argv[1]=='--smoke-test'
    instance=None
    if not smoke_mode:
        if test_instance:
            status_path=Path(sys.argv[2]).resolve()
            key='PDFeather-test-'+__import__('hashlib').sha256(str(status_path).encode()).hexdigest()[:20]
            instance=SingleInstance(app,name=key,directory=status_path.parent/'ipc')
            files=sys.argv[3:]
        else:
            instance=SingleInstance(app); files=sys.argv[1:]
        try:
            if not instance.start_or_forward(files): sys.exit(0)
        except Exception as exc:
            if test_instance:
                import json
                status_path.write_text(json.dumps({'error':str(exc),'server_error':instance.server.errorString()}),encoding='utf-8')
            else: QMessageBox.warning(None,NAME,str(exc))
            sys.exit(1)
        app.aboutToQuit.connect(instance.close)
    window=Window(enable_updates=not (smoke_mode or test_instance)); window.show()
    if instance: instance.paths_received.connect(window.receive_external_files)
    if test_instance:
        def report_instance():
            import json
            paths=[window.file_tabs.tabData(i).doc.path for i in range(window.file_tabs.count())]
            status_path.write_text(json.dumps({'pid':os.getpid(),'paths':paths,'tabs':len(paths)},ensure_ascii=False),encoding='utf-8')
        report_timer=QTimer(window); report_timer.setInterval(80); report_timer.timeout.connect(report_instance); report_timer.start()
        for path in files: window.open(path)
    if smoke_mode:
        window.open(sys.argv[2])
        dialog=PrintWindow(window.doc,window); dialog.show()
        result_path=Path(sys.argv[3]); deadline=time.monotonic()+40
        zoom_smoke={'started':False,'ready':False}
        check=QTimer(); check.setInterval(100)
        def smoke_check():
            pix=dialog.preview_label.pixmap()
            if pix and not pix.isNull():
                if not zoom_smoke['started']:
                    zoom_smoke['started']=True
                    window.canvas.zoom_renderer.ready.connect(lambda *_:zoom_smoke.update(ready=True))
                    window.set_zoom(window.zoom*1.15,interactive=True)
                    return
                if not zoom_smoke['ready']:
                    if time.monotonic()>deadline:
                        result_path.write_text('failed: background zoom renderer timed out');dialog.close();window.close();app.exit(1)
                    return
                check.stop()
                try:
                    from PySide6.QtNetwork import QSslSocket
                    assert QSslSocket.supportsSsl(), 'TLS support is unavailable'
                    # Exercise selection, composition, clipboard, and tab data in the frozen executable.
                    window.selection.begin((0,0)); window.selection.extend((0,3))
                    assert window.selection.text()=='Page'
                    rect=window.canvas.rects[0][1]
                    image=snapshot(window.doc,window.canvas.rects,QRectF(rect.x()+10,rect.y()+10,64,32))
                    window.captures.add(image); window.captures.add(image); merged=window.captures.image()
                    QApplication.clipboard().setImage(merged)
                    assert QApplication.clipboard().image().height()==64
                    window.captures.clear()
                    with tempfile.TemporaryDirectory() as folder:
                        path=Path(folder)/'second.pdf'; path.write_bytes(Path(window.doc.path).read_bytes())
                        window.open(str(path)); assert window.file_tabs.count()==2
                        window.file_tabs.setCurrentIndex(0); window.close_tab(1)
                    result_path.write_text('ok'); dialog.close(); window.close(); app.exit(0)
                except Exception as exc:
                    result_path.write_text('failed: '+str(exc)); dialog.close(); window.close(); app.exit(1)
            elif time.monotonic()>deadline:
                result_path.write_text('failed: '+dialog.error.text()); check.stop(); dialog.close(); window.close(); app.exit(1)
        check.timeout.connect(smoke_check); check.start()
    elif not test_instance:
        for path in files: window.open(path)
    sys.exit(app.exec())
