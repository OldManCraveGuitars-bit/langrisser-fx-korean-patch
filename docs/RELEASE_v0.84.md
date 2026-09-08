# Langrisser FX Korean Patch v0.84

개발/프리릴리스입니다. 새 숨은 던전 번역의 **전체 사람 검수와 모든 분기
플레이는 미완료**이며, 이 제한을 명시한 공개를 관리자가 승인했습니다.
v0.8·v0.81·v0.825 릴리스는 그대로 보존합니다.

## v0.825 이후 수정 내역

- **X2 번역 누락:** 제보된 시나리오 23 경로의 퀴즈 던전 대사 97개를
  한국어로 추가했습니다. 퀴즈 선택지 순서와 원래 페이지 넘김을 보존했습니다.
- **X3 번역 누락:** 패러디 던전 대사 146개를 추가하고 원래 빈 항목 2개를
  유지했습니다. 원본 게임에서 확인한 치트 선택 번호는 X2가 **72**, X3가
  **73**입니다. X3도 치트 메뉴로 직접 진입해 도입부와 필드를 확인했습니다.
- **승리·패배 조건:** X2는 `우키 격파`, X3는 `마녀 격파`, 패배는 주인공
  `사망`으로 표시합니다. 두 던전에서 조건 메뉴 열기·취소를 각각 3회 확인했습니다.
- **근육의 신전 조건:** 잘못된 `겠습니까?` 조각과 남아 있던 일본어를 수정해
  `적 전멸` / 주인공 `사망`을 표시합니다. 다른 공용 사전은 건드리지 않았습니다.
- **7화 대사:** 사용자가 편집기에서 저장한 대사 4개를 그대로 반영했습니다.
- **불러오기 X 글자:** 전투 중 `X1`의 X가 Y처럼 깨지던 메뉴 글꼴 충돌을
  수정했습니다. 메인 메뉴의 `22`는 일본판도 같은 표시이므로 그대로 두었습니다.
  세이브 데이터나 시나리오 번호 규칙은 변경하지 않았습니다.
- **12×12 글꼴:** 필요한 한글 10자를 빈 영역에 추가하고 `닝`은 기존 글자를
  재사용했습니다. 기존 글자, 전투 상성표와 대사 이어쓰기 코드는 보존했습니다.

이전 영상 자막, 겔 게더 표기, 전과보고 그래픽, 전투 상성, 아이템·상점,
이름 글꼴 수정도 누적 포함합니다. 이번 포장 과정에서 게임 데이터를 추가로
변경하지 않았으며, 로컬 검증 빌드 283과 같은 Track 2를 생성합니다.

## 확인한 범위와 남은 사항

- X2·X3 총 245개 레코드의 인코딩, 글자, 줄·페이지 제한, 이름·제어 코드와
  원래 레코드 순서를 검사했습니다. 그중 2개는 원래부터 빈 항목입니다.
- 제공된 SRAM으로 X2에 진입했고, X3는 원본 치트 메뉴와 강제 배치 규칙으로
  진입했습니다. 두 정상 조작 경로에는 메모리 수정이나 상태 저장 불러오기를
  사용하지 않았습니다.
- 전투 12장, 상점 2장, 불러오기 24장의 비교 화면과 명령 진행이 직전 검증
  빌드와 일치했습니다. 전체 게임에 새 문제가 절대로 없다는 뜻은 아닙니다.
- 별도의 글자 전용 진단에서는 11개 한글의 출력 픽셀이 글꼴과 일치했습니다.
  이멜다의 이상한 글자 나열 화면은 이 **테스트 메모리 전용 진단**이었으며,
  실제 배포 대사나 디스크에는 포함되지 않습니다.
- 모든 퀴즈 정답·오답, 전투 대사, 숨은 아이템, 엔딩·패배 분기를 플레이한
  것은 아닙니다. 패러디 기술명과 말장난을 포함한 전체 문구 검수는 진행 중입니다.
- 다른 내부 필드 74–98에 기록된 조건 문구 문제는 이번 X2·X3 수정으로
  해결하지 않았습니다. 전체 시나리오 번역·조건 완료를 주장하지 않습니다.
- v0.84에서 자동 오프닝이나 모든 자연 발생 영상 트리거를 다시 재생한 것은
  아닙니다. 이전 자막 검증 범위는 v0.825 문서에 따로 기록되어 있습니다.
- 아이폰 및 PC-FX 실기는 이번 작업에서 실행하지 않았습니다.

세부 검증과 해시: [VERIFICATION_v0.84.md](VERIFICATION_v0.84.md).

## 설치와 업데이트

1. `Langrisser_FX_Korean_Patch_v0.84.zip`을 새 폴더에 풉니다.
2. `Langrisser-FX-KR-Auto-Patcher-v0.84.exe`를 실행합니다.
3. **원본 일본판 CUE**와 출력 위치를 선택합니다. 이전 한글 BIN에 덧씌우지 마세요.
4. 생성된 폴더의 `Langrisser-FX-KR.cue`를 실행합니다.

원본 게임, 완성 BIN, BIOS, 개인 세이브는 포함하지 않습니다. Python 패처와
설치 설명도 동봉합니다. 원본과 기존 출력은 덮어쓰지 않습니다.
SRAM을 먼저 백업하고, 버전 변경 뒤에는 강제 세이브 대신 게임 내 저장을
불러오세요. 에뮬레이터의 저장 위치와 파일명이 달라지면 SRAM을 복사해야 합니다.

결과 Track 2: **762,048,000 bytes**

SHA-256: `2907E3B635BBF95B0A6C0834EE71B61DF708E30B9606FC77914A4377884004EC`

## English summary

This cumulative pre-release adds the missing X2/X3 dialogue and battle-menu
conditions, repairs the Muscle Temple conditions and in-game load-menu X glyph,
and includes four maintainer-authored Scenario 7 edits. Ten append-only Hangul
cells are added; existing font and combat owners are preserved. Full human wording
review and all hidden branches are not complete. The maintainer approved public
pre-release distribution with these limitations, not final translation approval.

Apply to the supported original Japanese CUE, never to an older Korean image.
The automatic EXE and Python workflows reproduce the runtime-verified target.
Original media, saves and prior releases are preserved. See the verification
document for bounded runtime evidence and known unresolved scope.
