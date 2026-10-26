from PySide6.QtGui import QPalette, QColor

PALETTES={
    'dark':dict(text='#e1e6ee',window='#262c35',title='#171c24',bar='#202630',muted='#b9c2d1',input='#303844',line='#465061',hover='#394251',pressed='#495770',sidebar='#242b35',canvas='#363c45',accent='#3e506f',button_hover='#50668e',disabled='#343a43',scroll='#282f39',handle='#667081',selected='#334358',placeholder='#424a57',error='#ffaaaa'),
    'light':dict(text='#253346',window='#f4f6f8',title='#e9eef3',bar='#ffffff',muted='#526176',input='#ffffff',line='#cbd5e1',hover='#e6edf5',pressed='#d6e2ef',sidebar='#edf1f5',canvas='#d9e0e7',accent='#d8e8f3',button_hover='#c5dcec',disabled='#e4e8ed',scroll='#e9eef3',handle='#9aaabd',selected='#d3e4f4',placeholder='#c8d2de',error='#b42318')
}


def stylesheet(name):
    c=PALETTES[name]
    return f"""
QWidget {{ font-family:'Malgun Gothic','Segoe UI',sans-serif; font-size:12px; color:{c['text']}; }}
QMainWindow,QDialog,#shell {{ background:{c['window']}; }}
#titleBar {{ background:{c['title']}; }}
#brand {{ background:transparent; padding:0; }}
#windowTitle {{ color:{c['muted']}; padding-left:5px; }}
#toolbar,#footer {{ background:{c['bar']}; }}
QToolButton {{ border:0; border-radius:5px; background:transparent; }}
QToolButton:hover {{ background:{c['hover']}; }}
QToolButton:pressed {{ background:{c['pressed']}; }}
#closeButton:hover {{ background:#c42b3c; }}
QComboBox,QSpinBox,QDoubleSpinBox,QLineEdit {{ background:{c['input']}; border:1px solid {c['line']}; border-radius:5px; padding:5px 7px; selection-background-color:#586baf; }}
QComboBox QAbstractItemView {{ background:{c['input']}; selection-background-color:{c['selected']}; }}
QListWidget {{ background:{c['sidebar']}; border:0; outline:0; }}
QScrollArea {{ border:0; background:{c['canvas']}; }}
QSplitter::handle {{ background:{c['line']}; }}
QPushButton {{ background:{c['accent']}; border:0; border-radius:5px; padding:9px 15px; }}
QPushButton:hover {{ background:{c['button_hover']}; }}
QPushButton:disabled {{ background:{c['disabled']}; color:{c['muted']}; }}
QScrollBar:vertical {{ background:{c['scroll']}; width:11px; margin:0; }}
QScrollBar::handle:vertical {{ background:{c['handle']}; min-height:25px; border-radius:4px; margin:2px; }}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{ height:0; }}
QScrollBar:horizontal {{ background:{c['scroll']}; height:11px; margin:0; }}
QScrollBar::handle:horizontal {{ background:{c['handle']}; min-width:25px; border-radius:4px; margin:2px; }}
QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal {{ width:0; }}
QToolButton:checked {{ background:{c['selected']}; border:1px solid {c['line']}; }}
#captureBar {{ background:{c['bar']}; border-bottom:1px solid {c['line']}; }}
#captureBar QPushButton {{ padding:6px 10px; }}
#noticeText {{ background:{c['title']}; color:{c['text']}; border:1px solid {c['line']}; border-radius:6px; padding:9px 14px; }}
#documentTabs {{ background:transparent; border:0; }}
#documentTabs::tab {{ background:transparent; color:{c['muted']}; padding:6px 12px 6px 14px; margin:4px 3px 0 0; border:0; border-top-left-radius:7px; border-top-right-radius:7px; }}
#documentTabs::tab:selected {{ background:{c['bar']}; color:{c['text']}; border-bottom:2px solid #2ca99a; }}
#documentTabs::tab:hover {{ background:{c['hover']}; }}
#tabClose {{ border:0; border-radius:4px; }}
#viewModePicker {{ background:{c['input']}; border:1px solid {c['line']}; border-radius:8px; padding:3px 10px; text-align:left; }}
#viewModePicker:hover {{ background:{c['hover']}; }}
#viewModePicker::menu-indicator {{ subcontrol-position:right center; subcontrol-origin:padding; width:9px; height:9px; right:5px; }}
#viewModeMenu {{ background:{c['window']}; border:1px solid {c['line']}; padding:6px; }}
#viewModeMenu::item {{ padding:9px 32px 9px 28px; border-radius:5px; }}
#viewModeMenu::item:selected {{ background:{c['selected']}; }}
#sectionTitle {{ font-size:21px; font-weight:600; }}
#categoryNav {{ background:{c['title']}; padding-top:14px; }}
#categoryNav::item {{ padding:13px 16px; margin:3px 8px; border-radius:5px; }}
#categoryNav::item:selected {{ background:{c['selected']}; color:{c['text']}; }}
QToolBox::tab {{ background:{c['bar']}; border:1px solid {c['line']}; border-radius:5px; min-height:20px; color:{c['text']}; padding:8px 12px; text-align:left; }}
QToolBox::tab:selected {{ background:{c['selected']}; font-weight:600; }}
#sectionHeader {{ text-align:left; padding:8px 12px; background:{c['bar']}; border:1px solid {c['line']}; border-radius:5px; }}
#sectionHeader:checked {{ background:{c['selected']}; font-weight:600; }}
#printSection {{ background:{c['window']}; }}
#primaryButton {{ background:#187f75; color:white; font-weight:600; padding:12px; }}
#popupCard {{ background:{c['window']}; border:1px solid {c['line']}; border-radius:18px; }}
#popupTitle {{ font-size:17px; font-weight:600; padding-left:6px; }}
#popupClose {{ background:transparent; color:{c['muted']}; font-size:22px; padding:0; border-radius:16px; }}
#popupClose:hover {{ background:{c['hover']}; }}
#categoryChip {{ background:{c['bar']}; border:1px solid {c['line']}; border-radius:8px; padding:9px 6px; }}
#categoryChip:checked {{ background:{c['selected']}; border-color:#259f90; }}
#cardHeading {{ font-size:14px; font-weight:600; }}
#settingsScroll {{ background:{c['window']}; border:0; }}
#categoryNav {{ background:{c['bar']}; border-radius:12px; padding:12px 0; }}
#categoryNav::item {{ padding:12px 14px; margin:3px 10px; border-radius:8px; }}
QGroupBox {{ background:{c['bar']}; border:0; border-radius:12px; margin-top:20px; padding:18px; }}
QGroupBox::title {{ color:{c['muted']}; left:4px; font-size:11px; font-weight:600; }}
#sectionHeader {{ border:0; border-radius:8px; padding:10px 12px; }}
QProgressBar {{ background:{c['line']}; border:0; border-radius:3px; }}
QProgressBar::chunk {{ background:#259f90; border-radius:3px; }}
QWidget:disabled {{ color:{c['muted']}; }}
QTabWidget::pane {{ border:0; }}
QTabBar::tab {{ background:{c['title']}; color:{c['muted']}; padding:9px 25px; border:0; }}
QTabBar::tab:selected {{ background:{c['bar']}; color:{c['text']}; border-bottom:2px solid #2ca99a; }}

QGroupBox::title {{ subcontrol-origin:margin; padding:0 5px; }}
QCheckBox {{ spacing:8px; padding:4px 0; }}
QCheckBox::indicator {{ width:16px; height:16px; }}
#errorText {{ color:{c['error']}; }}
#mutedText {{ color:{c['muted']}; }}
"""


def apply_palette(app,name):
    c=PALETTES[name]; palette=QPalette()
    for role,key in [(QPalette.ColorRole.Window,'window'),(QPalette.ColorRole.WindowText,'text'),(QPalette.ColorRole.Base,'input'),(QPalette.ColorRole.AlternateBase,'sidebar'),(QPalette.ColorRole.Text,'text'),(QPalette.ColorRole.Button,'accent'),(QPalette.ColorRole.ButtonText,'text'),(QPalette.ColorRole.ToolTipBase,'window'),(QPalette.ColorRole.ToolTipText,'text'),(QPalette.ColorRole.PlaceholderText,'muted')]: palette.setColor(role,QColor(c[key]))
    palette.setColor(QPalette.ColorRole.Highlight,QColor('#347fba')); palette.setColor(QPalette.ColorRole.HighlightedText,QColor('#ffffff'))
    app.setPalette(palette); app.setStyleSheet(stylesheet(name))
