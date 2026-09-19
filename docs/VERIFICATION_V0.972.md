# V0.972 verification scope

The publication target is the approved **successor310-review2**, unchanged.
Its build reconstructs approved309 from a hash-verified original-derived298 cache,
then applies bounded condition edits. Publication uses this approved result;
it does not claim a separate full authoring rebuild or new gameplay session.

## Data and runtime checks

- All98 physical field condition tables, 799 menu slots /472 nonempty rows,
  and142 pre-battle condition frames inspected against original Japanese data.
- 49 tables changed:85 menu rows and11 presentation frames.18 tables had46
  untranslated menu rows. Japanese residuals/width overflows:0.
- All71 Hangul glyph routes used by the replacement text validated.
- New condition tests8 and existing header-layout test1 passed.
- Exactly8,710 cooked bytes differ from approved309. Protected complement,
  headers/pointers/event code and unrelated expanded text consumers match.
- Native77 reproduced from a cold game load of the maintainer's SRAM. Conditions
  reopened after settings and checked alongside save prompts and field return.
- Normal20 condition/menu regression checked. No RAM edits or state injection;
  original save files unchanged. Native loaded tables match the final ISO.
- Auxiliary88/90 pre-existing source differences between menu and introduction
  preserved, not guessed from battle logic.98 tables is not98 playable scenarios.

## Package verification

The cumulative delta is generated from the supported original RAW Track2 to the
exact approved310 target. Both the Python CUE installer and final Windows EXE
are applied independently; their three complete output tracks and CUE are compared.
See [machine-readable verification](verification_V0.972.json) for results and identities.
Eleven public synthetic patch/container tests are run without game media.
The ZIP is allowlisted, CRC-checked and member-hashed. Five screenshots are checked
against their unedited source captures. Publication checks remote tag/body/tree/assets
and re-downloads the ZIP/checksum, preserving existing releases.

Original Track2 SHA-256:
`1013D1AECCD42BB46DEA36CF3BD088CAE02FAC5D25BF4BC0187821ACAB9F8AD0`.

Final RAW Track2 (762,048,000 bytes):
`397110E066F8CA2C13ABAF607D8AD85D82AAFBB0356FD36051389B1EF5FDD3CC`.

Final cooked ISO:
`A5C120878C0BBE6BBA6C15BCE498F265BB3E67E9BB46D0BFD56717A0BEDA57A5`.

## Limits

This is a development prerelease, not an all-scenario/all-branch playthrough or
hardware/iOS certification. The intermittent ending blackscreen remains unresolved.
Earlier cumulative tool failures (8 failures/1 error) are not claimed resolved.
Previous MP-shortage gameplay was skipped at the maintainer's request.
The source snapshot is inspectable, not a complete standalone game-authoring tree.
