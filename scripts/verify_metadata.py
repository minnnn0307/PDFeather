"""Verify both Windows language tables on the actual packaged EXE."""
import ctypes
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app_meta import NAME,VERSION,PUBLISHER_EN,PUBLISHER_KO


def verify(path):
    lib=ctypes.WinDLL('version',use_last_error=True)
    lib.GetFileVersionInfoSizeW.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_uint32)]; lib.GetFileVersionInfoSizeW.restype=ctypes.c_uint32
    lib.GetFileVersionInfoW.argtypes=[ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p]
    lib.VerQueryValueW.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(ctypes.c_uint)]
    handle=ctypes.c_uint32(); size=lib.GetFileVersionInfoSizeW(str(path),ctypes.byref(handle))
    if not size: raise ctypes.WinError(ctypes.get_last_error())
    data=ctypes.create_string_buffer(size)
    if not lib.GetFileVersionInfoW(str(path),0,size,data): raise ctypes.WinError(ctypes.get_last_error())
    for language,publisher in [('040904B0',PUBLISHER_EN),('041204B0',PUBLISHER_KO)]:
        expected=dict(CompanyName=publisher,FileDescription=NAME,ProductName=NAME,InternalName=NAME,OriginalFilename=NAME+'.exe',FileVersion=VERSION,ProductVersion=VERSION)
        for key,value in expected.items():
            pointer=ctypes.c_void_p(); length=ctypes.c_uint()
            if not lib.VerQueryValueW(data,f'\\StringFileInfo\\{language}\\{key}',ctypes.byref(pointer),ctypes.byref(length)): raise RuntimeError('Missing Windows metadata: '+language+'/'+key)
            actual=ctypes.wstring_at(pointer.value,length.value-1)
            if actual!=value: raise RuntimeError(f'{language}/{key}: {actual!r} != {value!r}')
    print('Bilingual application metadata verified')

if __name__=='__main__': verify(Path(sys.argv[1]).resolve())
