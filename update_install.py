"""Explicit, HTTPS-only, streamed installer download with size and SHA-256 checks."""
import hashlib,re,os,subprocess,sys,tempfile
from pathlib import Path
from PySide6.QtCore import QObject,Signal,QTimer,QUrl
from PySide6.QtNetwork import QNetworkAccessManager,QNetworkRequest,QNetworkReply
from app_meta import NAME,REPOSITORY
from versioning import Version
MAX_INSTALLER=256*1024*1024

def validate_asset(info):
    Version.parse(info.version)
    expected=f'https://github.com/{REPOSITORY}/releases/download/v{info.version}/{NAME}-{info.version}-Setup.exe'
    if info.download_url!=expected or not re.fullmatch(r'[a-fA-F0-9]{64}',info.sha256) or not isinstance(info.size,int) or not 0<info.size<=MAX_INSTALLER:
        raise ValueError('검증 가능한 설치 파일 정보가 없습니다. 배포 페이지를 이용하세요.')
    return expected

def launch_installer(path):
    if sys.platform!='win32':raise OSError('자동 설치는 Windows에서 지원됩니다.')
    if not getattr(sys,'frozen',False):raise OSError('자동 설치는 설치된 PDFeather에서 지원됩니다.')
    subprocess.Popen([str(path),'/SILENT','/SUPPRESSMSGBOXES','/NORESTART','/CLOSEAPPLICATIONS','/PDFEATHERUPDATE=1'],close_fds=True)

class InstallerDownload(QObject):
    progress=Signal(int,int);completed=Signal(str);failed=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent);self.manager=QNetworkAccessManager(self);self.reply=None;self.file=None;self.path=None;self.error='';self.received=0
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(300000);self.timer.timeout.connect(lambda:self.cancel('다운로드 시간이 초과되었습니다.'))
    def start(self,info):
        if self.reply:return
        try:
            url=validate_asset(info);self.info=info;self.error='';self.received=0;self.digest=hashlib.sha256()
            folder=Path(tempfile.mkdtemp(prefix='pdfeather-update-'));self.path=folder/f'PDFeather-{info.version}-Setup.exe';self.file=self.path.open('xb')
            request=QNetworkRequest(QUrl(url));request.setTransferTimeout(30000)
            request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
            self.reply=self.manager.get(request)
            if hasattr(self.reply,'setReadBufferSize'):self.reply.setReadBufferSize(256*1024)
            self.reply.readyRead.connect(self.read);self.reply.finished.connect(self.finish);self.timer.start()
        except Exception as exc:self.cleanup();self.failed.emit(str(exc))
    def read(self):
        if not self.reply or self.error:return
        try:
            data=bytes(self.reply.readAll());self.received+=len(data)
            if self.received>self.info.size or self.received>MAX_INSTALLER:raise ValueError('설치 파일 크기가 배포 정보와 다릅니다.')
            self.file.write(data);self.digest.update(data);self.progress.emit(self.received,self.info.size)
        except Exception as exc:
            self.error=str(exc)
            QTimer.singleShot(0,lambda:self.reply.abort() if self.reply else None)
    def cancel(self,message='다운로드를 취소했습니다.'):
        self.error=message
        if self.reply:self.reply.abort()
        else:self.cleanup()
    def cleanup(self):
        if self.file:self.file.close();self.file=None
        if self.path:
            self.path.unlink(missing_ok=True)
            try:self.path.parent.rmdir()
            except OSError:pass
    def finish(self):
        reply=self.reply
        if reply is None:return
        outcome=None;failure=None
        try:
            self.read()
            if self.error:raise ValueError(self.error)
            if reply.error()!=QNetworkReply.NetworkError.NoError:raise ValueError('설치 파일을 내려받지 못했습니다. 인터넷 연결을 확인하세요.')
            if reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)!=200:raise ValueError('다운로드 서버 응답이 올바르지 않습니다.')
            self.file.close();self.file=None
            if self.received!=self.info.size or self.digest.hexdigest().lower()!=self.info.sha256.lower():raise ValueError('설치 파일 검증에 실패했습니다. 다시 시도하세요.')
            outcome=str(self.path)
        except Exception as exc:self.cleanup();failure=str(exc)
        finally:self.reply=None;self.timer.stop();reply.deleteLater()
        if outcome:self.completed.emit(outcome)
        else:self.failed.emit(failure)
