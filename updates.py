"""Asynchronous, bounded, stable-release notifications. Never downloads or executes installers."""
import json
from dataclasses import dataclass
from urllib.parse import quote
from PySide6.QtCore import QObject,Signal,QUrl,QTimer
from PySide6.QtNetwork import QNetworkAccessManager,QNetworkRequest,QNetworkReply
from app_meta import VERSION,NAME,REPOSITORY,RELEASES_URL
from versioning import Version

MAX_RESPONSE=4*1024*1024
API_URL=f'https://api.github.com/repos/{REPOSITORY}/releases?per_page=20'

@dataclass(frozen=True)
class UpdateInfo:
    version:str
    url:str


def find_update(data,current=VERSION):
    if not isinstance(data,list): raise ValueError('업데이트 정보를 읽을 수 없습니다.')
    installed=Version.parse(current); candidates=[]
    for release in data:
        if not isinstance(release,dict) or release.get('draft') or release.get('prerelease'): continue
        tag=release.get('tag_name','')
        try: version=Version.parse(tag)
        except ValueError: continue
        if version.prerelease or version<=installed: continue
        number=tag.removeprefix('v')
        assets=release.get('assets',[])
        if not isinstance(assets,list) or not any(isinstance(a,dict) and a.get('name')==f'{NAME}-{number}-Setup.exe' and a.get('state')=='uploaded' for a in assets): continue
        candidates.append((version,UpdateInfo(number,f'{RELEASES_URL}/tag/{quote(tag,safe="")}')))
    return max(candidates,key=lambda item:item[0])[1] if candidates else None


class UpdateChecker(QObject):
    completed=Signal(object)
    failed=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent); self.manager=QNetworkAccessManager(self); self.reply=None; self.cancelled=False; self.too_large=False
        self.deadline=QTimer(self); self.deadline.setSingleShot(True); self.deadline.setInterval(8000); self.deadline.timeout.connect(self.timeout)

    @property
    def busy(self): return self.reply is not None

    def check(self):
        if self.busy: return False
        self.cancelled=False; self.too_large=False
        request=QNetworkRequest(QUrl(API_URL)); request.setRawHeader(b'Accept',b'application/vnd.github+json'); request.setRawHeader(b'User-Agent',f'{NAME}/{VERSION}'.encode('ascii')); request.setTransferTimeout(5000)
        self.reply=self.manager.get(request); self.reply.downloadProgress.connect(self.progress); self.reply.finished.connect(self.finished); self.deadline.start(); return True

    def progress(self,received,total):
        if max(received,total)>MAX_RESPONSE and self.reply:
            self.too_large=True; self.reply.abort()

    def timeout(self):
        if self.reply: self.reply.abort()

    def cancel(self):
        self.cancelled=True; self.deadline.stop()
        if self.reply: self.reply.abort()

    def finished(self):
        reply=self.reply
        if reply is None: return
        self.reply=None; self.deadline.stop()
        try:
            if self.cancelled: return
            status=reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if status==404: self.completed.emit(None); return
            if self.too_large: raise ValueError('업데이트 정보가 너무 큽니다.')
            if reply.error()!=QNetworkReply.NetworkError.NoError: raise ValueError('업데이트를 확인하지 못했습니다. 인터넷 연결을 확인한 뒤 다시 시도하세요.')
            content=bytes(reply.readAll())
            if len(content)>MAX_RESPONSE: raise ValueError('업데이트 정보가 너무 큽니다.')
            self.completed.emit(find_update(json.loads(content)))
        except (ValueError,TypeError,KeyError): self.failed.emit('업데이트를 확인하지 못했습니다. 인터넷 연결을 확인한 뒤 다시 시도하세요.')
        finally: reply.deleteLater()
