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
