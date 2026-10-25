from PySide6.QtCore import QSettings, Signal
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QFormLayout,QComboBox,QCheckBox,QSpinBox,
    QDoubleSpinBox,QGroupBox,QLabel,QPushButton,QGridLayout)

DEFAULTS=dict(theme='dark',default_mode=1,default_fit='page',show_thumbnails=True,wheel_step=15,
    edge_flip=True,remember_geometry=True,print_paper='A4',print_duplex=0,
    margin_left=10.,margin_top=10.,margin_right=10.,margin_bottom=10.,print_gap=2.)


class Preferences:
    def __init__(self,storage=None):
        self.storage=storage if storage is not None else QSettings('PDFeather','PDFeather')

    def get(self,key):
        default=DEFAULTS[key]
        try:
            value=self.storage.value(key,default,type=type(default))
            choices=dict(theme=('dark','light'),default_fit=('page','width','actual'),print_paper=('A4','A3','Letter','Legal'))
            if key in choices and value not in choices[key]: return default
            if key=='default_mode' and not 0<=value<=3: return default
            if key=='print_duplex' and not 0<=value<=2: return default
            if key=='wheel_step' and not 5<=value<=50: return default
            if (key.startswith('margin_') or key=='print_gap') and not 0<=value<=100: return default
            return value
        except (TypeError,ValueError): return default

    def set(self,key,value):
        self.storage.setValue(key,value); self.storage.sync()


class SettingsPanel(QWidget):
    changed=Signal(str,object)
    def __init__(self,prefs,parent=None):
        super().__init__(parent); self.prefs=prefs; self.controls={}
        root=QVBoxLayout(self); root.setContentsMargins(28,20,28,24); root.setSpacing(12)
        title=QLabel('설정'); title.setStyleSheet('font-size:22px; font-weight:600;'); root.addWidget(title)
        note=QLabel('변경 사항은 즉시 적용되며 다음 실행에도 유지됩니다.'); note.setObjectName('mutedText'); root.addWidget(note)
        def group(title):
            box=QGroupBox(title); form=QFormLayout(box); form.setVerticalSpacing(10); root.addWidget(box); return form
        appearance=group('화면')
        self.combo(appearance,'테마','theme',[('다크 모드','dark'),('라이트 모드','light')])
        self.check(appearance,'왼쪽 썸네일 기본 표시','show_thumbnails')
        reading=group('문서 보기와 탐색')
        self.combo(reading,'기본 보기','default_mode',[(v,i) for i,v in enumerate(['단일','단일 스크롤','2페이지','2페이지 스크롤'])])
        self.combo(reading,'파일을 열 때 배율','default_fit',[('쪽 맞추기','page'),('너비 맞추기','width'),('실제 크기 (100%)','actual')])
        step=QSpinBox(); step.setRange(5,50); step.setSuffix('%'); self.bind(reading,'휠 확대·축소 단계','wheel_step',step)
        self.check(reading,'페이지 끝에서 휠로 이전·다음 페이지 넘기기','edge_flip')
        self.check(reading,'창 위치와 크기 기억','remember_geometry')
        printing=group('인쇄 기본값')
        self.combo(printing,'용지','print_paper',[(v,v) for v in ('A4','A3','Letter','Legal')])
        self.combo(printing,'양면','print_duplex',[('단면',0),('양면 · 긴 쪽 넘김',1),('양면 · 짧은 쪽 넘김',2)])
        margins=QWidget(); mg=QGridLayout(margins); mg.setContentsMargins(0,0,0,0)
        for i,(label,key) in enumerate([('왼쪽','margin_left'),('위','margin_top'),('오른쪽','margin_right'),('아래','margin_bottom')]):
            spin=self.mm(); self.register(key,spin); mg.addWidget(QLabel(label),i//2,(i%2)*2); mg.addWidget(spin,i//2,(i%2)*2+1)
        printing.addRow('용지 가장자리 여백',margins)
        self.bind(printing,'모아찍기 페이지 사이 간격','print_gap',self.mm())
        hint=QLabel('인쇄 창에서 이번 작업의 여백을 따로 변경할 수 있습니다.\n0 mm 여백 인쇄는 프린터의 무테 인쇄 지원이 필요합니다.'); hint.setWordWrap(True); hint.setObjectName('mutedText'); printing.addRow(hint)
        reset=QPushButton('기본 설정으로 복원'); reset.clicked.connect(self.reset); root.addWidget(reset)
        version=QLabel('PDFeather 1.1.0'); version.setObjectName('mutedText'); root.addWidget(version); root.addStretch()

    @staticmethod
    def mm():
        spin=QDoubleSpinBox(); spin.setRange(0,100); spin.setDecimals(1); spin.setSuffix(' mm'); spin.setSingleStep(1); return spin

    def combo(self,form,label,key,choices):
        box=QComboBox()
        for name,value in choices: box.addItem(name,value)
        self.register(key,box); form.addRow(label,box)

    def check(self,form,label,key):
        box=QCheckBox(label); self.register(key,box); form.addRow(box)

    def bind(self,form,label,key,control):
        self.register(key,control); form.addRow(label,control)

    def register(self,key,control):
        self.controls[key]=control; self.assign(control,self.prefs.get(key))
        def commit(*_):
            value=control.currentData() if isinstance(control,QComboBox) else control.isChecked() if isinstance(control,QCheckBox) else control.value()
            self.prefs.set(key,value); self.changed.emit(key,value)
        if isinstance(control,QComboBox): control.currentIndexChanged.connect(commit)
        elif isinstance(control,QCheckBox): control.toggled.connect(commit)
        else: control.valueChanged.connect(commit)

    @staticmethod
    def assign(control,value):
        if isinstance(control,QComboBox): control.setCurrentIndex(control.findData(value))
        elif isinstance(control,QCheckBox): control.setChecked(value)
        else: control.setValue(value)

    def reset(self):
        for key,control in self.controls.items(): self.assign(control,DEFAULTS[key])
