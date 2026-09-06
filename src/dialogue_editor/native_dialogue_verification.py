"""Re-read actual roots and referenced dictionary bytes after the last writer.

This is a codec/population gate, not a substitute for consumer layout, font
residency, voice timing or runtime verification. No repair is performed here.
"""
import hashlib
import json

import dialogue_core as dialogue
import global_dialogue_storage as storage
from native_glyphs import with_native_ascii


def expand(raw, reverse, entries, bias, depth=0):
    dialogue.need(depth < 8, '대사 사전 순환/과도한 중첩')
    output, cursor = [], 0
    while cursor < len(raw):
        value, pair = raw[cursor], raw[cursor:cursor+2]
        if value == 4:
            dialogue.need(len(pair)==2 and 0<=pair[1]-bias<len(entries), '대사 사전 코드 범위 오류')
            output.append(expand(entries[pair[1]-bias],reverse,entries,bias,depth+1))
            cursor += 2
        elif value == 9:
            dialogue.need(len(pair)==2, '대사 이름 인수 누락')
            output.append(f'{{name:{pair[1]:02X}}}')
            cursor += 2
        elif pair == b'\x06\x07':
            output.append('{page}')
            cursor += 2
        elif value in (2,5,8,10):
            output.append(
                '\n' if value==8 else
                '{visual}' if value==10 else
                f'{{raw:{value:02X}}}'
            )
            cursor += 1
        else:
            dialogue.need(value>=0x80 and len(pair)==2, '대사 단일 바이트 영문/미완성 문자')
            output.append(reverse[pair] if pair in reverse else pair.decode('shift_jis'))
            cursor += 2
    return ''.join(output)


def verify_final(image, records, texts):
    by_id = {row.id:row for row in records}
    dialogue.need(len(records)==len(by_id)==9508, '최종 일반 대사 9,508개 분모 오류')
    dialogue.need(not set(texts)-set(by_id), '최종 대사 검증의 알 수 없는 수정 ID')
    roots={}
    for pool in dialogue.contiguous_pools(records):
        start=pool[0].cooked_offset
        end=start+sum(row.allocation for row in pool)
        cursor=start
        for row in pool:
            stop=image.find(b'\0',cursor,end)
            dialogue.need(stop>=cursor, f'{row.id}: 최종 종단/순번 누락')
            roots[row.id]=bytes(image[cursor:stop])
            cursor=stop+1
        dialogue.need(not any(image[cursor:end]), f'{pool[0].id}: 최종 대사 풀 뒤 오염')
    cursor=dialogue.S2_DIALOGUE_START
    for ordinal in range(dialogue.S2_DIALOGUE_RECORDS):
        record_id=f'scenario02/dialogue/{ordinal:03d}'
        stop=image.find(b'\0',cursor,dialogue.S2_DIALOGUE_END)
        dialogue.need(stop>=cursor, f'{record_id}: 최종 종단/순번 누락')
        roots[record_id]=bytes(image[cursor:stop])
        cursor=stop+1
    dialogue.need(not any(image[cursor:dialogue.S2_DIALOGUE_END]), '2화 최종 대사 풀 뒤 오염')
    # Scenario 1's three native battle-condition rows are fixed-address
    # consumers, not members of the movable dialogue pools.  Re-read them at
    # their pinned starts and remove only compiler-added trailing blank/no-op
    # padding before performing the same semantic round trip as every other
    # record.
    for record_id in sorted(dialogue.SCENARIO01_MENU_CONDITION_IDS):
        row = by_id[record_id]
        start = row.cooked_offset
        dialogue.need(start is not None, f'{record_id}: 고정 조건 주소 누락')
        raw = bytes(image[start:start + row.allocation])
        stop = raw.find(b'\0')
        dialogue.need(stop >= 0, f'{record_id}: 고정 조건 종단 누락')
        content = raw[:stop]
        while content.endswith(dialogue.SPACE_VISIBLE) or content.endswith(b'\x81\x40'):
            content = content[:-2]
        if content.endswith(b'\x05'):
            content = content[:-1]
        roots[record_id] = content
    dialogue.need(set(roots)==set(by_id), '최종 대사 검증 대상 누락')
    s1=dialogue.load_json(storage.SCENARIO01_PLAN)['dictionary']
    locations={1:(int(s1['start'],0),int(s1['bytes']),1,241),
               2:(dialogue.S2_DICT_START,dialogue.S2_DICT_END-dialogue.S2_DICT_START,1,239)}
    for path in (storage.EARLY_PLAN,storage.PLAN):
        for row in dialogue.load_json(path)['scenarios']:
            scenario=int(row['scenario'])
            dialogue.need(scenario not in locations, '최종 사전 시나리오 중복')
            locations[scenario]=(int(row['dictionary_start'],0),storage.DICTIONARY_BYTES,0,242)
    dialogue.need(set(locations)==set(range(1,71)), '최종 대사 사전 70개 분모 오류')
    tables={}
    for scenario,(start,size,bias,count) in locations.items():
        payload=image[start:start+size]
        dialogue.need(len(payload)==size, '최종 사전 물리 범위 오류')
        entries=bytes(payload).split(b'\0')
        dialogue.need(len(entries)>=count+1, f'{scenario}화 최종 사전 종단 누락')
        tables[scenario]=(entries[:count],bias)
    recovered=[]
    for row in records:
        if row.scenario==2:
            private=with_native_ascii(dialogue._s2_encoding_resources()[0])
            reverse={}
        else:
            private=with_native_ascii(dialogue.early_private_mapping() if row.scenario<=12 and row.scenario!=1
                                      else dialogue.all_dialogue_private_mapping())
            reverse={code:ch for ch,code in dialogue.latest_private_mapping().items()}
        for ch,code in private.items():
            dialogue.need(code not in reverse or reverse[code]==ch, f'{row.id}: 최종 글리프 소유 중복')
            reverse[code]=ch
        reverse={code:(' ' if ch=='\u2009' else ch) for code,ch in reverse.items()}
        try:
            expanded=expand(roots[row.id],reverse,*tables[row.scenario])
            actual=dialogue.encode_direct(dialogue.engine_text(expanded),private)
            expected=dialogue.encode_direct(dialogue.engine_text(texts.get(row.id,row.base_text)),private)
            dialogue.need(actual==expected, f'{row.id}: 최종 대사/사전 문구 또는 제어 불일치')
        except (dialogue.DialogueError,ValueError,UnicodeError,IndexError,KeyError) as exc:
            raise dialogue.DialogueError(f'{row.id}: 최종 네이티브 대사 읽기 실패: {exc}') from exc
        recovered.append((row.id,expanded))
    return dict(records_verified=len(recovered),dictionaries_verified=len(tables),
                expanded_sha256=hashlib.sha256(json.dumps(recovered,ensure_ascii=False).encode()).hexdigest().upper(),
                verified_after_last_writer=True,
                scope='Actual native text and control bytes; not a dialogue layout/runtime pass')
