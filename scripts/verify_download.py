"""Download an already published release with the actual Qt updater; never execute it."""
import json,sys,urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from update_install import InstallerDownload
from updates import find_update
from app_meta import REPOSITORY

def main():
    app=QApplication([])
    request=urllib.request.Request(f'https://api.github.com/repos/{REPOSITORY}/releases/tags/v1.10.1',headers={'User-Agent':'PDFeather-download-verification'})
    with urllib.request.urlopen(request,timeout=30) as response:release=json.load(response)
    info=find_update([release],'0.0.0')
    if not info:raise RuntimeError('Published fixture installer was not found')
    downloader=InstallerDownload();original=downloader.get_url
    def tracked(url,fresh=False):
        original(url,fresh)
        reply=downloader.reply
        reply.finished.connect(lambda:print(f'Download response: HTTP {downloader.http_status(reply)}',flush=True))
    downloader.get_url=tracked
    def complete(path):
        print(f'Verified SHA-256 and {Path(path).stat().st_size} bytes',flush=True);downloader.cleanup();app.exit(0)
    def fail(message):print(message,flush=True);app.exit(1)
    downloader.completed.connect(complete);downloader.failed.connect(fail)
    QTimer.singleShot(0,lambda:downloader.start(info))
    QTimer.singleShot(120000,lambda:downloader.cancel('Live download verification timed out'))
    return app.exec()
if __name__=='__main__':sys.exit(main())
