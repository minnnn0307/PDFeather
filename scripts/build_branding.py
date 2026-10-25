"""Build a multi-resolution Windows ICO from the shared vector painter."""
import os
import struct
import sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QBuffer,QByteArray,QIODevice
from PySide6.QtWidgets import QApplication
from branding import logo_pixmap


def build(destination):
    app=QApplication.instance() or QApplication([])
    frames=[]
    for size in (16,24,32,48,64,128,256):
        data=QByteArray(); buffer=QBuffer(data); buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        logo_pixmap(size).save(buffer,'PNG'); buffer.close(); frames.append((size,bytes(data)))
    offset=6+16*len(frames); header=bytearray(struct.pack('<HHH',0,1,len(frames))); payload=bytearray()
    for size,data in frames:
        header.extend(struct.pack('<BBBBHHII',size%256,size%256,0,0,1,32,len(data),offset))
        payload.extend(data); offset+=len(data)
    path=Path(destination); path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(header+payload)


if __name__=='__main__': build(Path(__file__).resolve().parents[1]/'assets/PDFeather.ico')
