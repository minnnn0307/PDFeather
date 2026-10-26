from PySide6.QtCore import Qt, QRectF, QPointF, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QIcon, QPixmap, QPainterPath
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QToolButton, QStyledItemDelegate, QStyle
from branding import logo_pixmap
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
    elif name=='text':
        line(5,5,19,5); line(12,5,12,20); line(8,20,16,20); line(5,5,5,8); line(19,5,19,8)
    elif name in ('capture','multi'):
        rect(4,5,16,14); line(8,3,8,7); line(2,9,6,9); line(18,15,22,15); line(16,17,16,21)
        if name=='multi': line(8,10,16,10); line(8,14,16,14)
    elif name=='settings':
        p.drawEllipse(QRectF(6,6,12,12)); p.drawEllipse(QRectF(10,10,4,4))
        for x1,y1,x2,y2 in [(12,2,12,5),(12,19,12,22),(2,12,5,12),(19,12,22,12),(5,5,7,7),(17,17,19,19),(5,19,7,17),(17,7,19,5)]: line(x1,y1,x2,y2)
    elif name=='minus': line(6,12,18,12)
    elif name=='plus': line(6,12,18,12); line(12,6,12,18)
    elif name=='minimize': line(6,16,18,16)
    elif name=='maximize': rect(6,6,12,12)
    elif name=='restore': rect(5,8,11,11); line(9,5,19,5); line(19,5,19,15)
    elif name=='close': line(7,7,17,17); line(17,7,7,17)
    p.end(); return QIcon(pix)


def tool(name, tip, callback, parent=None):
    b=QToolButton(parent); b.setProperty("iconName",name); b.setIcon(icon(name)); b.setIconSize(QSize(22,22)); b.setToolTip(tip); b.setAccessibleName(tip); b.setFixedSize(36,34); b.clicked.connect(callback); return b


class TitleBar(QWidget):
    def __init__(self, window):
        super().__init__(window); self.window=window; self.setObjectName('titleBar'); self.setFixedHeight(42)
        row=QHBoxLayout(self); row.setContentsMargins(14,0,4,0); row.setSpacing(4)
        self.brand=QLabel(); self.brand.setObjectName('brand'); self.brand.setFixedSize(16,16); self.brand.setAlignment(Qt.AlignmentFlag.AlignCenter); self.brand.setPixmap(logo_pixmap(16,THEME=='dark',window.devicePixelRatioF())); row.addWidget(self.brand)
        self.title=QLabel('PDFeather'); self.title.setObjectName('windowTitle'); row.addWidget(self.title); row.addStretch()
        row.addWidget(tool('minimize','최소화',window.showMinimized))
        self.max_button=tool('maximize','최대화 / 창 모드',self.toggle); row.addWidget(self.max_button)
        close=tool('close','종료',window.close); close.setObjectName('closeButton'); row.addWidget(close)
        window.windowTitleChanged.connect(self.title.setText)

    def toggle(self):
        self.window.showNormal() if self.window.isMaximized() else self.window.showMaximized()
        self.max_button.setProperty('iconName','restore' if self.window.isMaximized() else 'maximize'); self.max_button.setIcon(icon(self.max_button.property('iconName')))

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self.window.windowHandle(): self.window.windowHandle().startSystemMove()

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
            painter.drawPixmap(target,pix,QRectF(pix.rect()))
        else:
            painter.fillRect(r.adjusted(8,0,-8,0),QColor(PALETTES[THEME]['placeholder']))
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
