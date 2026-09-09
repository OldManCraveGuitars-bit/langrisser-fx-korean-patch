# Langrisser FX Korean Patch v0.85

This cumulative development/pre-release includes the verified internal build
288 and all earlier fixes. Apply it to the supported **original Japanese disc**,
not an older Korean-patched image. Full localization review and an all-scenario
playthrough are not claimed.

## 수정 리포트

### 1. 시나리오 12 엔젤 → 피닉스 전투 프리징

- 전투 시작 화면에서 멈추던 문제를 수정했습니다.
- 과거 영상 자막 자료 배치가 원래 게임 자료 목록의 마지막 주소 일부를
  덮어쓴 것이 원인이었습니다. 피닉스 전투에서 6섹터를 읽어야 할 곳을
  잘못된 큰 크기로 읽으려 했습니다.
- 손상된 주소를 일본판 원본과 동일하게 복원했습니다. 공격력·방어력·상성·
  피해 계산이나 난이도는 변경하지 않았습니다.
- 같은 원인으로 손상된 다른 공용 자료 경계 1곳도 찾아 복원했습니다.
  이 추가 지점은 데이터 오류를 확인한 것이며 별도의 전투 프리징까지
  실제 재현했다는 뜻은 아닙니다.
- 두 자료 목록의 전체 629개 구간을 검사하고 원본과 대조했습니다.

### 2. 하단 로열랜서 글꼴 배열

- 하단 UI에서 ‘로’만 다른 모양으로 보이던 부분을 기존 Galmuri7 규칙으로
  맞췄습니다. 로열랜서뿐 아니라 같은 글자를 쓰는 로열가드·로우가·로렌
  등의 하단 표기에도 적용됩니다.
- 전체 15개 글꼴 사본에서 각각 201개 글자를 검사했습니다. ‘로’ 외의 글자,
  클래스/이름 문자열, 글자 간격, 색상과 출력 코드는 그대로입니다.

### 확인한 내용

- 같은 세이브와 입력으로 기존 버전의 프리징을 재현하고 일본판 정상 진행을
  대조한 뒤, 새 빌드에서 엔젤→피닉스 전투 완료와 맵 복귀를 확인했습니다.
- 로열랜서 하단 글꼴을 게임 내 저장 불러오기부터 다시 확인했습니다.
- 시나리오 10 전투·클리어·결과창을 다시 진행했습니다. 결과창 표본 88장은
  앞서 검증한 v0.845와 동일하며 적 유닛 그래픽도 일본판 자료와 일치합니다.
- 가만히 켜 두면 재생되는 오프닝 2와 오마케의 오프닝 2를 각각 확인했습니다.
  한글 자막을 포함한 8개 비교 지점이 일치합니다.
- v0.845 대비 실제 게임 데이터 변경은 92바이트입니다. 이 중 프리징 원인
  복원은 2바이트, 하단 ‘로’ 글꼴은 90바이트입니다. RAW 섹터의 관련 오류 검출·
  정정 정보도 갱신하고 나머지 영역이 유지되는지 검사했습니다.

모든 시나리오를 직접 플레이한 것은 아닙니다. 변경하지 않은 98개 내부
시나리오 자료 컨테이너와 공통 자료 범위를 검사한 것이며, ‘98개 시나리오가
더 남아 있다’거나 전체 플레이를 완료했다는 뜻은 아닙니다.

## English summary

- Restored two native resource-directory terminal words damaged by an obsolete
  subtitle allocation. One caused the reproduced Angel-versus-Phoenix freeze;
  the second was a confirmed sibling data defect, not a separately observed hang.
- Audited all 629 resource intervals and restored only two corrupted bytes.
- Normalized the shared HUD syllable `로` to the adopted Galmuri7 source in all
  15 banks, retaining every other glyph, label and spacing rule.
- Rechecked cold Scenario 12 combat/map return, the Royal Lancer HUD,
  Scenario 10 combat/results and automatic/OMAKE Opening 2 subtitles.
- Only 92 cooked bytes change from v0.845. Gameplay code, stats, matchup tables,
  dialogue, current subtitle payload and audio tracks are unchanged.

## Download and install

Download **Langrisser_FX_Korean_Patch_v0.85.zip** from this release. Extract it,
run **Langrisser-FX-KR-Auto-Patcher-v0.85.exe**, select your original Japanese
CUE and choose a new output location. See `INSTALL.txt` for the Python fallback
and supported source hash. The package contains no original or fully patched
game image, BIOS, personal save or emulator.

Back up SRAM saves and load an in-game save after changing builds. Do not use an
old emulator save state, which can restore the previous version's code/data.
The automatic patcher leaves original files and existing outputs untouched.

## Limits retained from earlier pre-releases

Full human wording review of hidden-dungeon dialogue, every branch, every natural
movie trigger and physical-console/iPhone verification remain incomplete. The
earlier cumulative tooling baseline's eight failures and one error are not
claimed fixed. Other historical condition-field issues remain outside this
update. See the current README for inherited limitations.

Technical report: [implementation](IMPLEMENTATION_v0.85.md),
[verification](VERIFICATION_v0.85.md), [publication scope](PUBLICATION_v0.85.md).
