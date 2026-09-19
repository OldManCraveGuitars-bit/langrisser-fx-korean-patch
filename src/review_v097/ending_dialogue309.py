"""All 18 non-epilogue ending speeches, using their native ordinal pools."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'analysis/super-mode-review'),str(ROOT/'analysis/full-dialogue-review-307')]
import dialogue_core as d,presentation_dictionary as pd,condition_native_codec as nc
import packing,font_candidate,compile_review as cr
from muscle_temple_dialogue import split_rows
SOURCE=ROOT/'analysis/scenario50-ending-review-309/ending-source.json'
INPUT=ROOT/'dialogue_editor/scenario50_ending_review309.json'
FAMILY='ending-dialogue309'
def docs():return [x for x in json.loads(SOURCE.read_bytes()) if x['index'] in (102,104)]
def selected():return {f'ending-dialogue/{k}':cr.fit(v) for k,v in json.loads(INPUT.read_bytes())['ending'].items()}
def encode(text):
    raw,missing=d.encode_plain(text,d.with_native_ascii(font_candidate.mapping()))
    d.need(not missing,'Ending missing glyphs '+str(missing))
    d.need(not d.portrait_layout_inspection(text)['failures'],'Ending layout')
    nc.units(raw);return raw
def records():
    texts=selected();rows=[]
    for doc in docs():
        for r in doc['records']:
            if not r['original']:continue
            key=r['id'];assert key in texts
            rows.append(d.DialogueRecord(key,doc['index'],r['original'].replace('{wait:07}',''),texts[key],None,-1,-1,FAMILY,r['current'].replace('{wait:07}','')))
    assert len(rows)==len(texts)==18
    return rows
def plan(image,texts=None,strict=True):
    chosen=selected();chosen.update({k:v for k,v in (texts or {}).items() if k in chosen})
    writes=[];audits=[]
    for doc in docs():
        s=doc['sections'];di=doc['dictionary_index'];si=doc['pool_index'];ei=doc['end_index']
        before=bytes(image[s[si]:s[ei]]);db=bytes(image[s[di]:s[di+1]])
        if strict:
            assert hashlib.sha256(before).hexdigest().upper()==doc['pool_sha256']
            assert hashlib.sha256(db).hexdigest().upper()==doc['dictionary_sha256']
        else:
            # Old editor190 and current308 share the untranslated ending pool.
            assert before==bytes.fromhex(''.join(r['current_raw_hex']+'00' for r in doc['records'])), 'Unknown editor ending preimage'
        kd=pd._split_dictionary(db);old=split_rows(before,len(doc['records']));literal=[];audit=[]
        for r in doc['records']:
            if not r['original']:literal.append(b'');continue
            key=r['id'];text=chosen[key];raw=encode(text)
            assert cr.legacy_signature(raw)==cr.legacy_signature(bytes.fromhex(r['original_expanded_hex'])),key+' controls'
            literal.append(raw);audit.append(dict(id=key,original=r['original'],text=text,expanded_hex=raw.hex(),layout=d.portrait_layout_inspection(text)))
        # Section0 shared UI and the entire 134-row epilogue table own dictionary
        # references. Preserve their transitive closures, never assume unused.
        refs=set(pd._references(bytes(image[s[0]:s[1]])))
        for row in split_rows(bytes(image[s[7]:s[8]]),134):refs.update(pd._references(row))
        pending=list(refs)
        while pending:
            for c in pd._references(kd[pending.pop()-1]):
                if c not in refs:refs.add(c);pending.append(c)
        dictionary,pool,packed=packing.pack_dialogue(literal,kd,refs,len(db),len(before))
        nd=pd._split_dictionary(dictionary)
        assert all(kd[c-1]==nd[c-1] for c in refs)
        assert [nc.expand(r,nd) for r in split_rows(pool,len(literal))]==literal
        assert all(literal[i]==b'' for i,r in enumerate(doc['records']) if not r['original'])
        if dictionary!=db:writes.append((s[di],db,dictionary,f'ending309/{doc["index"]}/dictionary'))
        writes.append((s[si],before,pool,f'ending309/{doc["index"]}/dialogue'))
        audits.append(dict(index=doc['index'],records=audit,packing=packed,protected_external_codes=sorted(refs),native_records=len(literal)))
    return writes,dict(logical_speeches=18,resources=audits,events_epilogues_fonts_untouched=True)
