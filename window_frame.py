"""Subtle frameless-window outline; no visible resize handles."""
from PySide6.QtCore import Qt,QRectF,QEvent
from PySide6.QtGui import QPainter,QPainterPath,QRegion,QColor,QPen
from PySide6.QtWidgets import QWidget

class WindowFrame(QWidget):
    def __init__(self,owner):
        super().__init__(owner);self.owner=owner
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        owner.installEventFilter(self)

    def sync(self):
        self.setGeometry(self.owner.rect())
        if self.owner.isMaximized() or self.owner.isFullScreen(): self.owner.clearMask()
        else:
            path=QPainterPath();path.addRoundedRect(QRectF(self.owner.rect()),7,7)
            self.owner.setMask(QRegion(path.toFillPolygon().toPolygon()))
        self.raise_();self.update()

    def eventFilter(self,obj,event):
        if obj is self.owner and event.type() in (QEvent.Type.Resize,QEvent.Type.Show,QEvent.Type.WindowStateChange,QEvent.Type.ActivationChange):self.sync()
        return super().eventFilter(obj,event)

    def paintEvent(self,event):
        if self.owner.isMaximized() or self.owner.isFullScreen():return
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        dark=self.owner.theme_name=='dark'
        color=QColor('#77818f' if dark else '#9aa8b6')
        if not self.owner.isActiveWindow():color.setAlpha(135)
        painter.setPen(QPen(color,1));painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(.5,.5,-.5,-.5),6.5,6.5)
