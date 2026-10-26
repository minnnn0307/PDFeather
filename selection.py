"""Text hit testing and selection in PDF coordinates, including rotated pages."""
import ctypes
from PySide6.QtCore import QPointF, QRectF
import pypdfium2 as pdfium


def display_boxes(page,size,text,start=0,count=-1):
    width,height=size; boxes=[]
    for j in range(text.count_rects(start,count)):
        l,b,r,t=text.get_rect(j); points=[]
        for x,y in ((l,b),(l,t),(r,b),(r,t)):
            dx,dy=ctypes.c_int(),ctypes.c_int()
            pdfium.raw.FPDF_PageToDevice(page,0,0,round(width*10),round(height*10),0,x,y,ctypes.byref(dx),ctypes.byref(dy))
            points.append((dx.value/10,dy.value/10))
        boxes.append(QRectF(min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points)-min(p[0] for p in points),max(p[1] for p in points)-min(p[1] for p in points)))
    return boxes


class TextSelection:
    def __init__(self,doc):
        self.doc=doc; self.anchor=None; self.focus=None; self.box_cache={}

    def clear(self):
        self.anchor=None; self.focus=None; self.box_cache.clear()

    def hit(self,point,page_rects,strict=False):
        candidate=next(((i,r) for i,r in page_rects if r.contains(point)),None)
        if candidate is None and not strict and page_rects:
            candidate=min(page_rects,key=lambda item:abs(item[1].center().y()-point.y()))
        if candidate is None: return None
        index,rect=candidate
        page=self.doc.pdf[index]; text=None
        try:
            text=page.get_textpage()
            if text.count_chars()==0: return None
            x,y=ctypes.c_double(),ctypes.c_double()
            pdfium.raw.FPDF_DeviceToPage(page,0,0,round(rect.width()*10),round(rect.height()*10),0,round((point.x()-rect.x())*10),round((point.y()-rect.y())*10),ctypes.byref(x),ctypes.byref(y))
            tolerance=8*self.doc.sizes[index][0]/rect.width()
            char=text.get_index(x.value,y.value,tolerance if strict else 1e6,tolerance if strict else 1e6)
            return (index,char) if char is not None and char>=0 else None
        finally:
            if text: text.close()
            page.close()

    def begin(self,endpoint):
        self.anchor=endpoint; self.focus=endpoint; self.box_cache.clear()

    def extend(self,endpoint):
        if endpoint is not None and endpoint!=self.focus: self.focus=endpoint; self.box_cache.clear()

    def range_for_page(self,index):
        if self.anchor is None or self.focus is None: return None
        first,last=sorted((self.anchor,self.focus))
        if not first[0]<=index<=last[0]: return None
        start=first[1] if index==first[0] else 0
        count=last[1]-start+1 if index==last[0] else -1
        return start,count

    def boxes(self,index):
        span=self.range_for_page(index)
        if span is None: return []
        if index in self.box_cache: return self.box_cache[index]
        page=self.doc.pdf[index]; text=None
        try:
            text=page.get_textpage(); boxes=display_boxes(page,self.doc.sizes[index],text,*span)
        finally:
            if text: text.close()
            page.close()
        if len(self.box_cache)>=12: self.box_cache.clear()
        self.box_cache[index]=boxes; return boxes

    def text(self):
        if self.anchor is None or self.focus is None: return ''
        first,last=sorted((self.anchor,self.focus)); parts=[]
        for index in range(first[0],last[0]+1):
            page=self.doc.pdf[index]; text=None
            try:
                text=page.get_textpage(); parts.append(text.get_text_range(*self.range_for_page(index)))
            finally:
                if text: text.close()
                page.close()
        return '\n'.join(parts)
