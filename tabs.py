"""Per-document state; shared reader widgets only render the active document."""
from dataclasses import dataclass,field

@dataclass
class DocumentTab:
    doc: object
    selection: object
    current: int=0
    zoom: float=1.
    fit_mode: object='page'
    mode: int=1
    scroll_x: int=0
    scroll_y: int=0
    initialized: bool=False
    search_query: str=''
    search_input: str=''
    search_visible: bool=False
    search_page: int=0
    matches: list=field(default_factory=list)
    match_index: int=-1
