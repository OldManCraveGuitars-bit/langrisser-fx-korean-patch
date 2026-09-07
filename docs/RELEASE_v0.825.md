# Langrisser FX Korean Patch v0.825

개발/사전 공개 버전입니다. v0.8과 v0.81은 보존합니다.
**근육의 신전 새 번역은 기술 검증을 통과했지만 전체 문장 검수는 진행 중입니다.**

## 이번 수정

- **자동 영상 자막:** 게임의 공통 영상 시작/종료 시점에서 자막 상태를
  초기화하도록 수정했습니다. 오마케에 먼저 들어가야만 자막이 나오던 경로를
  수정했으며 자막용 SRAM이나 별도 실행 명령을 요구하지 않습니다.
- **겔 게더 표기:** 상세 창의 이름은 `겔 게더`, 클래스는 `겔게더`입니다.
  하단 HUD와 전투 화면의 짧은 이름 표시는 요청대로 `겔게더`로 통일했습니다.
- **승리조건 메뉴:** 첫 열기 지연, 잘못된 화살표, 취소를 여러 번 눌러야
  닫히던 문제의 원인인 빈 레코드 경계를 복원했습니다. 실제 조건 문구와
  원본 메뉴 처리 코드는 보존하고 등록된 필드 리소스 98개를 검사했습니다.
- **근육의 신전:** 제보된 시나리오 22 경로의 별도 숨은 대사 리소스에
  한국어 대사 86개를 추가했습니다. 원래 빈 항목 1개와 페이지 구조는 유지했습니다.
  숨은 리소스의 내부 번호는 71이며 일반 편집기 1~70화 목록과 별개입니다.
- **사용자 대사 수정:** 2화와 6화에서 저장한 두 문장을 그대로 반영했습니다.
- **12×12 이름 글꼴:** 삼손의 `삼·손`, 아돈의 `돈`, 바란의 `란` 등
  과거 글꼴이 남아 있던 이름용 칸과 일부 분할 한글 글꼴을 정규화했습니다.
  8×8 HUD, 16×16 UI, 의도된 좁은 상점 글꼴, 숫자 칸은 변경하지 않았습니다.

v0.81의 전투 상성표, 전과보고 그래픽, 로우가 이름, 버튼 안내 수정도
누적 포함합니다. 이번 배포를 위해 게임 내용을 추가로 수정하지 않고
검증된 최신 로컬 결과와 동일한 Track 2를 패치로 묶었습니다.

## 검증과 한계

- 최신 결과에서 근육의 신전 도입부부터 필드까지 27개 지점을 일반 조작으로 확인.
  이름 글꼴 변경은 예상된 픽셀 영역에만 한정됐습니다.
- 승리조건 열기/취소 3회, 상점 설명, 일반 전투, 자동 오프닝 1·2 경로 재검증.
  자동 영상 검사는 SRAM 없이 진행했습니다.
- 등록된 글꼴 프로필과 글자 코드, 대사/조건 경계 및 보호 영역을 검사했습니다.
- Windows 자동 EXE와 Python 패처를 원본 CUE에 각각 적용하여 전체 결과 해시를
  대조했습니다. 게임 데이터는 실제 런타임 검증에 사용한 결과와 동일합니다.
- 전체 시나리오 완주, 모든 자연 발생 영상의 개별 트리거, 숨은 대사의 모든 분기,
  아이폰 또는 PC-FX 실기 검증을 완료했다는 의미는 아닙니다.
- 새 번역의 전체 사람 검수는 미완료입니다. 패키지의 기술 검증 통과가
  번역 품질이나 전체 플레이 검증 완료를 뜻하지는 않습니다.

자세한 수치와 재현 범위: [검증 기록](VERIFICATION_v0.825.md).

## 설치 / 업데이트

1. `Langrisser_FX_Korean_Patch_v0.825.zip`을 새 폴더에 풉니다.
2. `Langrisser-FX-KR-Auto-Patcher-v0.825.exe`를 실행합니다.
3. **원본 일본판 CUE**와 출력 위치를 선택합니다. 기존 한글 BIN에 덧씌우지 않습니다.
4. 생성된 폴더의 `Langrisser-FX-KR.cue`를 실행합니다.

Python 패처도 동봉합니다. 원본 게임, 완성된 BIN, BIOS, 개인 세이브는
포함하지 않습니다. 원본 파일과 이미 존재하는 출력 폴더를 덮어쓰지 않습니다.
SRAM은 먼저 백업하고 에뮬레이터의 저장 위치/이름에 맞게 옮기세요.
버전 변경 뒤에는 이전 코드를 복원할 수 있는 강제 세이브 대신 게임 내 저장을 불러오세요.

결과 Track 2: 762,048,000 bytes

SHA-256: `657F36173A2A1518D0440B4E95C67883C70378D7848C58AD4E620FF44777DA44`

## English summary

This cumulative development/pre-release fixes native movie subtitle lifecycle,
Gel Gather display labels, victory-condition menu boundaries, and legacy
12×12 Hangul name glyphs. It also includes the missing Muscle Temple dialogue
and two maintainer-authored Scenario 2/6 edits. Full human wording review of
the new hidden dialogue remains pending; this is not a final localization release.

The exact target was checked through the hidden introduction, condition-menu
open/cancel cycles, shop, native combat and unattended openings 1/2. Full-campaign,
every natural movie trigger, iPhone and physical-console QA are not claimed.
Both packaged EXE and Python installation reproduce the verified Track 2 hash.
Apply to the supported original Japanese CUE, never to an older Korean-patched
image. Preserve SRAM backups and avoid cross-version emulator save states.
