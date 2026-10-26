from PySide6.QtCore import QSettings, Signal, QLocale
from app_meta import VERSION,publisher_for_language
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QFormLayout,QComboBox,QCheckBox,QSpinBox,
    QDoubleSpinBox,QGroupBox,QLabel,QPushButton,QGridLayout,QHBoxLayout,QListWidget,QStackedWidget,QScrollArea)

DEFAULTS=dict(auto_update=True,render_mode='tiles',theme='dark',default_mode=1,default_fit='page',show_thumbnails=True,wheel_step=15,
    edge_flip=True,remember_geometry=True,print_paper='A4',print_duplex=0,
    margin_left=10.,margin_top=10.,margin_right=10.,margin_bottom=10.,print_gap=2.)


class Preferences:
    def __init__(self,storage=None):
        self.storage=storage if storage is not None else QSettings('PDFeather','PDFeather')

    def get(self,key):
        default=DEFAULTS[key]
        try:
            value=self.storage.value(key,default,type=type(default))
            choices=dict(render_mode=('tiles','page'),theme=('dark','light'),default_fit=('page','width','actual'),print_paper=('A4','A3','Letter','Legal'))
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
    check_update_requested=Signal()
    open_release_requested=Signal()
    def __init__(self,prefs,parent=None):
        super().__init__(parent); self.prefs=prefs; self.controls={}
        root=QHBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        self.categories=QListWidget(); self.categories.setObjectName('categoryNav'); self.categories.setFixedWidth(158)
        self.categories.addItems(['일반','문서 표시','인쇄 기본값','정보']); root.addWidget(self.categories)
        self.stack=QStackedWidget(); root.addWidget(self.stack,1)
        def page(title,description):
            content=QWidget(); layout=QVBoxLayout(content); layout.setContentsMargins(26,22,26,22); layout.setSpacing(18)
            label=QLabel(title); label.setObjectName('sectionTitle'); layout.addWidget(label)
            hint=QLabel(description); hint.setObjectName('mutedText'); hint.setWordWrap(True); layout.addWidget(hint)
            scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(content); self.stack.addWidget(scroll)
            return layout
        def group(layout,title):
            box=QGroupBox(title); form=QFormLayout(box); form.setVerticalSpacing(13); form.setHorizontalSpacing(20); layout.addWidget(box); return form
        general=page('일반','화면 테마와 앱 동작을 설정합니다. 변경 사항은 자동으로 저장됩니다.')
        appearance=group(general,'화면')
        self.combo(appearance,'테마','theme',[('다크 모드','dark'),('라이트 모드','light')])
        self.check(appearance,'왼쪽 썸네일 기본 표시','show_thumbnails')
        behavior=group(general,'시작 및 창')
        self.check(behavior,'창 위치와 크기 기억','remember_geometry')
        updates=group(general,'업데이트')
        self.check(updates,'새 버전 자동 확인 (하루 한 번)','auto_update')
        notice=QLabel('업데이트 확인에만 GitHub에 연결합니다. 문서는 전송하지 않습니다.\n인터넷이 없으면 조용히 건너뛰며 PDF 열기·인쇄는 계속 사용할 수 있습니다.'); notice.setObjectName('mutedText'); notice.setWordWrap(True); updates.addRow(notice); general.addStretch()
        reading=page('문서 표시','화질과 문서 탐색 방식을 설정합니다.')
        quality=group(reading,'렌더링 품질')
        self.combo(quality,'표시 모드','render_mode',[('선명하게 · 고해상도 타일','tiles'),('메모리 절약 · 페이지 이미지','page')])
        hint=QLabel('타일 모드는 화면에 보이는 영역을 모니터 배율에 맞춰 다시 그립니다.\n페이지 모드는 전체 이미지를 사용하며 큰 배율에서는 화질이 제한됩니다.'); hint.setObjectName('mutedText'); hint.setWordWrap(True); quality.addRow(hint)
        view=group(reading,'기본 보기')
        self.combo(view,'보기 방식','default_mode',[(v,i) for i,v in enumerate(['단일','단일 스크롤','2페이지','2페이지 스크롤'])])
        self.combo(view,'파일을 열 때 배율','default_fit',[('쪽 맞추기','page'),('너비 맞추기','width'),('실제 크기 (100%)','actual')])
        navigation=group(reading,'마우스 및 페이지 이동')
        step=QSpinBox(); step.setRange(5,50); step.setSuffix('%'); self.bind(navigation,'휠 확대·축소 단계','wheel_step',step)
        self.check(navigation,'페이지 끝에서 휠로 이전·다음 페이지 넘기기','edge_flip'); reading.addStretch()
        printing_page=page('인쇄 기본값','다음 인쇄 작업에 사용할 기본값입니다. 인쇄 창에서 작업별로 변경할 수 있습니다.')
        printing=group(printing_page,'용지와 출력')
        self.combo(printing,'용지','print_paper',[(v,v) for v in ('A4','A3','Letter','Legal')])
        self.combo(printing,'양면','print_duplex',[('단면',0),('양면 · 긴 쪽 넘김',1),('양면 · 짧은 쪽 넘김',2)])
        spacing=group(printing_page,'여백과 간격')
        for label,key in [('왼쪽','margin_left'),('오른쪽','margin_right'),('위','margin_top'),('아래','margin_bottom')]: self.bind(spacing,label,key,self.mm())
        self.bind(spacing,'모아찍기 간격','print_gap',self.mm())
        hint=QLabel('0 mm 여백 출력은 프린터의 무테 인쇄 지원이 필요합니다.'); hint.setWordWrap(True); hint.setObjectName('mutedText'); printing_page.addWidget(hint); printing_page.addStretch()
        about=page('PDFeather','가볍고 간결한 오프라인 PDF 리더')
        info=group(about,'프로그램 정보'); info.addRow('버전',QLabel(VERSION)); info.addRow('게시자',QLabel(publisher_for_language((QLocale.system().uiLanguages() or [QLocale.system().name()])[0]))); info.addRow('네트워크',QLabel('문서 열기와 인쇄에 인터넷 연결이 필요하지 않습니다.'))
        updates=group(about,'업데이트 확인')
        self.update_button=QPushButton('지금 확인'); self.update_button.clicked.connect(self.check_update_requested.emit); updates.addRow(self.update_button)
        self.update_status=QLabel('새 버전 확인은 인터넷 연결이 필요합니다.'); self.update_status.setWordWrap(True); self.update_status.setObjectName('mutedText'); updates.addRow(self.update_status)
        self.release_button=QPushButton('배포 페이지 열기'); self.release_button.clicked.connect(self.open_release_requested.emit); self.release_button.hide(); updates.addRow(self.release_button)
        reset=QPushButton('모든 설정을 기본값으로 복원'); reset.clicked.connect(self.reset); about.addWidget(reset); about.addStretch()
        self.categories.currentRowChanged.connect(self.stack.setCurrentIndex); self.categories.setCurrentRow(0)

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
        control.setMaximumWidth(290)
        if isinstance(control,QCheckBox): control.setMaximumWidth(500)
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
