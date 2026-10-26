"""Generate bilingual Windows metadata and installer version definitions."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app_meta import NAME,VERSION,PUBLISHER_EN,PUBLISHER_KO
from versioning import Version


def build(root):
    version=Version.parse(VERSION); tuple_version=(*version.core,0)
    tables=[]
    for locale,publisher in [('040904B0',PUBLISHER_EN),('041204B0',PUBLISHER_KO)]:
        entries=dict(CompanyName=publisher,FileDescription=NAME,FileVersion=VERSION,InternalName=NAME,OriginalFilename=f'{NAME}.exe',ProductName=NAME,ProductVersion=VERSION)
        items=','.join(f'StringStruct({ascii(key)}, {ascii(value)})' for key,value in entries.items())
        tables.append(f'StringTable({locale!r}, [{items}])')
    text=f"VSVersionInfo(ffi=FixedFileInfo(filevers={tuple_version!r},prodvers={tuple_version!r},mask=0x3f,flags=0,OS=0x40004,fileType=1,subtype=0,date=(0,0)),kids=[StringFileInfo([{','.join(tables)}]),VarFileInfo([VarStruct('Translation',[1033,1200,1042,1200])])])\n"
    installer=Path(root)/'installer'; installer.mkdir(parents=True,exist_ok=True)
    (installer/'version_info.txt').write_text(text,encoding='ascii')
    (installer/'version.iss').write_text(f'#define AppVersion "{VERSION}"\n#define AppPublisherEnglish "{PUBLISHER_EN}"\n#define AppPublisherKorean "{PUBLISHER_KO}"\n',encoding='utf-8-sig')

if __name__=='__main__': build(Path(__file__).resolve().parents[1])
