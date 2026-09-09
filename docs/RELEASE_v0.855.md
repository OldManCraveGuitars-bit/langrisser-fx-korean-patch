# v0.855 — Dialogue review and maintainer correction

## 한국어 수정 내역

이번 버전은 **원본 일본판에 적용하는 누적 패치**입니다. 내부 빌드는 293이며,
v0.851의 하단 이름 잔상 및 이전 전투 프리징 수정도 그대로 포함합니다.

### 직접 수정한 15화 대사 적용

편집기에서 저장한 `scenario15/dialogue/022`를 정확히 반영했습니다.

```text
……알고 있어…….
엘윈이…… 그……
리아나를 좋아한다는 걸.
```

실제 데이터는 이름을 고정하지 않고 기존 주인공·리아나 이름 토큰을 유지합니다.
기본 이름에서 `엘윈가`로 나오던 조사를 `엘윈이`로 고쳤으며, 이름 변경에 따른
자동 조사 선택 기능을 새로 추가한 것은 아닙니다. 수정 전 292 대비 2바이트만
변경하고 나머지 15화 대사 143개와 모든 레코드 위치는 보존했습니다.

### 13·14화 대사 검수 반영

- 13화 174개 대사와 14화 104개 대사를 일본판 원문과 대조해 검수했습니다.
- 13화의 의미 오역·어색한 말투·페이지별 내용 배치를 수정했습니다.
  `ヴェルゼリアか`의 잘못된 레온 언급을 `벨제리아인가……`로 바로잡는 등의
  수정과, 베른하르트 대면 시 `네가 네가`가 중복되던 수정도 포함합니다.
- 14화는 13화 수정 전보다 양호했지만 직역투와 명령·응답의 뉘앙스를 다듬었습니다.
  `하, 하지만……` → `예……`, `덤벼라!` → `공격하라!` 등이 해당합니다.
- 일본판의 13화 **243페이지**, 14화 **125페이지**와 페이지·대기·이름 제어
  순서를 그대로 보존했습니다. 페이지 안에서만 한국어 구절에 맞게 줄을 끊었습니다.
- 14화 70개 항목의 문구 또는 줄바꿈이 바뀌었습니다. 모두 오역이라는 뜻은 아닙니다.

### 보존한 영역과 검증 한계

v0.851 대비 변경된 cooked 데이터는 10,129바이트이며, S13/S14 대사 및 S15의
선택된 조사만 달라졌습니다. 다른 시나리오 대사, 공용 폰트·사전, UI, 승패조건,
실행 코드, 전투 데이터, 영상 자막 및 음원은 동일합니다.

13·14화의 원문 대조와 최종 데이터 검증은 전체 해당 대사에 수행했습니다.
실제 플레이 확인은 [검증 보고서](VERIFICATION_v0.855.md)에 적은 경로만 해당하며
모든 분기를 플레이했다는 뜻은 아닙니다. 숨은 던전 전체 문장 검수, 전 시나리오
플레이 및 실기/iPhone 검증은 여전히 완료를 주장하지 않습니다. 이전 누적 도구
검사의 실패 8개·오류 1개도 이번에 해결했다고 주장하지 않습니다.

## English summary

- Applies the exact maintainer-authored S15/022 particle correction with a
  two-byte write, without moving any native record or changing shared resources.
- Includes the S13 (174 records) and S14 (104 records) Japanese-source reviews,
  preserving their 243/125 original pages and page-local name/control order.
- Retains the duplicate-`네가` fix in the Bernhardt confrontation and all v0.851 fixes.
- Changes only the stated dialogue scope; battle behavior, UI/fonts, conditions,
  subtitles and audio remain byte-identical to v0.851.
- Refreshes the cumulative delta and automatic patcher. This remains a prerelease
  review candidate for maintainer/community testing, not a completed translation.

## Installation

Run **Langrisser-FX-KR-Auto-Patcher-v0.855.exe** with the supported **original
Japanese CUE**. Do not patch an older Korean BIN. The installer validates all
three source tracks and creates a separate complete CUE/BIN set.

Back up SRAM saves and use an in-game save. Do not transfer emulator save states
between builds: they can restore old patched code. Original game media, BIOS,
save files and fully patched discs are not included in this release.

Installation guide: `INSTALL.txt` in the release ZIP (`patch/INSTALL.txt` in the repository).

[Verification](VERIFICATION_v0.855.md) ·
[Implementation](IMPLEMENTATION_v0.855.md) · [Publication scope](PUBLICATION_v0.855.md)
