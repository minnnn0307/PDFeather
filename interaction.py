from PySide6.QtCore import Qt,QPointF,QRectF,QTimer
from PySide6.QtGui import QPainter,QColor,QPen,QKeySequence
from PySide6.QtWidgets import QMenu


class CanvasInteraction:
    def init_interactions(self):
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True); self.setCursor(Qt.CursorShape.ArrowCursor)
        self.dragging=False; self.drag_anchor=None; self.drag_pointer=None; self.capture_rect=None; self.pan_origin=None; self.pan_scroll=(0,0)
        self.drag_timer=QTimer(self); self.drag_timer.setInterval(30); self.drag_timer.timeout.connect(self.auto_scroll)

    def cancel_drag(self):
        self.dragging=False; self.drag_timer.stop(); self.capture_rect=None
        if self.reader.selection_tool=='hand': self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.update()

    def mousePressEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton or not self.reader.doc: return super().mousePressEvent(event)
        self.setFocus(); self.drag_anchor=event.position(); self.drag_pointer=event.globalPosition().toPoint()
        if self.reader.selection_tool=='pointer':
            if self.reader.selection: self.reader.selection.clear()
            self.update(); event.accept(); return
        if self.reader.selection_tool=='hand':
            self.pan_origin=event.globalPosition().toPoint(); self.pan_scroll=(self.reader.scroll.horizontalScrollBar().value(),self.reader.scroll.verticalScrollBar().value()); self.dragging=True; self.setCursor(Qt.CursorShape.ClosedHandCursor); event.accept(); return
        if self.reader.selection_tool=='text':
            endpoint=self.reader.selection.hit(event.position(),self.rects,strict=True)
            if endpoint is None:
                self.reader.selection.clear(); self.update(); return
            self.reader.selection.begin(endpoint)
        else:
            self.capture_rect=QRectF(event.position(),event.position())
        self.dragging=True; self.drag_timer.start(); self.update(); event.accept()

    def update_drag(self,point):
        if self.reader.selection_tool=='hand':
            delta=self.drag_pointer-self.pan_origin
            self.reader.scroll.horizontalScrollBar().setValue(self.pan_scroll[0]-delta.x()); self.reader.scroll.verticalScrollBar().setValue(self.pan_scroll[1]-delta.y()); return
        if self.reader.selection_tool=='text':
            self.reader.selection.extend(self.reader.selection.hit(point,self.rects))
        else:
            point=QPointF(max(0,min(self.width(),point.x())),max(0,min(self.height(),point.y())))
            self.capture_rect=QRectF(self.drag_anchor,point).normalized()
        self.update()

    def mouseMoveEvent(self,event):
        if self.dragging:
            self.drag_pointer=event.globalPosition().toPoint(); self.update_drag(event.position()); event.accept()
        else: super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self.dragging:
            self.drag_pointer=event.globalPosition().toPoint(); self.update_drag(event.position()); self.dragging=False; self.drag_timer.stop()
            if self.reader.selection_tool=='hand': self.setCursor(Qt.CursorShape.OpenHandCursor)
            if self.reader.selection_tool in ('capture','multi'):
                region=self.capture_rect; self.capture_rect=None; self.update()
                if region and region.width()>=4 and region.height()>=4: self.reader.capture_region(region)
            event.accept()
        else: super().mouseReleaseEvent(event)

    def auto_scroll(self):
        if not self.dragging or self.drag_pointer is None: return
        scroll=self.reader.scroll; point=scroll.viewport().mapFromGlobal(self.drag_pointer)
        dx=-22 if point.x()<22 else 22 if point.x()>scroll.viewport().width()-22 else 0
        dy=-22 if point.y()<22 else 22 if point.y()>scroll.viewport().height()-22 else 0
        if dx: scroll.horizontalScrollBar().setValue(scroll.horizontalScrollBar().value()+dx)
        if dy: scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().value()+dy)
        if dx or dy: self.update_drag(QPointF(self.mapFromGlobal(self.drag_pointer)))

    def keyPressEvent(self,event):
        if event.matches(QKeySequence.StandardKey.Copy): self.reader.copy_content(); event.accept()
        elif event.key()==Qt.Key.Key_Escape:
            self.cancel_drag()
            if self.reader.selection: self.reader.selection.clear()
            self.reader.set_selection_tool('text'); self.update(); event.accept()
        else: super().keyPressEvent(event)

    def contextMenuEvent(self,event):
        menu=QMenu(self)
        copy=menu.addAction('선택한 텍스트 복사'); copy.setEnabled(bool(self.reader.selection and self.reader.selection.anchor is not None)); copy.triggered.connect(self.reader.copy_text)
        menu.addSeparator()
        menu.addAction('일반 포인터',lambda:self.reader.set_selection_tool('pointer'))
        menu.addAction('손 도구',lambda:self.reader.set_selection_tool('hand'))
        menu.addAction('텍스트 선택',lambda:self.reader.set_selection_tool('text'))
        menu.addAction('영역 캡처',lambda:self.reader.set_selection_tool('capture'))
        menu.addAction('다중캡처',lambda:self.reader.set_selection_tool('multi'))
        if self.reader.captures.items: menu.addAction('다중캡처 이어붙여 복사',self.reader.copy_captures)
        menu.exec(event.globalPos())

    def paint_selection(self,painter,index,rect):
        if not self.reader.selection: return
        for box in self.reader.selection.boxes(index):
            target=QRectF(rect.x()+box.x()*self.reader.zoom,rect.y()+box.y()*self.reader.zoom,box.width()*self.reader.zoom,box.height()*self.reader.zoom)
            painter.fillRect(target,QColor(70,151,240,100))

    def paint_drag(self,painter):
        if self.capture_rect:
            painter.setPen(QPen(QColor('#45c3b3'),1.4,Qt.PenStyle.DashLine)); painter.setBrush(QColor(45,190,170,35)); painter.drawRect(self.capture_rect)
