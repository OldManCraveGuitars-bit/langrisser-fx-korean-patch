"""One immutable write plan: reproduce accepted258 from256, then class UI.

Never patches a manually edited working image. The independently reproduced
258 intermediate must equal the user-accepted artifact before composition.
Only the class UI delta is permitted relative to that baseline.
"""
import argparse
import json
from pathlib import Path
import shutil
import struct
import build_successor257_event_rewards_menu_tiles as base
import class_change_ui as ui

ROOT = base.ROOT
STEM = 'r80-successor258-class-change-global-successor259'
ACCEPTED_STEM = 'r80-successor256-event-rewards-hud-complete-successor258'
ACCEPTED_SHA = '0B72F13A6231DD8860D775E5972B42DE6B56B40ABCA750A1893BE03470C18F37'


def class_plan(source):
    catalog_path = ROOT/'analysis/common_dictionary_replicas_v340_audit.json'
    base.need(base.file_sha(catalog_path) == ui.CATALOG_SHA, 'common population identity')
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    roots = tuple(int(x, 16) for x in catalog['replica_offsets'])
    base.need(roots == tuple(x-0x1b8 for x in base.REWARD_OFFSETS), 'independent common population closure')
    writes = []
    for ordinal, root in enumerate(roots):
        for delta, before, after, owner in ui.TEXT_FIELDS:
            off = root + delta
            new = ui.replace_record(source[off:off+len(before)], before, after)
            writes.append((off, before, new, f'{owner}/replica/{ordinal:03d}'))
    hits=[]; cursor=-1
    while (cursor:=source.find(ui.LOOP_BEFORE,cursor+1)) >= 0: hits.append(cursor)
    base.need(tuple(hits) == ui.CODE_OFFSETS, 'native class code copy closure')
    base.need(base.sha(source[0xa928:0xaa30]) == ui.CALLEE_SHA, 'small renderer ABI')
    for off in ui.CODE_OFFSETS:
        base.need(base.sha(source[off-0x3e:off+0x2ce]) == ui.FUNCTION_SHA, 'class function/liveness identity')
        writes.append((off, ui.LOOP_BEFORE, ui.command_range_caption(), 'class-change/command-range-caption'))
    return writes


def diff_bytes(a, b):
    base.need(len(a) == len(b), 'image size changed')
    changed=set()
    for start in range(0,len(a),1<<20):
        x=a[start:start+(1<<20)];y=b[start:start+(1<<20)]
        if x!=y: changed.update(start+i for i,(m,n) in enumerate(zip(x,y)) if m!=n)
    return changed


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-dir',type=Path,default=base.SOURCE)
    parser.add_argument('--accepted-dir',type=Path,default=ROOT/'work'/ACCEPTED_STEM)
    parser.add_argument('--out',type=Path,default=ROOT/'work'/STEM)
    args=parser.parse_args();out=args.out
    base.need(not out.exists(), 'immutable output already exists')
    source_files={k:args.source_dir/n for k,n in {
        'cooked':f'track02-{base.SOURCE_STEM}.iso','raw':f'Track-2.{base.SOURCE_STEM}.bin',
        'cue':f'Langrisser-FX-KR-{base.SOURCE_STEM}.cue'}.items()}
    for k,p in source_files.items():base.need(base.file_sha(p)==base.SOURCE_SHA[k],f'source {k}')
    accepted=args.accepted_dir/f'track02-{ACCEPTED_STEM}.iso'
    base.need(base.file_sha(accepted)==ACCEPTED_SHA,'accepted258 identity')
    source=source_files['cooked'].read_bytes()
    # The established258 Resource-12 loader closure, composed before any write.
    offsets=struct.unpack_from('<17I',source,0x1903800)
    for index,expected in [(2,0x276a1608),(10,0x27765608)]:
        base.need(offsets[index+1]-offsets[index]==0x18800 and
                  0x1903800+offsets[index]+0x5e08==expected,'resource12 loader identity')
    old_slots=base.SLOT_OFFSETS
    try:
        base.SLOT_OFFSETS=old_slots+(0x276a1608,0x27765608)
        predecessor=base.planned_writes(source)
    finally:base.SLOT_OFFSETS=old_slots
    baseline=bytearray(source)
    for off,before,after,owner in predecessor:baseline[off:off+len(before)]=after
    base.need(base.sha(baseline)==ACCEPTED_SHA,'reconstructed258 differs from accepted product')
    delta=class_plan(source);writes=sorted(predecessor+delta)
    for a,b in zip(writes,writes[1:]):base.need(a[0]+len(a[1])<=b[0],'overlapping write owners')
    image=bytearray(source);expected=set();expected_delta=set()
    for off,before,after,owner in writes:
        base.need(source[off:off+len(before)]==before,'immutable preimage')
        image[off:off+len(before)]=after
        expected.update(off+i for i,(a,b) in enumerate(zip(before,after)) if a!=b)
    for off,before,after,owner in delta:
        expected_delta.update(off+i for i,(a,b) in enumerate(zip(before,after)) if a!=b)
    base.need(diff_bytes(source,image)==expected,'full source diff')
    base.need(diff_bytes(baseline,image)==expected_delta,'accepted258 protected-region diff')
    for off in ui.CODE_OFFSETS:ui.validate_caption(image[off:off+26])
    out.mkdir(parents=True)
    cooked=out/f'track02-{STEM}.iso';raw=out/f'Track-2.{STEM}.bin';cue=out/f'Langrisser-FX-KR-{STEM}.cue'
    cooked.write_bytes(image)
    sectors=sorted({x//2048 for x in expected})
    raw_audit=base.dialogue._repair_raw(cooked,source_files['raw'],raw,sectors)
    for name in ['Track-1.bin','Track-3.bin','subtitle-payload.bin']:
        a=args.source_dir/name;b=out/name;shutil.copyfile(a,b)
        base.need(base.file_sha(a)==base.file_sha(b)==base.file_sha(args.accepted_dir/name),f'protected {name}')
    cue.write_text(source_files['cue'].read_text(encoding='ascii').replace(source_files['raw'].name,raw.name),encoding='ascii',newline='')
    report={'schema':'langrisser-fx-class-change-build/v1','status':'STATIC_PASS_RUNTIME_REQUIRED',
        'stem':STEM,'source':base.SOURCE_SHA,'accepted258_sha256':ACCEPTED_SHA,
        'source_changed_bytes':len(expected),'accepted258_changed_bytes':len(expected_delta),
        'common_text_replicas':105,'caption_code_copies':2,'raw_audit':raw_audit,
        'writes':[{'offset':o,'owner':n,'before_hex':a.hex(),'after_hex':b.hex()} for o,a,b,n in writes],
        'protected_relative_to258':{'all_other_bytes_unchanged':True,'font_bitmaps_unchanged':True,
            'item_names_tooltips_rewards_unchanged':True,'movie_data_and_subtitles_unchanged':True,
            'battle_rules_and_class_parameters_unchanged':True},
        'outputs':{k:{'path':p.name,'sha256':base.file_sha(p)} for k,p in [('cue',cue),('cooked',cooked),('raw',raw)]},
        'runtime_verified':False}
    (out/'class-change-build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':report['status'],'cue':str(cue),'class_delta':len(expected_delta)},ensure_ascii=False))


if __name__=='__main__':main()
