"""One GUI per user/session; subsequent launches forward PDF paths over local IPC."""
import ctypes
import getpass
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from PySide6.QtCore import QObject,Signal,QLockFile,QStandardPaths,QThread
from PySide6.QtNetwork import QLocalServer,QLocalSocket

MAX_MESSAGE=1024*1024


def session_key():
    identity=f'{os.environ.get("USERDOMAIN", "")}:{getpass.getuser()}:{getattr(os,"getuid",lambda:0)()}'
    if sys.platform=='win32':
        session=ctypes.c_uint32()
        if ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(),ctypes.byref(session)): identity+=f':{session.value}'
    return 'PDFeather-'+hashlib.sha256(identity.lower().encode()).hexdigest()[:24]


def encode_paths(paths):
    normalized=[str(Path(p).resolve()) for p in paths]
    validate_paths(normalized)
    content=json.dumps({'paths':normalized},ensure_ascii=False).encode('utf-8')+b'\n'
    if len(content)>MAX_MESSAGE: raise ValueError('한 번에 여는 파일이 너무 많습니다.')
    return content


def validate_paths(paths):
    if not isinstance(paths,list) or len(paths)>256: raise ValueError('Invalid paths')
    for path in paths:
        if not isinstance(path,str) or '\x00' in path or len(path)>32767 or not Path(path).is_absolute() or Path(path).suffix.lower()!='.pdf': raise ValueError('Invalid PDF path')


class SingleInstance(QObject):
    paths_received=Signal(list)
    def __init__(self,parent=None,name=None,directory=None):
        super().__init__(parent)
        self.name=name or session_key()
        location=Path(directory or QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
        location.mkdir(parents=True,exist_ok=True)
        lock_name=hashlib.sha256(self.name.encode()).hexdigest()[:24]+'.lock'
        self.lock=QLockFile(str(location/lock_name)); self.lock.setStaleLockTime(0)
        self.server=QLocalServer(self); self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption); self.server.newConnection.connect(self.accept)
        self.owner=False; self.connections=set()

    def start_or_forward(self,paths):
        packet=encode_paths(paths)
        if self.lock.tryLock(0):
            self.owner=True
            # Only the lock owner can remove an endpoint left by a crashed instance.
            QLocalServer.removeServer(self.name)
            if not self.server.listen(self.name):
                self.close(); raise RuntimeError('PDFeather 로컬 연결을 열 수 없습니다.')
            return True
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            socket=QLocalSocket(); socket.connectToServer(self.name)
            if socket.waitForConnected(150):
                socket.write(packet)
                if socket.bytesToWrite() and not socket.waitForBytesWritten(2000):
                    socket.abort(); raise RuntimeError('기존 PDFeather에 파일을 전달할 수 없습니다.')
                if socket.waitForReadyRead(3000):
                    try:
                        response=json.loads(bytes(socket.readLine()))
                        if sys.platform=='win32' and isinstance(response.get('pid'),int): ctypes.windll.user32.AllowSetForegroundWindow(response['pid'])
                    except (ValueError,TypeError): pass
                socket.disconnectFromServer()
                return False
            socket.abort(); QThread.msleep(30)
        raise RuntimeError('기존 PDFeather가 시작 중이거나 응답하지 않습니다. 잠시 후 다시 열어 주세요.')

    def accept(self):
        while self.server.hasPendingConnections():
            socket=self.server.nextPendingConnection(); self.connections.add(socket); buffer=bytearray()
            def consume(sock=socket,data=buffer):
                if sock.property('handled'): return
                data.extend(bytes(sock.readAll()))
                if len(data)>MAX_MESSAGE:
                    sock.abort(); return
                if b'\n' not in data: return
                sock.setProperty('handled',True)
                try:
                    payload=json.loads(bytes(data).split(b'\n',1)[0]); paths=payload['paths']; validate_paths(paths)
                    sock.write(json.dumps({'pid':os.getpid()}).encode()+b'\n'); sock.flush()
                    self.paths_received.emit(paths)
                except (ValueError,TypeError,KeyError): sock.abort()
            def disconnected(sock=socket):
                self.connections.discard(sock); sock.deleteLater()
            socket.readyRead.connect(consume); socket.disconnected.connect(disconnected); consume()

    def close(self):
        for socket in list(self.connections): socket.abort()
        self.connections.clear(); self.server.close()
        if self.owner: self.lock.unlock(); self.owner=False
