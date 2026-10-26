"""Clean PDF region snapshots and bounded, disk-backed multi-capture composition."""
import math
import tempfile
from pathlib import Path
from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QImage,QPainter
from rendering import visible_tiles

MAX_CAPTURE_PIXELS=16_000_000
MAX_CAPTURE_EDGE=30000


def snapshot(doc,page_rects,region,dpr=1.):
    region=region.normalized()
    if not any(rect.intersects(region) for _,rect in page_rects): raise ValueError('문서가 포함된 영역을 선택하세요.')
    width=max(1,math.ceil(region.width()*dpr)); height=max(1,math.ceil(region.height()*dpr))
    check_size(width,height)
    image=QImage(width,height,QImage.Format.Format_RGB888)
    if image.isNull(): raise ValueError('캡처 이미지를 만들 메모리가 부족합니다.')
    image.fill(Qt.GlobalColor.white); painter=QPainter(image)
    try:
        painter.scale(dpr,dpr); painter.translate(-region.x(),-region.y())
        for index,rect in page_rects:
            for tile,target in visible_tiles(rect,region,dpr): painter.drawImage(target,doc.tile(index,*tile))
    finally: painter.end()
    return image


def check_size(width,height,limit=MAX_CAPTURE_PIXELS):
    if width<1 or height<1 or width*height>limit or max(width,height)>MAX_CAPTURE_EDGE:
        raise ValueError('합친 이미지가 너무 큽니다. 일부를 복사한 뒤 초기화하거나 더 작은 영역을 선택하세요. (최대 1,600만 픽셀)')


class CaptureCollection:
    def __init__(self,limit=MAX_CAPTURE_PIXELS):
        self.temp=tempfile.TemporaryDirectory(prefix='pdfeather-captures-'); self.items=[]; self.serial=0; self.limit=limit

    @property
    def size(self):
        return max((item[1] for item in self.items),default=0),sum(item[2] for item in self.items)

    def add(self,image):
        if image.isNull(): raise ValueError('빈 이미지입니다.')
        width,height=self.size
        check_size(max(width,image.width()),height+image.height(),self.limit)
        self.serial+=1; path=Path(self.temp.name)/f'{self.serial}.png'
        if not image.save(str(path),'PNG'): raise ValueError('캡처를 임시 보관할 수 없습니다.')
        self.items.append((path,image.width(),image.height()))

    def undo(self):
        if self.items: self.items.pop()[0].unlink(missing_ok=True)

    def clear(self):
        while self.items: self.undo()

    def image(self):
        if not self.items: raise ValueError('영역을 드래그해 캡처를 먼저 추가하세요.')
        width,height=self.size; check_size(width,height,self.limit)
        result=QImage(width,height,QImage.Format.Format_RGB888)
        if result.isNull(): raise ValueError('합친 이미지를 만들 메모리가 부족합니다.')
        result.fill(Qt.GlobalColor.white); painter=QPainter(result); y=0
        try:
            for path,w,h in self.items:
                image=QImage(str(path))
                if image.isNull(): raise ValueError('임시 캡처를 읽을 수 없습니다. 다시 캡처하세요.')
                painter.drawImage((width-w)//2,y,image); y+=h
        finally: painter.end()
        return result

    def close(self): self.temp.cleanup(); self.items.clear()
