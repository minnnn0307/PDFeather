"""Deterministic PDF with a searchable standard-font text layer on every OS."""
import sys
from pathlib import Path


def create_pdf(path, count=4, background=False):
    objects=[b'', b'']
    pages=[]
    for index in range(count):
        page_id=len(objects)+1; content_id=page_id+1
        pages.append(page_id)
        prefix='0.2 0.2 0.2 rg 0 0 595 842 re f 1 1 1 rg ' if background else ''
        content=(prefix+f'BT /F1 24 Tf 72 740 Td (Page {index+1} PDFeather print preview test) Tj ET').encode('ascii')
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> /Contents {content_id} 0 R >>'.encode('ascii'))
        objects.append(b'<< /Length '+str(len(content)).encode()+b' >>\nstream\n'+content+b'\nendstream')
    objects[0]=b'<< /Type /Catalog /Pages 2 0 R >>'
    objects[1]=f'<< /Type /Pages /Count {count} /Kids [ {" ".join(f"{p} 0 R" for p in pages)} ] >>'.encode('ascii')
    data=bytearray(b'%PDF-1.4\n'); offsets=[0]
    for index,obj in enumerate(objects,1):
        offsets.append(len(data)); data.extend(f'{index} 0 obj\n'.encode()+obj+b'\nendobj\n')
    start=len(data)
    data.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]: data.extend(f'{offset:010d} 00000 n \n'.encode())
    data.extend(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode())
    target=Path(path); target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(data)


if __name__=='__main__': create_pdf(sys.argv[1])
