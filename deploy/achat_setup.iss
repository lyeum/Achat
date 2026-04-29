; Inno Setup 6 — Achat 설치 스크립트
;
; 빌드 전 준비:
;   - dist\Achat.exe   : PyInstaller 빌드 결과물 (build_installer.bat가 자동 생성)
;   - dist\uv.exe      : https://github.com/astral-sh/uv/releases 에서 다운로드
;   - 소스 파일 전체   : 프로젝트 루트 기준으로 상대 경로 참조
;
; 빌드: iscc.exe achat_setup.iss
; 출력: dist\AchatSetup.exe

#define MyAppName      "Achat"
#define MyAppVersion   "0.1.0"
#define MyAppPublisher "lyeum"
#define MyAppURL       "https://github.com/lyeum/Achat"
#define MyAppExeName   "Achat.exe"

; 빌드 루트: achat_setup.iss 가 위치한 deploy\ 의 한 단계 위 (프로젝트 루트)
#define SrcRoot ".."

[Setup]
AppId={{E3A1F2B4-9C8D-4E7F-A6B5-1D2C3E4F5A6B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases

; 기본 설치 경로: C:\Achat (시스템 드라이브 루트 / 사용자 변경 가능)
DefaultDirName={sd}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes

; 언인스톨러 등록 (제어판 "프로그램 추가/제거")
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}

; 출력
OutputDir=dist
OutputBaseFilename=AchatSetup
SetupIconFile={#SrcRoot}\ui_ux\assets\icons\app.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

; 권한: 현재 사용자만 설치 (UAC 불필요)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; 최소 요구 사항
MinVersion=10.0

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon";    Description: "바탕화면에 바로가기 만들기";  GroupDescription: "추가 작업:"; Flags: unchecked
Name: "startmenuicon";  Description: "시작 메뉴에 바로가기 만들기"; GroupDescription: "추가 작업:"

; ── 설치 파일 목록 ─────────────────────────────────────────────────────────────
[Files]
; 런처 exe (PyInstaller 빌드 결과물)
Source: "dist\{#MyAppExeName}";             DestDir: "{app}";           Flags: ignoreversion

; uv.exe (의존성 관리 / venv 생성)
Source: "dist\uv.exe";                      DestDir: "{app}";           Flags: ignoreversion

; Python 소스 (main.py + 패키지)
Source: "{#SrcRoot}\main.py";              DestDir: "{app}";           Flags: ignoreversion
Source: "{#SrcRoot}\config.py";            DestDir: "{app}";           Flags: ignoreversion
Source: "{#SrcRoot}\pyproject.toml";       DestDir: "{app}";           Flags: ignoreversion
Source: "{#SrcRoot}\uv.lock";              DestDir: "{app}";           Flags: ignoreversion skipifsourcedoesntexist

; Python 패키지 디렉토리
Source: "{#SrcRoot}\ui_ux\*";              DestDir: "{app}\ui_ux";     Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SrcRoot}\conversation\*";       DestDir: "{app}\conversation"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SrcRoot}\memory\*";             DestDir: "{app}\memory";    Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SrcRoot}\rag\*";               DestDir: "{app}\rag";       Flags: ignoreversion recursesubdirs createallsubdirs

; models 폴더 (gguf 제외 — README.txt만 안내)
Source: "{#SrcRoot}\models\README.txt";   DestDir: "{app}\models";    Flags: ignoreversion skipifsourcedoesntexist

; ── 언인스톨 시 삭제할 디렉토리/파일 ─────────────────────────────────────────
; [Files]의 Flags:deleteafterinstall은 설치 후 즉시 삭제용.
; 아래는 언인스톨러 실행 시 추가로 삭제되는 항목들.
[UninstallDelete]
; uv가 생성한 가상환경
Type: filesandordirs; Name: "{app}\.venv"
; ChromaDB 벡터 인덱스
Type: filesandordirs; Name: "{app}\chroma_deploy"
; 세션 데이터
Type: filesandordirs; Name: "{app}\data\sessions"
; 사용자 설정
Type: files;          Name: "{app}\ui_ux\assets\preferences.json"
; 모델 파일 (사용자가 배치한 gguf)
Type: filesandordirs; Name: "{app}\models"
; 나머지 설치 디렉토리 전체 (빈 폴더 정리)
Type: dirifempty;     Name: "{app}\data"
Type: dirifempty;     Name: "{app}"

; ── 바로가기 ──────────────────────────────────────────────────────────────────
[Icons]
Name: "{group}\{#MyAppName}";              Filename: "{app}\{#MyAppExeName}"; Tasks: startmenuicon
Name: "{group}\{#MyAppName} 제거";         Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}";      Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

; ── 설치 완료 후 실행 ────────────────────────────────────────────────────────
[Run]
; uv sync — .venv 생성 + 의존성 설치 (진행 표시줄 없는 백그라운드)
Filename: "{app}\uv.exe"; Parameters: "sync"; WorkingDir: "{app}"; \
    StatusMsg: "의존성 패키지 설치 중... (최초 1회, 수 분 소요)"; \
    Flags: runhidden waituntilterminated

; 설치 완료 후 앱 바로 실행 (선택)
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName} 실행"; \
    Flags: nowait postinstall skipifsilent
