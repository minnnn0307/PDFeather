"""One scalable document-and-quill mark for the title bar and Windows icon."""
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QColor, QPen, QIcon


def logo_pixmap(size=128, dark=False, dpr=1.):
    pix=QPixmap(round(size*dpr),round(size*dpr)); pix.setDevicePixelRatio(dpr); pix.fill(Qt.GlobalColor.transparent)
    p=QPainter(pix); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.scale(size/128,size/128)
    paper=QColor('#253647' if dark else '#f8fafc')
    outline=QColor('#637c95' if dark else '#a8b9c9')
    ink=QColor('#8ce0d0' if dark else '#117a72')
    stem=QColor('#d2faf0' if dark else '#075b57')
    page=QPainterPath(); page.moveTo(25,7); page.lineTo(78,7); page.lineTo(102,31); page.lineTo(102,113); page.quadTo(102,121,94,121); page.lineTo(25,121); page.quadTo(17,121,17,113); page.lineTo(17,15); page.quadTo(17,7,25,7)
    p.setPen(QPen(outline,2.5)); p.setBrush(paper); p.drawPath(page)
    fold=QPainterPath(); fold.moveTo(78,8); fold.lineTo(78,26); fold.quadTo(78,32,84,32); fold.lineTo(101,32)
    p.drawPath(fold)
    feather=QPainterPath(); feather.moveTo(39,70); feather.cubicTo(41,42,70,15,117,9); feather.cubicTo(117,34,103,58,81,67); feather.lineTo(72,58); feather.lineTo(67,70); feather.closeSubpath()
    p.setPen(QPen(stem,1.8)); p.setBrush(ink); p.drawPath(feather)
    p.setPen(QPen(stem,3.5,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap)); p.drawLine(QPointF(33,73),QPointF(106,22))
    p.setPen(QPen(stem,1.7)); p.drawLine(QPointF(62,53),QPointF(65,34)); p.drawLine(QPointF(80,40),QPointF(99,39))
    # Large high-contrast PDF badge remains legible at desktop icon sizes.
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(ink); p.drawRoundedRect(QRectF(5,78,113,36),5,5)
    p.setPen(QPen(QColor('#17312f' if dark else '#ffffff'),5.8,Qt.PenStyle.SolidLine,Qt.PenCapStyle.SquareCap,Qt.PenJoinStyle.RoundJoin)); p.setBrush(Qt.BrushStyle.NoBrush)
    letters=QPainterPath(); letters.moveTo(24,106); letters.lineTo(24,85); letters.lineTo(34,85); letters.cubicTo(46,85,46,98,34,98); letters.lineTo(24,98)
    letters.moveTo(54,106); letters.lineTo(54,85); letters.lineTo(61,85); letters.cubicTo(78,85,78,106,61,106); letters.closeSubpath()
    letters.moveTo(87,106); letters.lineTo(87,85); letters.lineTo(104,85); letters.moveTo(87,94); letters.lineTo(100,94); p.drawPath(letters)
    p.end(); return pix


def application_icon(dark=False):
    result=QIcon()
    for size in (16,24,32,48,64,128,256): result.addPixmap(logo_pixmap(size,dark))
    return result
