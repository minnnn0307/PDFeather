import json,hashlib,os,time,math
from pathlib import Path
from PySide6.QtCore import QSettings, Signal, QLocale, Qt
from app_meta import VERSION,publisher_for_language
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QFormLayout,QComboBox,QCheckBox,QSpinBox,
    QDoubleSpinBox,QGroupBox,QLabel,QPushButton,QGridLayout,QHBoxLayout,QListWidget,QStackedWidget,QScrollArea)

DEFAULTS=dict(auto_update=True,optimization=False,render_mode='tiles',theme='dark',default_mode=1,default_fit='page',show_thumbnails=True,wheel_step=15,scroll_step=100,
    edge_flip=True,remember_document=True,remember_geometry=True,print_paper='A4',print_duplex=0,
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
            if key=='scroll_step' and not 20<=value<=600: return default
            if (key.startswith('margin_') or key=='print_gap') and not 0<=value<=100: return default
            return value
        except (TypeError,ValueError): return default

    def set(self,key,value):
        self.storage.setValue(key,value); self.storage.sync()

    def document_key(self,path):
        return 'document_positions/'+hashlib.sha256(os.path.normcase(str(Path(path).resolve())).encode('utf-8')).hexdigest()

    def save_document(self,state):
        if not self.get('remember_document'): return
        try:
            stat=Path(state.doc.path).stat()
            data=dict(size=stat.st_size,mtime=stat.st_mtime_ns,current=state.current,zoom=state.zoom,
                mode=state.mode,x=state.scroll_x,y=state.scroll_y,saved=time.time())
            self.storage.setValue(self.document_key(state.doc.path),json.dumps(data))
            keys=[k for k in self.storage.allKeys() if k.startswith('document_positions/')]
            if len(keys)>200:
                def age(key):
                    try: return json.loads(self.storage.value(key))['saved']
                    except (ValueError,TypeError,KeyError): return 0
                for key in sorted(keys,key=age)[:-200]: self.storage.remove(key)
            self.storage.sync()
        except (OSError,ValueError,TypeError): pass

    def restore_document(self,state):
        if not self.get('remember_document'): return
        try:
            data=json.loads(self.storage.value(self.document_key(state.doc.path),'')); stat=Path(state.doc.path).stat()
            zoom=float(data['zoom']); mode=int(data['mode']); current=int(data['current'])
            if (data['size'],data['mtime'])!=(stat.st_size,stat.st_mtime_ns): return
            if not math.isfinite(zoom) or not .1<=zoom<=10 or not 0<=mode<=3 or not 0<=current<len(state.doc.sizes): return
            x,y=int(data['x']),int(data['y'])
            if not 0<=x<=2147483647 or not 0<=y<=2147483647: return
            state.current=current; state.zoom=zoom; state.mode=mode; state.fit_mode=None
            state.scroll_x=x; state.scroll_y=y; state.initialized=True
        except (OSError,ValueError,TypeError,KeyError,OverflowError): pass


class SettingsPanel(QWidget):
    changed=Signal(str,object)
    check_update_requested=Signal()
    open_release_requested=Signal()
    def __init__(self,prefs,parent=None):
        super().__init__(parent); self.prefs=prefs; self.controls={}
        root=QHBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        self.categories=QListWidget(); self.categories.setObjectName('categoryNav'); self.categories.setFixedWidth(158)
        self.categories.addItems(['일반','문서 표시','인쇄 기본값','도움말','정보']); root.addWidget(self.categories)
        self.stack=QStackedWidget(); root.addWidget(self.stack,1)
        def page(title,description):
            content=QWidget(); layout=QVBoxLayout(content); layout.setContentsMargins(26,22,26,22); layout.setSpacing(18)
            label=QLabel(title); label.setObjectName('sectionTitle'); layout.addWidget(label)
            hint=QLabel(description); hint.setObjectName('mutedText'); hint.setWordWrap(True); layout.addWidget(hint)
            scroll=QScrollArea(); scroll.setObjectName('settingsScroll'); scroll.setWidgetResizable(True); scroll.setWidget(content); self.stack.addWidget(scroll)
            return layout
        def group(layout,title):
            box=QGroupBox(title); form=QFormLayout(box); form.setVerticalSpacing(16); form.setHorizontalSpacing(20); layout.addWidget(box); return form
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
        performance=group(reading,'성능 최적화')
        self.check(performance,'극한 메모리 절약 모드','optimization')
        note=QLabel('화면 캐시 8 MiB, 썸네일 기본 12개, 미리 로딩·전환 효과 축소. 고해상도 화면의 표시 해상도와 페이지 이미지 품질을 낮춰 메모리를 절약합니다. 문서 자체와 인쇄·캡처 원본 품질은 유지됩니다.'); note.setWordWrap(True); note.setObjectName('mutedText'); performance.addRow(note)
        quality=group(reading,'렌더링 품질')
        self.combo(quality,'표시 모드','render_mode',[('선명하게 · 고해상도 타일','tiles'),('메모리 절약 · 페이지 이미지','page')])
        hint=QLabel('타일 모드는 화면에 보이는 영역을 모니터 배율에 맞춰 다시 그립니다.\n페이지 모드는 전체 이미지를 사용하며 큰 배율에서는 화질이 제한됩니다.'); hint.setObjectName('mutedText'); hint.setWordWrap(True); quality.addRow(hint)
        view=group(reading,'기본 보기')
        self.combo(view,'보기 방식','default_mode',[(v,i) for i,v in enumerate(['단일','단일 스크롤','2페이지','2페이지 스크롤'])])
        self.combo(view,'파일을 열 때 배율','default_fit',[('쪽 맞추기','page'),('너비 맞추기','width'),('실제 크기 (100%)','actual')])
        memory=group(reading,'이어서 읽기')
        self.check(memory,'문서별 마지막 위치와 배율 기억','remember_document')
        hint=QLabel('같은 파일을 다시 열면 마지막 보기 방식·위치·배율을 복원합니다. 끄면 기본 보기로 열립니다. 최대 200개 문서를 이 컴퓨터에 기억합니다.'); hint.setWordWrap(True); hint.setObjectName('mutedText'); memory.addRow(hint)
        navigation=group(reading,'마우스 및 페이지 이동')
        step=QSpinBox(); step.setRange(5,50); step.setSuffix('%'); self.bind(navigation,'휠 확대·축소 단계','wheel_step',step)
        distance=QSpinBox(); distance.setRange(20,600); distance.setSingleStep(10); distance.setSuffix(' px'); self.bind(navigation,'휠 한 칸 이동량','scroll_step',distance)
        hint=QLabel('문서와 썸네일에 함께 적용됩니다. 터치패드의 정밀 스크롤은 기기 동작을 유지합니다.'); hint.setWordWrap(True); hint.setObjectName('mutedText'); navigation.addRow(hint)
        self.check(navigation,'페이지 끝에서 휠로 이전·다음 페이지 넘기기','edge_flip'); reading.addStretch()
        printing_page=page('인쇄 기본값','다음 인쇄 작업에 사용할 기본값입니다. 인쇄 창에서 작업별로 변경할 수 있습니다.')
        printing=group(printing_page,'용지와 출력')
        self.combo(printing,'용지','print_paper',[(v,v) for v in ('A4','A3','Letter','Legal')])
        self.combo(printing,'양면','print_duplex',[('단면',0),('양면 · 긴 쪽 넘김',1),('양면 · 짧은 쪽 넘김',2)])
        spacing=group(printing_page,'여백과 간격')
        for label,key in [('왼쪽','margin_left'),('오른쪽','margin_right'),('위','margin_top'),('아래','margin_bottom')]: self.bind(spacing,label,key,self.mm())
        self.bind(spacing,'모아찍기 간격','print_gap',self.mm())
        hint=QLabel('0 mm 여백 출력은 프린터의 무테 인쇄 지원이 필요합니다.'); hint.setWordWrap(True); hint.setObjectName('mutedText'); printing_page.addWidget(hint); printing_page.addStretch()
        self.help_index=self.stack.count()
        help_page=page('도움말','단축키와 문서 도구 사용 방법입니다. F1로 바로 열 수 있습니다.')
        guide=QLabel('Ctrl+O  파일 열기\nCtrl+P  인쇄\nCtrl+F  찾기\nCtrl+C  선택한 텍스트 / 다중캡처 복사\nCtrl+W  문서 탭 닫기\nCtrl+Tab / Ctrl+Shift+Tab  다음·이전 탭\nCtrl+,  설정\nEnter / F3  다음 결과\nShift+Enter / Shift+F3  이전 결과\nEsc  찾기 닫기\nCtrl+휠  포인터 기준 확대·축소\nCtrl++ / Ctrl+−  확대·축소\nCtrl+0  쪽 맞추기\nCtrl+1  너비 맞추기\nPageUp / PageDown  이전·다음 페이지\n\n일반 포인터: 선택·캡처 없이 문서 보기\n손 도구: 마우스를 누르고 끌어 화면 이동\n텍스트 선택: 드래그 후 Ctrl+C 또는 우클릭 복사\n영역 캡처: 드래그 후 이미지가 바로 복사됩니다.\n다중캡처: 드래그 → 스크롤 → 다시 드래그 → 이어붙여 복사\n마지막 취소 / 초기화 / 미리보기 사용 가능\n\n단일 / 2페이지 보기: 맨 아래에서 휠을 더 내리면 다음 페이지, 맨 위에서 올리면 이전 페이지\n제목 표시줄: 끌어서 이동, 두 번 클릭으로 최대화 / 복원\n창 가장자리와 오른쪽 아래에서 크기 조절'); guide.setWordWrap(True); guide.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); help_page.addWidget(guide); help_page.addStretch()
        about=page('PDFeather','가볍고 간결한 오프라인 PDF 리더')
        info=group(about,'프로그램 정보'); info.addRow('버전',QLabel(VERSION)); info.addRow('게시자',QLabel(publisher_for_language((QLocale.system().uiLanguages() or [QLocale.system().name()])[0]))); info.addRow('네트워크',QLabel('문서 열기와 인쇄에 인터넷 연결이 필요하지 않습니다.'))
        updates=group(about,'업데이트 확인')
        self.update_button=QPushButton('지금 확인'); self.update_button.clicked.connect(self.check_update_requested.emit); updates.addRow(self.update_button)
        self.update_status=QLabel('새 버전 확인은 인터넷 연결이 필요합니다.'); self.update_status.setWordWrap(True); self.update_status.setObjectName('mutedText'); updates.addRow(self.update_status)
        self.release_button=QPushButton('업데이트 설치'); self.release_button.clicked.connect(self.open_release_requested.emit); self.release_button.hide(); updates.addRow(self.release_button)
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
