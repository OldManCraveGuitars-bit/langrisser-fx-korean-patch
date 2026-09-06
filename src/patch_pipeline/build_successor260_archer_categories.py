"""Compose accepted258/259 and display fixes into one immutable256 write plan."""
import argparse
import json
from pathlib import Path
import shutil
import build_successor259_class_change as prior
import archer_category_display as display

base=prior.base
ROOT=base.ROOT
STEM='r80-successor259-archer-category-global-successor260'
PREVIOUS_SHA='F1C21152B1B20B0DB6C85646741DC4D517C0FB075892C69D31E4094341202CC7'


def compose(source):
    slots=base.SLOT_OFFSETS
    try:
        base.SLOT_OFFSETS=slots+(0x276a1608,0x27765608)
        predecessor=base.planned_writes(source)
    finally:
        base.SLOT_OFFSETS=slots
    reconstructed=bytearray(source)
    for off,before,after,owner in predecessor:
        base.need(source[off:off+len(before)]==before,owner+' preimage')
        reconstructed[off:off+len(before)]=after
    base.need(base.sha(reconstructed)==prior.ACCEPTED_SHA,'Reproduce user-accepted258')
    predecessor+=prior.class_plan(source)
    for off,before,after,owner in predecessor:
        reconstructed[off:off+len(before)]=after
    base.need(base.sha(reconstructed)==PREVIOUS_SHA,'Reproduce259 independently')
    delta=display.plan(source)
    writes=sorted(predecessor+delta)
    for a,b in zip(writes,writes[1:]):
        base.need(a[0]+len(a[1])<=b[0],'Overlapping writers')
    result=bytearray(source);expected=set()
    for off,before,after,owner in writes:
        base.need(len(before)==len(after) and source[off:off+len(before)]==before,owner+' immutable preimage')
        result[off:off+len(before)]=after
        expected.update(off+i for i,(a,b) in enumerate(zip(before,after)) if a!=b)
    expected_delta={off+i for off,a,b,_ in delta for i,(x,y) in enumerate(zip(a,b)) if x!=y}
    base.need(prior.diff_bytes(source,result)==expected,'Full immutable-source difference')
    base.need(prior.diff_bytes(reconstructed,result)==expected_delta,'Non-target259 data changed')
    display.verify(result)
    return result,writes,expected,expected_delta


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source-dir',type=Path,default=base.SOURCE)
    p.add_argument('--out',type=Path,default=ROOT/'work'/STEM)
    a=p.parse_args();out=a.out
    base.need(not out.exists(),'Output is immutable')
    paths={k:a.source_dir/n for k,n in {
        'cooked':f'track02-{base.SOURCE_STEM}.iso','raw':f'Track-2.{base.SOURCE_STEM}.bin',
        'cue':f'Langrisser-FX-KR-{base.SOURCE_STEM}.cue'}.items()}
    for k,v in paths.items():base.need(base.file_sha(v)==base.SOURCE_SHA[k],'Source '+k)
    image,writes,changed,delta=compose(paths['cooked'].read_bytes())
    out.mkdir(parents=True)
    cooked=out/f'track02-{STEM}.iso';raw=out/f'Track-2.{STEM}.bin';cue=out/f'Langrisser-FX-KR-{STEM}.cue'
    cooked.write_bytes(image)
    sectors=sorted({x//2048 for x in changed})
    raw_audit=base.dialogue._repair_raw(cooked,paths['raw'],raw,sectors)
    for name in ('Track-1.bin','Track-3.bin','subtitle-payload.bin'):
        shutil.copyfile(a.source_dir/name,out/name)
        base.need(base.file_sha(a.source_dir/name)==base.file_sha(out/name),'Protected '+name)
    cue.write_text(paths['cue'].read_text(encoding='ascii').replace(paths['raw'].name,raw.name),encoding='ascii',newline='')
    report={'schema':'langrisser-fx-archer-category-build/v1','stem':STEM,
        'status':'STATIC_PASS_RUNTIME_REQUIRED','source':base.SOURCE_SHA,'reproduced259_sha256':PREVIOUS_SHA,
        'changes':display.verify(image),'source_changed_bytes':len(changed),'relative259_changed_bytes':len(delta),
        'all_other_bytes_identical_to259':True,'raw_audit':raw_audit,
        'writes':[{'offset':o,'owner':n,'before_hex':b.hex(),'after_hex':c.hex()} for o,b,c,n in writes],
        'outputs':{k:{'path':v.name,'sha256':base.file_sha(v)} for k,v in [('cue',cue),('cooked',cooked),('raw',raw)]}}
    (out/'archer-category-build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':report['status'],'cue':str(cue),'delta':len(delta)},ensure_ascii=False))


if __name__=='__main__':main()
