"""Centered, dimmed in-app sheets shared by settings and print workflows."""
from PySide6.QtCore import Qt,QEvent,QSize,QPoint,QRect
from PySide6.QtWidgets import QDialog,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QLayout


def resize_edges(point,size,margin=8):
    edges=Qt.Edge(0)
    if not QRect(QPoint(0,0),size).contains(point): return edges
    if point.x()<margin: edges|=Qt.Edge.LeftEdge
    elif point.x()>=size.width()-margin: edges|=Qt.Edge.RightEdge
    if point.y()<margin: edges|=Qt.Edge.TopEdge
    elif point.y()>=size.height()-margin: edges|=Qt.Edge.BottomEdge
    return edges


class PopupSheet(QDialog):
    def __init__(self,parent,title='',size=QSize(900,680)):
        super().__init__(parent,Qt.WindowType.Dialog|Qt.WindowType.FramelessWindowHint)
        self.owner=parent; self.preferred=size; self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setSizeGripEnabled(False)
        self.scrim=QWidget(parent); self.scrim.setObjectName('popupScrim')
        self.scrim.setStyleSheet('#popupScrim { background:rgba(10,16,24,105); }'); self.scrim.hide()
        self.destroyed.connect(self.scrim.deleteLater)
        outer=QVBoxLayout(self); outer.setContentsMargins(0,0,0,0); outer.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.card=QWidget(); self.card.setObjectName('popupCard'); outer.addWidget(self.card)
        self.body=QVBoxLayout(self.card); self.body.setContentsMargins(20,16,20,20); self.body.setSpacing(16)
        header=QHBoxLayout(); label=QLabel(title); label.setObjectName('popupTitle'); header.addWidget(label); header.addStretch()
        self.close_button=QPushButton('×'); self.close_button.setObjectName('popupClose'); self.close_button.setFixedSize(32,32); self.close_button.setToolTip('닫기'); self.close_button.clicked.connect(self.reject); header.addWidget(self.close_button)
        self.body.addLayout(header)
        parent.installEventFilter(self)

    def place(self):
        bounds=self.owner.rect(); self.scrim.setGeometry(bounds)
        self.resize(min(self.preferred.width(),max(320,bounds.width()-32)),min(self.preferred.height(),max(260,bounds.height()-32)))
        center=self.owner.mapToGlobal(bounds.center()); self.move(center-QPoint(self.width()//2,self.height()//2))

    def showEvent(self,event):
        self.place(); self.scrim.show(); self.scrim.raise_(); super().showEvent(event)

    def hideEvent(self,event):
        self.scrim.hide(); super().hideEvent(event)

    def eventFilter(self,obj,event):
        if obj is self.owner and self.isVisible() and event.type() in (QEvent.Type.Resize,QEvent.Type.Move): self.place()
        return super().eventFilter(obj,event)
