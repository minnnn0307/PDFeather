"""One isolated PDFium renderer, one request in flight; obsolete zooms are discarded."""
import multiprocessing
from collections import OrderedDict
from PySide6.QtCore import QObject,QTimer,Signal
from PySide6.QtGui import QImage

def worker(connection):
    doc=None;identity=None
    try:
        from main import Document
        while True:
            message=connection.recv()
            if message is None:break
            generation,path,password,key,args=message
            try:
                if identity!=(path,password):
                    if doc:doc.close()
                    doc=Document(path,password);doc.cache_limit=0;identity=(path,password)
                image=doc.tile(*args) if key[0]=='tile' else doc.image(*args,cached=False)
                rgb=image.convertToFormat(QImage.Format.Format_RGB888)
                connection.send((generation,key,rgb.width(),rgb.height(),rgb.bytesPerLine(),bytes(rgb.constBits()),None))
            except Exception as exc:connection.send((generation,key,0,0,0,b'',str(exc)))
    except (EOFError,OSError):pass
    finally:
        if doc:doc.close()
        connection.close()

class ZoomRenderer(QObject):
    ready=Signal(object,object);failed=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent);self.process=None;self.pipe=None;self.pending=False;self.pending_key=None;self.pending_generation=0;self.generation=0;self.requests=OrderedDict();self.doc=None
        self.timer=QTimer(self);self.timer.setInterval(12);self.timer.timeout.connect(self.poll)
    def invalidate(self):
        self.generation+=1;self.requests.clear()
    def offer(self,doc,requests):
        self.doc=doc;self.requests=OrderedDict((key,args) for key,args in requests if not (self.pending and self.pending_generation==self.generation and key==self.pending_key))
        self.dispatch()
    def dispatch(self):
        if self.pending or not self.requests:return
        if not self.process:
            ctx=multiprocessing.get_context('spawn');self.pipe,child=ctx.Pipe()
            self.process=ctx.Process(target=worker,args=(child,),daemon=True);self.process.start();child.close();self.timer.start()
        key,args=self.requests.popitem(last=False)
        self.pipe.send((self.generation,self.doc.path,self.doc.password,key,args));self.pending=True;self.pending_key=key;self.pending_generation=self.generation
    def poll(self):
        if not self.pipe:return
        try:
            if self.pipe.poll():
                generation,key,width,height,stride,data,error=self.pipe.recv();self.pending=False;self.pending_key=None
                if generation==self.generation:self.requests.pop(key,None)
                if generation==self.generation:
                    if error:self.failed.emit(error)
                    else:self.ready.emit(key,QImage(data,width,height,stride,QImage.Format.Format_RGB888).copy())
                self.dispatch()
            elif self.process and not self.process.is_alive():raise OSError('렌더링 작업이 종료되었습니다.')
        except (EOFError,OSError) as exc:self.close();self.failed.emit(str(exc))
    def close(self):
        self.timer.stop();self.invalidate();self.pending=False;self.doc=None
        if self.process:
            if self.process.is_alive():self.process.terminate()
            self.process.join(timeout=.2)
            if not self.process.is_alive():self.process.close()
            self.process=None
        if self.pipe:self.pipe.close();self.pipe=None
