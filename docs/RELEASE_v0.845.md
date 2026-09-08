# v0.845 — dialogue and result-screen graphics fixes

Development/pre-release. This is a cumulative patch for the supported original
Japanese PC-FX **Der Langrisser FX** disc, not an incremental patch for an older
Korean image. Earlier v0.84 and previous fixes remain included.

## 한국어 수정 내역

- 8·9화에서 사용자가 수정한 대사 10개를 반영했습니다. 쉐리의 존댓말을
  반말로 바꾼 내용 등을 그대로 적용했으며, 선택하지 않은 대사와 기존
  페이지 넘김·이름 제어 구조는 보존했습니다.
- 시나리오 10 클리어 후 결과창에서 적 유닛에 불필요한 글자 조각이 붙던
  문제를 수정했습니다. 공통 메뉴 글자가 유닛 그래픽 영역을 덮어쓰던
  충돌이 원인이었습니다.
- 해당 전투의 유닛만 대상으로 고친 것이 아니라, 공통 유닛 캐시 전체
  46개 항목·414개 타일과 충돌하던 메뉴 글자 조각 6개를 분리했습니다.
  메뉴 사본 10개와 설정 사본 10개의 연결된 참조도 함께 수정했습니다.
- 이번 그래픽 수정은 직전 대사 반영 빌드에서 400바이트만 변경합니다.
  글자 그림, 이름, 실행 코드, 전투 수치, 영상·자막·음원 데이터는 바꾸지
  않았으며 이전 X1·X2·X3 불러오기 글자 수정도 유지했습니다.

## 검증 범위

- 시나리오 10 세이브를 초기 부팅부터 불러와 메테오, 턴 종료, 엘윈 공격으로
  발가스 처치 → 대화 이벤트 → 결과창까지 실제 입력으로 확인했습니다.
- 결과창 88개 시점에서 사용 중인 유닛 29개의 그래픽 타일 261개가 일본판
  원본의 같은 유닛 목록과 일치했습니다. 이름과 하단 UI도 직전 빌드의 같은
  시점과 일치했습니다.
- 설정의 `꺼짐`, 승리·패배조건, 불러오기 메뉴를 확인했습니다. 승리조건과
  불러오기는 취소 한 번으로 돌아왔습니다.
- 다른 스테이지에 대해서는 공통 캐시 전체 경계와 모든 등록 메뉴·설정 사본을
  데이터로 검사했습니다. 전체 스테이지를 새로 플레이했다는 뜻은 아닙니다.

## Installation / 설치

Download `Langrisser_FX_Korean_Patch_v0.845.zip`, extract it and run
`Langrisser-FX-KR-Auto-Patcher-v0.845.exe`. Select the **original Japanese CUE**
and a new output location. Full instructions: [INSTALL.txt](../patch/INSTALL.txt)
in the repository, or `INSTALL.txt` in the release ZIP.

원본 일본판에 새로 적용하세요. 이전 한글판 BIN에 덧씌우지 마세요.
SRAM을 백업하고 게임 내 저장을 불러오세요. 이전 빌드의 강제 세이브는
옛 코드까지 복원할 수 있으므로 사용하지 마세요. 원본과 기존 출력은
덮어쓰지 않습니다. 원본 게임·완성된 게임 이미지·세이브는 배포하지 않습니다.

## English summary

Ten selected Scenario 8/9 dialogue edits are included. Six shared Korean menu
scatter entries and their exact references were moved outside the entire native
unit-cache range to resolve Scenario 10 result-screen sprite corruption.
All registered menu/settings replicas are covered without modifying gameplay,
glyph pixels, names, executable code or subtitle/audio data in this correction.
The target was verified through a cold SRAM/controller route and exact artifact
checks. Both Python and the packaged Windows EXE reproduce the verified target.

## Remaining limits

This remains a pre-release. Full human wording review of the Muscle Temple and
X2/X3 dialogue, every hidden branch, full-campaign playback and physical PC-FX/iOS
verification remain unfinished. The six later Scenario 9 conversations were
verified in data, not all reached through campaign play. The Scenario 5 smoke
attempt did not reach results and is not counted as new result-screen evidence.
Every movie trigger was not replayed for this release; prior movie evidence keeps
its original version attribution. Unrelated historical tooling failures and
condition issues in other internal field records are not claimed fixed.
The 98 catalogued field containers are not 98 additional playable scenarios.

See [verification](VERIFICATION_v0.845.md),
[implementation](IMPLEMENTATION_v0.845.md) and
[publication scope](PUBLICATION_v0.845.md).
