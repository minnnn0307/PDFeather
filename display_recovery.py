"""Rebuild device-dependent content after resume/display changes, in Qt coordinates."""
import time
from PySide6.QtCore import QObject,QTimer,QEvent
from PySide6.QtWidgets import QWidget
from branding import logo_pixmap

class DisplayRecovery(QObject):
    def __init__(self,owner):
        super().__init__(owner);self.owner=owner;self.screen=None;self.handle=None;self.suspended_view=None;self.inactive_since=None
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(180);self.timer.timeout.connect(self.refresh)
        owner.installEventFilter(self)
        self.watch_screen(owner.screen())

    def schedule(self,*args):
        if not getattr(self.owner,'closing',False):self.timer.start()

    def watch_screen(self,screen):
        if screen is self.screen:return
        if self.screen:
            try:
                self.screen.logicalDotsPerInchChanged.disconnect(self.schedule);self.screen.geometryChanged.disconnect(self.schedule)
            except (RuntimeError,TypeError):pass
        changed=self.screen is not None
        self.screen=screen
        if screen:
            screen.logicalDotsPerInchChanged.connect(self.schedule);screen.geometryChanged.connect(self.schedule)
        if changed:self.schedule()

    def eventFilter(self,obj,event):
        if obj is self.owner:
            if event.type()==QEvent.Type.Show and self.owner.windowHandle() is not self.handle:
                self.handle=self.owner.windowHandle()
                if self.handle:self.handle.screenChanged.connect(self.watch_screen)
            if event.type()==QEvent.Type.WindowDeactivate:self.inactive_since=time.monotonic()
            if event.type()==QEvent.Type.DevicePixelRatioChange:self.schedule()
            if event.type()==QEvent.Type.WindowActivate:
                if self.suspended_view or self.inactive_since is not None and time.monotonic()-self.inactive_since>30:self.schedule()
                self.inactive_since=None
        return False

    def native_message(self,message,wparam):
        if message==0x0218 and wparam==4:
            w=self.owner
            self.suspended_view=(w.doc,w.zoom,w.fit_mode,w.current,w.scroll.horizontalScrollBar().value(),w.scroll.verticalScrollBar().value())
            self.timer.stop();w.canvas.reset_zoom_rendering()
            return
        # Let Qt process WM_DPICHANGED itself, including the suggested geometry.
        if message in (0x007e,0x02e0) or message==0x0218 and wparam in (6,7,18):self.schedule()

    def refresh(self):
        w=self.owner
        if getattr(w,'closing',False):return
        if w.restoring_tab:self.schedule();return
        w.canvas.cancel_drag();w.canvas.reset_zoom_rendering()
        if w.doc:w.doc.cache.clear();w.doc.cache_bytes=0
        w.canvas.welcome_key=None
        x=w.scroll.horizontalScrollBar().value();y=w.scroll.verticalScrollBar().value()
        if self.suspended_view:
            doc,zoom,fit,current,sx,sy=self.suspended_view;self.suspended_view=None
            if w.doc is doc:
                w.zoom=zoom;w.fit_mode=fit;w.current=current;x=sx;y=sy
                w.zoom_box.blockSignals(True);w.zoom_box.setValue(round(zoom*100));w.zoom_box.blockSignals(False)
        # Activate layouts before calculating page fit; never multiply logical sizes by DPI.
        for widget in [w,*w.findChildren(QWidget)]:
            if widget.layout():widget.layout().invalidate();widget.layout().activate()
        w.titlebar.brand.setPixmap(logo_pixmap(16,w.theme_name=='dark',w.devicePixelRatioF()))
        w.suppress_scroll=True
        if w.fit_mode and w.doc:w.fit(w.fit_mode)
        else:
            w.canvas.arrange();w.scroll.horizontalScrollBar().setValue(x);w.scroll.verticalScrollBar().setValue(y)
        w.suppress_scroll=False
        w.rebuild_thumbnails();w.sync_page() if w.doc else None;w.queue_thumbs();w.frame_outline.sync()
        # Repaint all children, including the backing-store area left by the old DPI.
        for widget in [w,*w.findChildren(QWidget)]:QWidget.update(widget)
        w.repaint()
