"""SemVer 2.0.0 parsing and precedence; build metadata does not affect ordering."""
import re
from dataclasses import dataclass
from functools import total_ordering

_PATTERN=re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?')

@total_ordering
@dataclass(frozen=True,eq=False)
class Version:
    major:int
    minor:int
    patch:int
    prerelease:tuple=()

    @classmethod
    def parse(cls,text):
        if not isinstance(text,str): raise ValueError('Invalid semantic version')
        match=_PATTERN.fullmatch(text.removeprefix('v'))
        if not match: raise ValueError('Invalid semantic version')
        pre=tuple(match.group(4).split('.')) if match.group(4) else ()
        if any(part.isdigit() and len(part)>1 and part[0]=='0' for part in pre): raise ValueError('Invalid prerelease identifier')
        return cls(*(int(match.group(i)) for i in (1,2,3)),pre)

    @property
    def core(self): return self.major,self.minor,self.patch

    def __eq__(self,other):
        if not isinstance(other,Version): return NotImplemented
        return self.core==other.core and self.prerelease==other.prerelease

    def __lt__(self,other):
        if not isinstance(other,Version): return NotImplemented
        if self.core!=other.core: return self.core<other.core
        if not self.prerelease: return False
        if not other.prerelease: return True
        for left,right in zip(self.prerelease,other.prerelease):
            if left==right: continue
            ln,rn=left.isdigit(),right.isdigit()
            if ln and rn: return int(left)<int(right)
            if ln!=rn: return ln
            return left<right
        return len(self.prerelease)<len(other.prerelease)
