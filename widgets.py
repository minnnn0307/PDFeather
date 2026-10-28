from PySide6.QtCore import Qt, QRectF, QPointF, QSize, Signal, QEvent, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QIcon, QPixmap, QPainterPath, QAction, QActionGroup
from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QLabel, QToolButton, QStyledItemDelegate, QStyle, QTabBar, QMenu
from branding import logo_pixmap
import math
import time
from themes import PALETTES

THEME='dark'

def set_theme(name):
    global THEME
    THEME=name



def icon(name):
    pix = QPixmap(24,24); pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(PALETTES[THEME]['text']),1.65,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
    def line(a,b,c,d): p.drawLine(QPointF(a,b),QPointF(c,d))
    def rect(x,y,w,h): p.drawRoundedRect(QRectF(x,y,w,h),1,1)
    if name=='open':
        path=QPainterPath(); path.moveTo(3,7); path.lineTo(9,7); path.lineTo(11,9); path.lineTo(21,9); path.lineTo(18,19); path.lineTo(3,19); path.closeSubpath(); p.drawPath(path); line(3,7,3,5); line(3,5,10,5)
    elif name=='print':
        rect(3,8,18,10); rect(7,3,10,5); p.fillRect(QRectF(7,14,10,7),QColor(PALETTES[THEME]['bar'])); rect(7,14,10,7); line(17,11,18,11)
    elif name=='search': p.drawEllipse(QRectF(4,3,12,12)); line(14,14,21,21)
    elif name=='info': p.drawEllipse(QRectF(3,3,18,18)); line(12,11,12,17); p.drawPoint(QPointF(12,7))
    elif name=='help':
        p.drawEllipse(QRectF(3,3,18,18)); path=QPainterPath(); path.moveTo(9,9); path.cubicTo(9,4,18,7,13,11); path.lineTo(12,14); p.drawPath(path); p.drawPoint(QPointF(12,17))
    elif name in ('prev','next'):
        x=14 if name=='prev' else 10; to=9 if name=='prev' else 15; line(x,6,to,12); line(to,12,x,18)
    elif name=='sidebar': rect(3,4,18,16); line(9,4,9,20); line(5,8,7,8); line(5,12,7,12)
    elif name in ('fit','width'):
        rect(5,3,14,18)
        if name=='fit': line(9,7,15,7); line(9,17,15,17); line(12,7,12,17)
        else: line(2,12,22,12); line(2,12,5,9); line(2,12,5,15); line(22,12,19,9); line(22,12,19,15)
    elif name=='pointer':
        path=QPainterPath(); path.moveTo(5,3); path.lineTo(5,19); path.lineTo(9,15); path.lineTo(12,21); path.lineTo(15,19.5); path.lineTo(12,14); path.lineTo(19,14); path.closeSubpath(); p.drawPath(path)
    elif name=='hand':
        path=QPainterPath(); path.moveTo(8,13); path.lineTo(8,6); path.cubicTo(8,3,11,3,11,6); path.lineTo(11,10); path.lineTo(11,4); path.cubicTo(11,1,14,1,14,4); path.lineTo(14,10); path.lineTo(14,6); path.cubicTo(14,3,17,3,17,6); path.lineTo(17,11); path.lineTo(17,9); path.cubicTo(17,6,20,6,20,9); path.lineTo(20,15); path.cubicTo(20,20,17,22,13,22); path.cubicTo(9,22,8,20,6,17); path.lineTo(4,14); path.cubicTo(2,11,4,10,6,12); path.lineTo(8,14); p.drawPath(path)
    elif name.startswith('view_'):
        if name=='view_single': rect(7,3,10,18)
        elif name=='view_scroll': rect(7,2,10,9); rect(7,13,10,9)
        elif name=='view_spread': rect(3,4,8,16); rect(13,4,8,16)
        else:
            for x in (3,13):
                for y in (2,13): rect(x,y,8,9)
    elif name=='text':
        line(5,5,19,5); line(12,5,12,20); line(8,20,16,20); line(5,5,5,8); line(19,5,19,8)
    elif name in ('capture','multi'):
        rect(4,5,16,14); line(8,3,8,7); line(2,9,6,9); line(18,15,22,15); line(16,17,16,21)
        if name=='multi': line(8,10,16,10); line(8,14,16,14)
    elif name=='settings':
        # A solid six-tooth silhouette keeps the teeth legible at toolbar size.
        gear=QPainterPath(); gear.addEllipse(QRectF(5,5,14,14))
        for tooth in range(6):
            angle=math.radians(tooth*60)
            points=[]
            for radial,tangent in [(6,-2),(10,-2),(10,2),(6,2)]:
                points.append(QPointF(12+math.cos(angle)*radial-math.sin(angle)*tangent,
                                     12+math.sin(angle)*radial+math.cos(angle)*tangent))
            tab=QPainterPath(); tab.moveTo(points[0])
            for point in points[1:]: tab.lineTo(point)
            tab.closeSubpath(); gear=gear.united(tab)
        hole=QPainterPath(); hole.addEllipse(QRectF(8.8,8.8,6.4,6.4))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(PALETTES[THEME]['text']))
        p.drawPath(gear.subtracted(hole))
    elif name=='minus': line(6,12,18,12)
    elif name=='plus': line(6,12,18,12); line(12,6,12,18)
    elif name=='minimize': line(6,16,18,16)
    elif name=='maximize': rect(6,6,12,12)
    elif name=='restore': rect(5,8,11,11); line(9,5,19,5); line(19,5,19,15)
    elif name=='close': line(7,7,17,17); line(17,7,7,17)
    p.end(); return QIcon(pix)


def tool(name, tip, callback, parent=None):
    b=QToolButton(parent); b.setProperty("iconName",name); b.setIcon(icon(name)); b.setIconSize(QSize(22,22)); b.setToolTip(tip); b.setAccessibleName(tip); b.setFixedSize(36,34); b.clicked.connect(callback); return b


class TitleTabBar(QTabBar):
    def __init__(self,parent=None):
        super().__init__(parent); self.setObjectName('documentTabs'); self.setDocumentMode(True); self.setExpanding(False); self.setMovable(True); self.setUsesScrollButtons(True); self.setElideMode(Qt.TextElideMode.ElideRight); self.setDrawBase(False)

    def tabSizeHint(self,index):
        size=super().tabSizeHint(index); return QSize(min(230,max(140,size.width())),34)

    def tabInserted(self,index):
        super().tabInserted(index)
        close=tool('close','탭 닫기',lambda:self.close_button(close),self); close.setObjectName('tabClose'); close.setFixedSize(22,22); close.setIconSize(QSize(13,13)); self.setTabButton(index,QTabBar.ButtonPosition.RightSide,close)

    def close_button(self,button):
        for index in range(self.count()):
            if self.tabButton(index,QTabBar.ButtonPosition.RightSide) is button: self.tabCloseRequested.emit(index); return

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self.tabAt(event.position().toPoint())<0:
            self.parentWidget().mousePressEvent(event)
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if self.parentWidget().drag_origin is not None: self.parentWidget().mouseMoveEvent(event)
        else: super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self,event):
        if self.tabAt(event.position().toPoint())<0: self.parentWidget().toggle()
        else: super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self.parentWidget().drag_origin is not None:
            self.parentWidget().mouseReleaseEvent(event); return
        if event.button()==Qt.MouseButton.MiddleButton:
            index=self.tabAt(event.position().toPoint())
            if index>=0: self.tabCloseRequested.emit(index)
        else: super().mouseReleaseEvent(event)


class ViewModePicker(QToolButton):
    currentIndexChanged=Signal(int)
    ICONS=('view_single','view_scroll','view_spread','view_spread_scroll')
    def __init__(self,parent=None):
        super().__init__(parent); self.labels=[]; self.index=-1; self.actions=[]
        self.setObjectName('viewModePicker'); self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon); self.setIconSize(QSize(18,18)); self.setFixedSize(142,32); self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup); self.setToolTip('문서 보기 방식')
        self.popup=QMenu(self); self.popup.setObjectName('viewModeMenu'); self.group=QActionGroup(self); self.group.setExclusive(True); self.setMenu(self.popup)

    def addItems(self,labels):
        for index,label in enumerate(labels):
            self.labels.append(label); action=QAction(icon(self.ICONS[index]),label,self); action.setCheckable(True); action.triggered.connect(lambda checked=False,i=index:self.setCurrentIndex(i)); self.group.addAction(action); self.popup.addAction(action); self.actions.append(action)
        if self.index<0: self.setCurrentIndex(0)

    def currentIndex(self): return self.index

    def setCurrentIndex(self,index):
        if not 0<=index<len(self.labels): return
        changed=index!=self.index; self.index=index; self.setText(self.labels[index]); self.setProperty('iconName',self.ICONS[index]); self.setIcon(icon(self.ICONS[index])); self.actions[index].setChecked(True)
        if changed: self.currentIndexChanged.emit(index)

    def refresh_icons(self):
        for index,action in enumerate(self.actions): action.setIcon(icon(self.ICONS[index]))
        if self.index>=0: self.setIcon(icon(self.ICONS[self.index]))


class TitleBar(QWidget):
    def __init__(self, window):
        super().__init__(window); self.reader=window; self.drag_origin=None; self.dragging=False; self.setObjectName('titleBar'); self.setFixedHeight(42)
        row=QHBoxLayout(self); row.setContentsMargins(14,0,4,0); row.setSpacing(4)
        self.brand=QLabel(); self.brand.setObjectName('brand'); self.brand.setFixedSize(16,16); self.brand.setAlignment(Qt.AlignmentFlag.AlignCenter); self.brand.setPixmap(logo_pixmap(16,THEME=='dark',window.devicePixelRatioF())); row.addWidget(self.brand)
        self.title=QLabel('PDFeather'); self.title.setObjectName('windowTitle'); row.addWidget(self.title); row.addSpacing(14)
        self.tabs=TitleTabBar(self); row.addWidget(self.tabs,1)
        self.empty_space=QWidget(); row.addWidget(self.empty_space,1)
        self.drag_space=QWidget(); self.drag_space.setFixedWidth(28); row.addWidget(self.drag_space)
        self.sync_tabs()
        window.installEventFilter(self)
        row.addWidget(tool('minimize','최소화',window.showMinimized))
        self.max_button=tool('maximize','최대화 / 창 모드',self.toggle); row.addWidget(self.max_button)
        close=tool('close','종료',window.close); close.setObjectName('closeButton'); row.addWidget(close)


    def sync_tabs(self):
        present=self.tabs.count()>0; self.tabs.setVisible(present); self.empty_space.setVisible(not present)

    def sync_maximize_icon(self):
        name='restore' if self.reader.isMaximized() else 'maximize'
        self.max_button.setProperty('iconName',name); self.max_button.setIcon(icon(name))

    def eventFilter(self,obj,event):
        if obj is self.reader and event.type()==QEvent.Type.WindowStateChange:
            self.sync_maximize_icon()
        return super().eventFilter(obj,event)

    def toggle(self):
        self.drag_origin=None; self.dragging=False
        self.reader.showNormal() if self.reader.isMaximized() else self.reader.showMaximized()
        self.sync_maximize_icon()

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self.drag_origin=event.globalPosition().toPoint()
            self.drag_offset=self.reader.mapFromGlobal(self.drag_origin)
            self.drag_ratio=max(0.,min(1.,self.drag_offset.x()/max(1,self.reader.width())))
            self.dragging=False; event.accept()

    def mouseMoveEvent(self,event):
        if self.drag_origin is None or not event.buttons() & Qt.MouseButton.LeftButton: return
        point=event.globalPosition().toPoint()
        if not self.dragging:
            if (point-self.drag_origin).manhattanLength()<QApplication.startDragDistance(): return
            self.dragging=True
            if self.reader.isMaximized():
                normal=self.reader.normalGeometry()
                self.reader.showNormal()
                self.reader.resize(normal.size())
                self.drag_offset=QPoint(round(self.reader.width()*self.drag_ratio),min(self.drag_offset.y(),self.height()-1))
        self.reader.move(point-self.drag_offset); event.accept()

    def mouseReleaseEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton or self.drag_origin is None: return
        point=event.globalPosition().toPoint()
        screen=QApplication.screenAt(point)
        if self.dragging and screen is not None:
            bounds=screen.availableGeometry()
            if bounds.left()<=point.x()<=bounds.right() and point.y()<=bounds.top()+8:
                self.reader.showMaximized()
            elif point.x()<=bounds.left()+8 or point.x()>=bounds.right()-8:
                self.reader.showNormal()
                half=bounds.width()//2;left=point.x()<=bounds.left()+8
                self.reader.setGeometry(bounds.left() if left else bounds.left()+half,bounds.top(),half if left else bounds.width()-half,bounds.height())
        self.drag_origin=None; self.dragging=False; self.sync_maximize_icon(); event.accept()

    def mouseDoubleClickEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton: self.toggle()


class ThumbnailDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        painter.save(); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r=option.rect.adjusted(12,10,-12,-10)
        selected=bool(option.state & QStyle.StateFlag.State_Selected)
        if selected:
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QColor(PALETTES[THEME]['selected'])); painter.drawRoundedRect(QRectF(option.rect.adjusted(4,3,-4,-3)),6,6)
        image=index.data(Qt.ItemDataRole.DecorationRole)
        if isinstance(image,QIcon) and not image.isNull():
            pix=image.pixmap(QSize(r.width(),r.height()-8)); size=pix.size(); size.scale(r.size(),Qt.AspectRatioMode.KeepAspectRatio)
            target=QRectF(r.center().x()-size.width()/2,r.center().y()-size.height()/2,size.width(),size.height())
            painter.fillRect(target,QColor('#ffffff')); painter.save()
            started=index.data(Qt.ItemDataRole.UserRole+10)
            if started: painter.setOpacity(min(1.,max(0.,(time.monotonic()-started)/.14)))
            painter.drawPixmap(target,pix,QRectF(pix.rect())); painter.restore()
        else:
            paper=r.adjusted(8,0,-8,0); painter.fillRect(paper,QColor('#ffffff'))
            painter.setPen(QPen(QColor('#e8edf1'),3,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
            for row in range(5): painter.drawLine(QPointF(paper.left()+12,paper.top()+22+row*12),QPointF(paper.right()-12-(14 if row==4 else 0),paper.top()+22+row*12))
        label=QRectF(r.center().x()-25,r.bottom()-24,50,23)
        painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QColor(20,25,33,205)); painter.drawRoundedRect(label,7,7)
        painter.setPen(QColor('#ffffff')); painter.drawText(label,Qt.AlignmentFlag.AlignCenter,str(index.row()+1))
        painter.restore()


class CategorySections(QWidget):
    """Predictable accordion sizing without platform-dependent toolbox tab metrics."""
    def __init__(self,parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QVBoxLayout
        self.rows=QVBoxLayout(self); self.rows.setContentsMargins(0,0,0,0); self.rows.setSpacing(6)
        self.pages=[]; self.buttons=[]; self.index=0

    def addItem(self,page,title):
        from PySide6.QtWidgets import QPushButton
        index=len(self.pages); button=QPushButton(title); button.setObjectName('sectionHeader'); button.setCheckable(True); button.setFixedHeight(38)
        button.clicked.connect(lambda *_:self.setCurrentIndex(index))
        self.buttons.append(button); self.pages.append(page); self.rows.addWidget(button); self.rows.addWidget(page)
        self.setCurrentIndex(self.index)

    def setCurrentIndex(self,index):
        self.index=index
        for i,(button,page) in enumerate(zip(self.buttons,self.pages)):
            button.setChecked(i==index); page.setVisible(i==index); self.rows.setStretch(i*2+1,1 if i==index else 0)
