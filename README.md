# PDFeather

오프라인 Windows 10/11 x64 PDF 리더. Python을 설치하지 않은 PC에서도 설치본 실행이 가능합니다. 브라우저 엔진, 서버, 로그인, 원격 API, 자동 업데이트가 없습니다. 빌드할 때만 인터넷이 필요합니다.

## 기능

- Ctrl+마우스 휠: 마우스 포인터 기준 확대/축소 (10~500%), 하단 오른쪽 배율 입력과 +/- 버튼
- 쪽 맞추기 / 너비 맞추기, 창 크기 변경 시 맞춤 유지
- 통합 제목 표시줄: 최소화 / 최대화·복원 / 종료, 제목줄 이동·더블클릭, 가장자리 크기 조절
- 아이콘 도구막대와 도움말(F1), 하단 왼쪽 안내 문구 제거
- 단일 / 단일 스크롤 / 2페이지 / 2페이지 스크롤. 문서 외곽 여백·테두리 제거, 연속 보기에는 얇은 페이지 경계선
- 단일 / 2페이지 보기에서 맨 아래에서 휠을 더 내리면 다음 페이지, 맨 위에서 올리면 이전 페이지
- 하단 가운데 현재 페이지 / 전체 페이지 및 번호 입력 이동
- 왼쪽 스크롤 썸네일, 클릭 이동, 보이는 썸네일부터 생성. 하단 중앙의 반투명 배경 페이지 번호
- Ctrl+F 텍스트 찾기, 검색 결과 강조, Enter/F3 다음 결과, Shift+Enter/Shift+F3 이전 결과, Esc 닫기
- PDF 메타데이터, 파일 크기, 페이지 크기 확인
- 암호 PDF 열기, 드래그 앤 드롭, Ctrl+O, Ctrl+P
- 별도 프로세스에서 프린터 조회·인쇄·미리보기 생성. 선택한 용지 한 면씩 미리보기와 이전/다음 이동, 작업 중단
- 인쇄 미리보기: 단면 / 양면 긴 쪽·짧은 쪽, 가로 / 세로, A4 / A3 / Letter / Legal
- 한 면에 1 / 2 / 4 / 6 / 9 / 16페이지, 페이지 범위, 매수
- 용지에 맞춤 / 실제 크기 / 10~400% 사용자 인쇄 배율

화면 캐시는 64 MiB로 제한하며 개별 비트맵은 1,600만 픽셀 이하입니다. PDF 자체와 Qt 런타임 메모리는 별도입니다. Qt/Python 런타임이 포함되므로 설치 용량이 몇 MB 수준인 초소형 네이티브 앱은 아닙니다. 실제 크기와 시작 시간은 Windows 빌드 후 측정해야 합니다. 무거운 문서는 렌더링 중 UI가 잠시 멈출 수 있습니다. 인쇄는 최대 300dpi의 래스터 출력이며 텍스트 벡터를 보존하지 않습니다.

## 개발 실행

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
python -m unittest discover -s tests -v
```

## GitHub 연결 및 설치 EXE 만들기

1. GitHub에서 빈 저장소를 생성합니다. 이 ZIP을 풀고 README.md와 .github 폴더가 있는 폴더에서 아래를 실행합니다.

```powershell
git init
git add .
git commit -m "Initial offline PDF reader"
git branch -M main
git remote add origin https://github.com/minnnn0307/PDFeather.git
git push -u origin main
```

2. GitHub Actions의 **Windows installer** 빌드가 완료되면 **Artifacts → PDFeather-1.0.0-Windows-x64**에서 압축 파일을 내려받습니다. `release/PDFeather-1.0.0-Setup.exe`가 설치 프로그램입니다. `dist/PDFeather` 폴더 전체는 무설치 실행용입니다.
3. 버전 배포: `git tag v1.0.0` 후 `git push origin v1.0.0`을 실행하면 설치 EXE가 GitHub Release에 첨부됩니다. 저장소의 Actions 실행/쓰기 권한 정책이 허용되어야 합니다.

서명 인증서는 포함되어 있지 않습니다. 서명 없는 설치 EXE에는 Windows 보안 경고가 표시될 수 있습니다. GitHub 저장소: https://github.com/minnnn0307/PDFeather

## Windows 로컬 설치본 빌드

Python 3.12 x64와 Inno Setup 6 설치 후:

```powershell
pip install -r requirements-build.txt
# 배포본에는 THIRD_PARTY_NOTICES.md와 각 의존성의 라이선스를 함께 포함하세요.
pyinstaller --noconfirm --clean --windowed --onedir --name PDFeather --version-file installer/version_info.txt --collect-all pypdfium2 main.py
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" installer/setup.iss
```

배포용 라이선스 수집은 GitHub Actions에서 자동 처리하므로 Actions 경로를 권장합니다.

## 검증 상태와 제한

자동 검사: 페이지 범위 오류, N-up 배치 계산, 실제 5페이지 PDF 열기/렌더링, 네 가지 보기 모드, 포인터 기준 확대 좌표 보존, 페이지 끝 휠 넘김, 텍스트 검색 결과, 2-up 출력 PDF의 3장 생성, 인쇄 미리보기 중 이벤트 루프 응답. Linux와 GitHub Actions의 Windows offscreen Qt 환경에서 수행합니다. 빌드된 Windows EXE 자체에서도 별도 프로세스 미리보기가 생성되는지 검사합니다. Windows 설치/제거, 프린터 드라이버별 양면·매수·용지 적용, 큰 문서 성능은 실제 Windows 장치에서 추가 확인해야 합니다. 양면 기능은 드라이버와 프린터 지원에 따릅니다. 미리보기는 레이아웃을 보여주며 프린터의 물리적 양면 동작은 재현하지 않습니다.

검색은 PDF 텍스트 레이어를 대상으로 하며 OCR은 포함하지 않습니다. 검색 결과는 최대 10,000개입니다. 프린터 조회가 오래 걸리면 제한 시간 후 미리보기로 이동하며 다시 조회할 수 있습니다. 인쇄 중단 전에 Windows 대기열로 전송된 작업은 대기열에서 취소해야 합니다.
