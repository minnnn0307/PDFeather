"""One scalable document-and-quill mark for the title bar and Windows icon."""
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QColor, QPen, QIcon


def logo_pixmap(size=128, dark=False):
    pix=QPixmap(size,size); pix.fill(Qt.GlobalColor.transparent)
    p=QPainter(pix); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.scale(size/128,size/128)
    paper=QColor('#253647' if dark else '#f8fafc')
    outline=QColor('#637c95' if dark else '#a8b9c9')
    ink=QColor('#8ce0d0' if dark else '#117a72')
    stem=QColor('#d2faf0' if dark else '#075b57')
    page=QPainterPath(); page.moveTo(25,7); page.lineTo(78,7); page.lineTo(102,31); page.lineTo(102,113); page.quadTo(102,121,94,121); page.lineTo(25,121); page.quadTo(17,121,17,113); page.lineTo(17,15); page.quadTo(17,7,25,7)
    p.setPen(QPen(outline,2.5)); p.setBrush(paper); p.drawPath(page)
    fold=QPainterPath(); fold.moveTo(78,8); fold.lineTo(78,26); fold.quadTo(78,32,84,32); fold.lineTo(101,32)
    p.drawPath(fold)
    # Vector lettering keeps the ICO and runtime logo identical across OS fonts.
    p.setPen(QPen(ink,4.2,Qt.PenStyle.SolidLine,Qt.PenCapStyle.SquareCap,Qt.PenJoinStyle.RoundJoin)); p.setBrush(Qt.BrushStyle.NoBrush)
    letters=QPainterPath(); letters.moveTo(31,112); letters.lineTo(31,96); letters.lineTo(38,96); letters.cubicTo(47,96,47,105,38,105); letters.lineTo(31,105)
    letters.moveTo(52,112); letters.lineTo(52,96); letters.lineTo(57,96); letters.cubicTo(70,96,70,112,57,112); letters.closeSubpath()
    letters.moveTo(76,112); letters.lineTo(76,96); letters.lineTo(88,96); letters.moveTo(76,103); letters.lineTo(85,103); p.drawPath(letters)
    feather=QPainterPath(); feather.moveTo(42,85); feather.cubicTo(42,59,67,28,117,17); feather.cubicTo(117,47,104,70,79,78); feather.lineTo(69,70); feather.lineTo(67,82); feather.lineTo(55,82); feather.closeSubpath()
    p.setPen(QPen(stem,1.3)); p.setBrush(ink); p.drawPath(feather)
    p.setPen(QPen(stem,3,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap)); p.drawLine(QPointF(33,95),QPointF(105,30))
    p.setPen(QPen(stem,1.5)); p.drawLine(QPointF(64,67),QPointF(66,49)); p.drawLine(QPointF(79,54),QPointF(96,53)); p.drawLine(QPointF(89,45),QPointF(90,32))
    p.end(); return pix


def application_icon(dark=False):
    result=QIcon()
    for size in (16,24,32,48,64,128,256): result.addPixmap(logo_pixmap(size,dark))
    return result
