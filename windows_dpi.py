"""Refresh Qt's Windows monitor data using its normal settings-change path."""
import ctypes,sys
from PySide6.QtWidgets import QApplication

def native_monitor_scale(owner):
    if sys.platform!='win32' or QApplication.platformName()!='windows':return None
    try:
        user=ctypes.windll.user32
        user.MonitorFromWindow.argtypes=[ctypes.c_void_p,ctypes.c_uint];user.MonitorFromWindow.restype=ctypes.c_void_p
        monitor=user.MonitorFromWindow(int(owner.winId()),2)
        get=ctypes.windll.shcore.GetDpiForMonitor
        get.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.POINTER(ctypes.c_uint),ctypes.POINTER(ctypes.c_uint)];get.restype=ctypes.c_long
        x=ctypes.c_uint();y=ctypes.c_uint()
        if monitor and get(monitor,0,ctypes.byref(x),ctypes.byref(y))==0 and 48<=x.value<=960:return x.value/96.
    except (AttributeError,OSError):pass
    return None

def refresh_monitor_data(owner):
    if sys.platform!='win32' or QApplication.platformName()!='windows':return False
    try:
        send=ctypes.windll.user32.SendMessageW
        send.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_size_t,ctypes.c_ssize_t];send.restype=ctypes.c_ssize_t
        # Qt 6.8's SettingChangedEvent calls QWindowsScreenManager::handleScreenChanges,
        # re-enumerating monitors and notifying QScreen of effective DPI changes.
        # Only this application's HWND is notified; no system settings are changed.
        send(int(owner.winId()),0x001a,0,0)
        return True
    except (AttributeError,OSError):return False
