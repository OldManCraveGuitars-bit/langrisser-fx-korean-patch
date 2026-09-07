#!/usr/bin/env python3
"""Build from Japanese Track 2 + pinned cumulative v0.81 specification.

The older game output is NOT a build input. The v0.81 LFXPAT01 delta is the
retained cumulative implementation specification; it reconstructs its declared
baseline within this invocation. The display writer is explicitly composed on
that intermediate, with an exact protected-complement check. No existing game
output, save, public repository, or release is modified.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'dialogue_editor')]
import gel_gather_labels as labels
import build_successor261_shop_hud as integrity
import cd_mode1

STEM = 'r80-v081-gel-gather-labels-successor273'
AUTOMATIC_MOVIE_STEM = 'r80-v081-labels-automatic-opening-successor274'
LIFECYCLE_STEM = 'r80-v081-common-movie-lifecycle-successor275'
COMPACT_STEM = 'r80-v081-gel-gather-compact-successor276'
CONDITION_STEM = 'r80-v081-condition-menu-boundaries-successor277'
MUSCLE_STEM = 'r80-v081-muscle-temple-user-dialogue-successor278'
FONT_STEM = 'r80-v081-unified-12x12-names-successor279'
RAW_SHA = '033D1813DBD570FDABC4B8A0C53FAC7FA8DBEB5EB484F8ED0421B5B5A59EB594'
COOKED_SHA = '74B5AA9D0083302D6C74C54CE0BC3B5DAB725E17F576D285B56E1CD550D53B17'
DELTA_SHA = 'AD05ACECDFEA7EC2B3E49D8FD82B74D189E789C7EB645955FA0608C5C2B07511'
COOKED_SIZE = 663091200


def verify_raw(baseline_raw, raw, cooked, sectors):
    """Verify each final raw byte against its composed payload/checksum owner."""
    labels.need(raw.stat().st_size == baseline_raw.stat().st_size, 'Raw extent changed')
    changed=set(sectors)
    checked=0
    with baseline_raw.open('rb') as old, raw.open('rb') as new, cooked.open('rb') as iso:
        for first in range(0, raw.stat().st_size//2352, 1024):
            before=old.read(1024*2352)
            after=new.read(len(before))
            expected=bytearray(before)
            for cooked_sector in changed:
                relative=cooked_sector+225-first
                if not 0 <= relative < len(before)//2352:
                    continue
                offset=relative*2352
                sector=bytearray(before[offset:offset+2352])
                iso.seek(cooked_sector*2048)
                sector[16:2064]=iso.read(2048)
                cd_mode1.repair_mode1_sector(sector)
                labels.need(cd_mode1.verify_mode1_sector(bytes(sector)), 'Final EDC/ECC')
                expected[offset:offset+2352]=sector
                checked+=1
            labels.need(after==expected, f'Unexpected raw change in block {first}')
    labels.need(checked==len(changed),'Changed raw sector denominator')
    return {'sectors_checked':raw.stat().st_size//2352,
            'changed_sectors':checked,'all_unplanned_bytes_identical':True}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--original-track2', type=Path, required=True)
    parser.add_argument('--public-repo', type=Path, required=True)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--fix-automatic-movies', action='store_true',
                        help='Also restore the common subtitle renderer return-anchor contract')
    parser.add_argument('--fix-movie-lifecycle',action='store_true',
                        help='Bind subtitles to native movie entry/exit, covering the common physical-ID path')
    parser.add_argument('--compact-battle-names',action='store_true',
                        help='Use the existing compact Gel Gather record for lower-HUD names; preserve both font banks')
    parser.add_argument('--fix-condition-menu-boundaries',action='store_true',
                        help='Restore native-readable empty condition records without changing text or fonts')
    parser.add_argument('--muscle-temple-review',action='store_true',
                        help='Non-distribution hidden resource 71 translation plus the two selected user edits')
    parser.add_argument('--normalize-12x12',action='store_true',
                        help='Normalize semantic name and split-word Hangul without touching other font sizes')
    args=parser.parse_args()
    if args.fix_automatic_movies and args.fix_movie_lifecycle:
        parser.error('Choose one movie implementation')
    if args.compact_battle_names and not args.fix_movie_lifecycle:
        parser.error('Compact names require the current common movie lifecycle implementation')
    if args.fix_condition_menu_boundaries and not args.compact_battle_names:
        parser.error('Condition repair requires the current compact-name profile')
    if args.muscle_temple_review and not args.fix_condition_menu_boundaries:
        parser.error('Hidden translation review requires the complete successor277 profile')
    if args.normalize_12x12 and not args.muscle_temple_review:
        parser.error('Current font profile requires the complete successor278 review profile')
    stem=LIFECYCLE_STEM if args.fix_movie_lifecycle else AUTOMATIC_MOVIE_STEM if args.fix_automatic_movies else STEM
    if args.compact_battle_names:
        stem=COMPACT_STEM
    if args.fix_condition_menu_boundaries:
        stem=CONDITION_STEM
    if args.muscle_temple_review:
        stem=MUSCLE_STEM
    if args.normalize_12x12:
        stem=FONT_STEM
    args.out=args.out or ROOT/'work'/stem
    need=labels.need
    need(not args.out.exists(), 'Choose a new immutable output directory')
    delta=args.public_repo/'patch/Langrisser-FX-KR-v0.81.lfxpatch'
    need(integrity.file_sha(delta)==DELTA_SHA, 'Cumulative specification identity')
    spec=importlib.util.spec_from_file_location('lfx_public_apply',args.public_repo/'patch/apply_patch.py')
    applier=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(applier)
    derived=args.out/'derived-inputs'
    derived.mkdir(parents=True)
    baseline_raw=derived/'v0.81-reconstructed.bin'
    patch_audit=applier.apply_patch(args.original_track2,delta,baseline_raw)
    need(patch_audit['sha256']==RAW_SHA, 'Reconstructed cumulative raw identity')
    baseline_cooked=derived/'v0.81-reconstructed.iso'
    with baseline_raw.open('rb') as source, baseline_cooked.open('xb') as target:
        source.seek(225*2352)
        remaining=COOKED_SIZE//2048
        while remaining:
            count=min(remaining,2048)
            block=source.read(count*2352)
            need(len(block)==count*2352,'Cumulative raw projection truncated')
            target.write(b''.join(block[i+16:i+16+2048] for i in range(0,len(block),2352)))
            remaining-=count
    need(integrity.file_sha(baseline_cooked)==COOKED_SHA, 'Cooked projection identity')
    source=baseline_cooked.read_bytes()
    writes,audit=labels.plan(source, compact=args.compact_battle_names)
    condition_audit=None
    if args.fix_condition_menu_boundaries:
        import condition_menu_boundaries as condition
        condition_writes,condition_audit=condition.plan(source)
        writes=sorted([*writes,*condition_writes])
    movie_audit=None
    fix_movies=args.fix_automatic_movies or args.fix_movie_lifecycle
    if fix_movies:
        if args.fix_movie_lifecycle:
            import subtitle_movie_lifecycle as movie
        else:
            import subtitle_return_anchor as movie
        movie_writes,movie_audit=movie.plan(source)
        writes=sorted([*writes,*movie_writes])
    muscle_audit=user_audit=None
    if args.muscle_temple_review:
        import muscle_temple_dialogue as muscle
        import selected_user_dialogue as selected
        muscle_writes,muscle_audit=muscle.plan(source)
        user_writes,user_audit=selected.plan(source)
        writes=sorted([*writes,*muscle_writes,*user_writes])
    font_audit=None
    if args.normalize_12x12:
        import font_policy_12x12 as typography
        font_writes,font_audit=typography.plan(source)
        writes=sorted([*writes,*font_writes])
    for offset,before,after,owner in writes:
        need(len(before)==len(after) and source[offset:offset+len(before)]==before,
             f'Immutable-source expected-write mismatch: {owner}')
    for left,right in zip(writes,writes[1:]):
        need(left[0]+len(left[1])<=right[0], 'Overlapping cumulative writers')
    expected={offset+i for offset,before,after,_ in writes
              for i,(a,b) in enumerate(zip(before,after)) if a!=b}
    cooked=args.out/f'track02-{stem}.iso'
    raw=args.out/f'Track-2.{stem}.bin'
    cue=args.out/f'Langrisser-FX-KR-{stem}.cue'
    shutil.copyfile(baseline_cooked,cooked)
    with cooked.open('r+b') as target:
        for offset,_before,after,_owner in writes:
            target.seek(offset)
            target.write(after)
    target=cooked.read_bytes()
    need(integrity.diff_bytes(source,target)==expected,'Unplanned final cooked difference')
    for offset,_before,after,owner in writes:
        need(target[offset:offset+len(after)]==after,f'Final write missing: {owner}')
    if fix_movies:
        movie.verify(target if args.fix_movie_lifecycle else target[movie.OFFSET:movie.OFFSET+96])
    if args.fix_condition_menu_boundaries:
        condition_audit['final_verification']=condition.verify(target)
    if args.muscle_temple_review:
        muscle_audit['final_verification']=muscle.verify(target)
        selected.verify(source,target)
    if args.normalize_12x12:
        font_audit['final_verification']=typography.verify(target)
    sectors=sorted({x//2048 for x in expected})
    raw_audit=integrity.raw_tools.dialogue._repair_raw(cooked,baseline_raw,raw,sectors)
    raw_audit.update(verify_raw(baseline_raw,raw,cooked,sectors))
    audio={
        1:'1E1840205CE98F5E0DF8067BEA8B3336DB62CA071C7B67538A0312C267D9CFA9',
        3:'9D1133A7DDAB061567F6C83F3342C90CBE32DC6A94561AE5309FA74335FDDD8D',
    }
    for track,digest in audio.items():
        original=args.original_track2.with_name(args.original_track2.name.replace('(Track 2)',f'(Track {track})'))
        need(integrity.file_sha(original)==digest,f'Original audio track {track}')
        shutil.copyfile(original,args.out/f'Track-{track}.bin')
    cue.write_text('CATALOG 0000000000000\nFILE "Track-1.bin" BINARY\n  TRACK 01 AUDIO\n'
        '    INDEX 01 00:00:00\n'+f'FILE "{raw.name}" BINARY\n  TRACK 02 MODE1/2352\n'
        '    INDEX 00 00:00:00\n    INDEX 01 00:03:00\nFILE "Track-3.bin" BINARY\n'
        '  TRACK 03 AUDIO\n    INDEX 00 00:00:00\n    INDEX 01 00:02:00\n',encoding='ascii')
    report={
        'status':'STATIC_PASS_RUNTIME_REQUIRED', 'stem':stem, 'display_audit':audit,
        'automatic_movie_audit':movie_audit,
        'condition_menu_audit':condition_audit,
        'muscle_temple_audit':muscle_audit,'selected_user_dialogue':user_audit,
        'font_12x12_audit':font_audit,
        'distribution_allowed':False if args.muscle_temple_review else None,
        'build_inputs':{'original_track2_sha256':integrity.file_sha(args.original_track2),
                        'cumulative_delta_sha256':DELTA_SHA,
                        'approved_labels_sha256':integrity.file_sha(labels.LABELS)},
        'reconstructed_baseline':patch_audit,'changed_bytes':len(expected),
        'sectors':sectors,'raw_audit':raw_audit,
        'writes':[{'offset':hex(o),'owner':n,'before':b.hex(),'after':a.hex()} for o,b,a,n in writes],
        'all_other_cooked_bytes_identical_to_v081':True,
        'movie_issue':('Common native movie lifecycle; runtime required' if args.fix_movie_lifecycle else
                      'Automatic Opening-2 return-anchor repair; runtime required'
                       if args.fix_automatic_movies else 'Not fixed by this display-only change'),
        'outputs':{p.name:integrity.file_sha(p) for p in (cooked,raw,cue)},
    }
    (args.out/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':report['status'],'cue':str(cue),'changed_bytes':len(expected)},ensure_ascii=False))


if __name__=='__main__':
    main()
