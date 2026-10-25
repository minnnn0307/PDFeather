"""Physical-pixel tiles; no full-page bitmap is allocated at high zoom."""
import math
from PySide6.QtCore import QRectF

TILE_SIZE=768


def visible_tiles(page_rect, visible_rect, dpr, size=TILE_SIZE):
    full_width=max(1,math.ceil(page_rect.width()*dpr))
    full_height=max(1,math.ceil(page_rect.height()*dpr))
    clipped=page_rect.intersected(visible_rect)
    if clipped.isEmpty(): return
    x0=max(0,math.floor((clipped.left()-page_rect.left())/page_rect.width()*full_width))
    y0=max(0,math.floor((clipped.top()-page_rect.top())/page_rect.height()*full_height))
    x1=min(full_width,math.ceil((clipped.right()-page_rect.left())/page_rect.width()*full_width))
    y1=min(full_height,math.ceil((clipped.bottom()-page_rect.top())/page_rect.height()*full_height))
    for y in range(y0//size*size,y1,size):
        for x in range(x0//size*size,x1,size):
            width=min(size,full_width-x); height=min(size,full_height-y)
            target=QRectF(page_rect.x()+x/full_width*page_rect.width(),page_rect.y()+y/full_height*page_rect.height(),width/full_width*page_rect.width(),height/full_height*page_rect.height())
            yield (full_width,full_height,x,y,width,height),target
