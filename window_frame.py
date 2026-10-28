"""Subtle frameless-window outline; no visible resize handles."""
import sys,ctypes
from PySide6.QtWidgets import QApplication
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
        elif self.native_rounding(): self.owner.clearMask()
        else:
            path=QPainterPath();path.addRoundedRect(QRectF(self.owner.rect()),6,6)
            self.owner.setMask(QRegion(path.toFillPolygon().toPolygon()))
        self.raise_();self.update()

    def native_rounding(self):
        if sys.platform!='win32' or QApplication.platformName()!='windows':return False
        try:
            value=ctypes.c_int(3)
            function=ctypes.windll.dwmapi.DwmSetWindowAttribute
            function.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_void_p,ctypes.c_uint]
            return function(int(self.owner.winId()),33,ctypes.byref(value),ctypes.sizeof(value))==0
        except (AttributeError,OSError):return False

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
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(.5,.5,-.5,-.5),5.5,5.5)
