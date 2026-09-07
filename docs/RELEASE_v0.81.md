# Langrisser FX Korean Patch v0.81

개발/사전 공개 버전입니다. **v0.8은 보존하고 v0.81을 별도로 배포합니다.**

## 버그 수정

- **전투 상성 오류:** 시나리오 6에서 승병이 겔에게 제대로 피해를 주지 못하는 등
  전투 결과가 비정상적으로 나오던 공통 상성표 오염을 수정했습니다.
  일본판의 상성값으로 복원했으며 공격력·방어력이나 난이도를 임의로 조정하지 않았습니다.
- **전과보고 그래픽:** 시나리오 5 클리어 후 결과창에서 적 유닛에 붙던 불필요한
  그래픽 조각을 수정했습니다.
- **로우가 이름:** 결과창 이름에 남던 따옴표 모양의 불필요한 표시를 수정했습니다.
- **버튼 안내:** `버퀴를 눌러주세요`를 `버튼을 눌러주세요`로 수정했습니다.

수정 대상 공통 코드와 데이터 사본에 적용하여 특정 시나리오에만 한정하지 않았습니다.
전투 상성표는 기존 한글 글꼴·자막 초기화 영역과 겹치지 않도록 분리했습니다.

## 확인한 범위

- 시나리오 6: 제공된 게임 내 세이브에서 4턴까지 실제 진행. 전투 상성표 324칸이
  일본판과 같고, 실행 중 24,745회 검사에서 유지되는 것을 확인했습니다.
- 시나리오 5: 실제 전투로 마지막 적 격파 → 이벤트 → 전과보고 → 다음 시나리오
  저장창까지 확인했습니다. 적 유닛 그래픽, 로우가 이름, 버튼 안내를 재확인했습니다.
- 시나리오 2·3: 레아드 대사/아이템 입수, 7턴 표시, 헤인의 `응. 푹 잘 잤어.`,
  `자금이 부족합니다.` 안내를 재확인했습니다.
- 아이템 설명: 상점 33종 99줄, 별도 진단으로 숨은 2종 6줄을 확인했습니다.
  숨은 2종 검사는 표시 검증이며 정상 플레이 입수 경로를 검증한 것은 아닙니다.
- 기존 한글 글자 1,074개의 참조 범위가 새 상성표와 겹치지 않는지 검사했습니다.

위 범위에서 새로운 한글 깨짐이나 누락은 발견되지 않았습니다. 모든 시나리오
완주·전체 영상 재검사·아이폰 또는 PC-FX 실기 검증을 의미하지는 않습니다.
일본판과 전투 계산용 데이터는 같지만 번역에 따른 이벤트 시간 차이가 있으므로
매 턴의 난수 결과까지 동일하다고 주장하지 않습니다.
이전 누적 도구 검사에 있던 실패 8개와 오류 1개의 해결도 이번 배포 범위가 아닙니다.

## 설치 / 업데이트

1. `Langrisser_FX_Korean_Patch_v0.81.zip`을 새 폴더에 압축 해제하세요.
2. `Langrisser-FX-KR-Auto-Patcher-v0.81.exe`를 실행하세요.
3. **원본 일본판 CUE**와 출력 위치를 선택하세요. v0.8 한글판 BIN에 덧씌우지 마세요.
4. 생성된 폴더의 `Langrisser-FX-KR.cue`를 실행하세요.

Python용 패처와 설치 설명도 포함합니다. 원본 게임, 완성된 게임 이미지, BIOS,
개인 세이브는 포함하지 않습니다. 원본과 기존 출력 폴더는 덮어쓰지 않습니다.
SRAM은 먼저 백업하고 에뮬레이터의 저장 위치·이름에 맞게 옮기세요. 버전 변경 후에는
이전 코드까지 복원하는 강제 세이브 대신 게임 내 저장을 불러오세요.

결과 Track 2: 762,048,000 bytes

SHA-256: `033D1813DBD570FDABC4B8A0C53FAC7FA8DBEB5EB484F8ED0421B5B5A59EB594`

## English summary

This development/pre-release update fixes the shared combat matchup table,
result-screen enemy sprite artifacts, the stray mark beside Rohga's name, and
the Korean button prompt. Combat uses native Japanese matchup values; this is
not an arbitrary difficulty adjustment. The shared fix covers both constructor
copies and all 15 complete resident-resource replicas.

Targeted Windows PC-FX emulator checks cover Scenario 6 through turn 4, native
Scenario 5 combat/clear/results, Scenario 2/3 text regressions, and 35 item-description
records (two via a diagnostic-only catalog substitution). No new Hangul corruption
was observed in those routes. Full-campaign, complete movie-sweep, iPhone and
physical-console verification are not claimed. Earlier unrelated tool-test
failures are not claimed resolved.

Apply the cumulative v0.81 patch to the supported **original Japanese dump**,
not to v0.8. Back up SRAM saves; avoid cross-version emulator save states.
The original game and fully patched disc images are not distributed.
