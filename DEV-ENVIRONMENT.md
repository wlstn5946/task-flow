# 개발 환경 (DEV-ENVIRONMENT)

확인한 날짜: 2026-10-19
확인 방법: 각 도구의 `--version` 을 실행한 결과를 그대로 적었다.

## 운영체제 · 셸

| 항목 | 값 |
|---|---|
| 운영체제 | Microsoft Windows 11 Pro 10.0.22631 64비트 |
| 기본 셸 | PowerShell 7.6.7 |
| 보조 셸 | Git Bash (GNU bash, version 5.3.15(2)-release (x86_64-pc-cygwin)) |

## 도구별 버전

| 도구 | 명령 | 결과 |
|---|---|---|
| git | `git --version` | `git version 2.56.0.windows.2` |
| node | `node --version` | `v24.22.0` (2026-10-19 설치) |
| npm | `npm --version` | `11.19.1` |
| uv | `uv --version` | `uv 0.13.1 (62faed335 2026-10-13 x86_64-pc-windows-msvc)` |
| python | `python --version` | 실패. 출력은 `Python` 뿐이고 종료 코드는 9009 이다. |
| python (uv 가 설치한 것) | `python3.12 --version` (`C:\Users\EZ\.local\bin\python3.12.exe`) | `Python 3.12.15` |
| python (uv 로 실행) | `uv run --no-project python --version` | `Python 3.12.15` |

## 주의할 점
- PATH 의 `python` 과 `python3` 는 `C:\Users\EZ\AppData\Local\Microsoft\WindowsApps\` 아래의 Microsoft Store 연결용 자리표시자이다. 실제 Python 이 아니다. 실제 Python 은 uv 가 관리하는 3.12.15 이다.
- `pip`, `py`, `sqlite3` 명령은 없다. SQLite 는 Python 에 내장된 모듈을 쓰므로 따로 필요하지 않다.
- winget(v1.2.10691)은 `install` · `search` · `source update` 에서 접근 위반(-1073741819)으로 종료한다. 업데이트 전까지 winget 으로 설치할 수 없다.

## 새로 설치한 것
- Node.js LTS v24.22.0 (npm 11.19.1): nodejs.org 의 msi 를 SHA256 확인 후 `msiexec /qn` 으로 설치했다. 이미 열려 있던 셸에서는 PATH 를 다시 읽어야 보인다.
- backend: uv 로 fastapi, uvicorn[standard] (backend/pyproject.toml, uv.lock)
- frontend: Vite react-ts 템플릿과 npm 의존성 (frontend/package.json)
