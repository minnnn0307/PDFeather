"""Pure layout routines shared by preview and printing."""
import math


def parse_pages(text, count):
    if not text.strip():
        return list(range(count))
    result = []
    for part in text.split(','):
        bounds = part.strip().split('-')
        if len(bounds) > 2 or any(not x.strip().isdigit() for x in bounds):
            raise ValueError('페이지 범위 예: 1-3,5,8')
        a, b = int(bounds[0]), int(bounds[-1])
        if not 1 <= a <= b <= count:
            raise ValueError(f'1~{count} 범위의 페이지를 입력하세요.')
        result.extend(range(a - 1, b))
    return list(dict.fromkeys(result))


def grid(n):
    return {1: (1, 1), 2: (2, 1), 4: (2, 2), 6: (3, 2), 9: (3, 3), 16: (4, 4)}[n]


def placement(size, cell, dpi, percent=None):
    x, y, w, h = cell
    pw, ph = size
    scale = min(w / pw, h / ph) if percent is None else dpi / 72 * percent / 100
    return x + (w-pw*scale)/2, y + (h-ph*scale)/2, pw*scale, ph*scale


def print_cells(page_mm, margins_mm, nup, gap_mm, dpi):
    """Physical sheet coordinates; margins are left, top, right, bottom in mm."""
    width,height=page_mm; left,top,right,bottom=margins_mm
    if min(left,top,right,bottom,gap_mm)<0: raise ValueError('여백과 간격은 0 이상이어야 합니다.')
    cols,rows=grid(nup)
    cw=(width-left-right-gap_mm*(cols-1))/cols
    ch=(height-top-bottom-gap_mm*(rows-1))/rows
    if cw<=0 or ch<=0: raise ValueError('여백 또는 페이지 간격이 너무 큽니다. 인쇄 영역을 확보하세요.')
    factor=dpi/25.4
    return [((left+(i%cols)*(cw+gap_mm))*factor,(top+(i//cols)*(ch+gap_mm))*factor,cw*factor,ch*factor) for i in range(nup)]


def print_placement(size,cell,dpi,percent=100,basis='fit'):
    """Fit is 100%; actual-size mode explicitly uses the PDF's physical size."""
    if basis=='actual': return placement(size,cell,dpi,100 if percent is None else percent)
    x,y,w,h=placement(size,cell,dpi,None)
    factor=(100 if percent is None else percent)/100
    return x+w*(1-factor)/2,y+h*(1-factor)/2,w*factor,h*factor
