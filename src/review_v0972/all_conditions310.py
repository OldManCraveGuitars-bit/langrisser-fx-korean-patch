"""Source-reviewed conditions only; preserve every other text consumer and code."""
import sys,json,re,struct,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'analysis/all-conditions-review-310'),str(ROOT/'analysis/super-mode-review'),str(ROOT/'analysis/full-dialogue-review-307'),str(ROOT/'tools')]
import survey310 as sv,condition_core as cc,condition_native_codec as nc,presentation_dictionary as pd
import dialogue_core as d,font_candidate as font,compile_review as cr
from muscle_temple_dialogue import split_rows

MENU={
 6:{5:' ・다크 로드 입수'},7:{7:' ・주민 전멸'},9:{7:' ・주민 전멸'},
 11:{7:' ・{name:0C}이 랑그릿사에',8:'    도착'},
 17:{7:' ・홀리로드를 가진 적이',8:'    화면 아래로 탈출'},
 25:{5:'    뱀파이어 로드 격파'},28:{7:' ・주민 전멸'},
 31:{7:' ・홀리로드를 가진 적이',8:'    화면 아래로 탈출'},
 33:{7:' ・홀리로드를 가진 적이',8:'    화면 아래로 탈출'},
 40:{4:' ・랑그릿사 입수',7:' ・랑그릿사를 빼앗김'},
 42:{7:' ・적이 화면 위로 탈출'},
 44:{4:' ・{name:01} 외 전원 격파',5:' ・{name:0F}·{name:01} 인접',7:' ・{name:01} 사망 또는 탈출'},
 46:{5:'    또는 설득'},53:{5:'    또는 설득'},
 58:{8:'    화면 위로 탈출'},
 59:{4:' ・{name:01} 외 전원 격파',5:' ・{name:0B}를 {name:01}에게',6:'    인접시키기',7:' ・{name:01} 사망 또는 탈출'},
 60:{9:' ・{name:15} 그리고'},
}

def selected(doc):
    n=doc['native'];menu={};frames={}
    for row in doc['menu']:
        text=row['current'].replace('\u2009',' ')
        if row['residual']:
            text=row['original']
            # The exact same fixed staff abbreviation is already reviewed as
            # 신도O in native79..84 (their original menus also spell it S藤).
            # Keep it literal, not a newly introduced protagonist variable.
            text=text.replace('Ｓ藤','신도O').replace('の死亡',' 사망').replace('死亡',' 사망')
            text=text.replace('の撃破',' 격파').replace('がマップ下へ逃亡',' 아래로 탈출').replace('が画面下に移動',' 화면 아래로 이동')
            text=text.replace('{raw:05}',' ')
            assert not sv.JP.search(text.replace('・','')),(n,text)
            menu[row['row']]=text
        elif '적전멸' in text:menu[row['row']]=text.replace('적전멸','적 전멸')
    menu.update(MENU.get(n,{}))
    for f in doc['presentation']:
        before=f['current'].replace('\u2009',' ')
        text=before.replace('쉐리','셰리').replace('마을 전멸','주민 전멸').replace('다크로드','다크 로드')
        original=next((r['original'] for r in doc['original_presentation'] if r['frame']==f['frame']),'')
        if 'Ｓ藤' in original:text=text.replace('엘윈','신도O')
        text=text.replace(' ・소니아 아군화\n ・소니아 격파',' ・소니아 격파 또는 설득')
        if before!=text:frames[f['frame']]=text
    return menu,frames

def encode(text):
    text=text.replace('{wait:07}','') # encode_plain page emits native06/07
    raw,missing=d.encode_plain(text,font.mapping());assert not missing,missing
    nc.units(raw)
    return raw

def presentation_raw(text,dd):
    raw=encode(text)
    for label,code in (('*승리조건',28),('*패배조건',29)):
        root=bytes((4,code));expanded=sv.survey.legacy_expand(root,dd)
        assert sv.render(root,dd,sv.survey.reverse_mapping())==label
        raw=raw.replace(encode(label),expanded)
    return raw

def refs(raw,rows):
    codes=set(pd._references(raw));pending=list(codes)
    while pending:
        c=pending.pop();assert 1<=c<=len(rows)
        for v in pd._references(rows[c-1]):
            if v not in codes:codes.add(v);pending.append(v)
    return codes

def live(image,s,dd):
    # Exact expanded content of all unrelated text sections, including shop/save.
    return {i:sv.survey.legacy_expand(bytes(image[s[i]:s[i+1]]),dd) for i in (0,3,5)}

def plan(image):
    assert hashlib.sha256(image).hexdigest().upper()=='C257BD326AE49B88DF20CE1265D518EA5CA631458AC9EBB5ABBDD21E44EC4102'
    docs=sv.run(image);writes=[];audit=[]
    for doc in docs:
        menu,frames=selected(doc)
        if not(menu or frames):continue
        n=doc['native'];s=doc['sections'];dd=pd._split_dictionary(image[s[4]:s[5]])
        cn=sv.cb.required_rows(image[s[6]:s[7]],sv.cb.required_records(n))
        pf,suffix=cc.split_frames(image[s[7]:s[8]])
        old_cn=list(cn);old_pf=list(pf)
        # Prefer literal CN strings when the native table has room. Some
        # fully reviewed dialogue pools (notably77) own every high dictionary row.
        for ordinal,text in menu.items():cn[ordinal-1]=encode(text)
        for ordinal,text in frames.items():
            literal=presentation_raw(text,dd)
            inline=literal
            for code in (28,29):inline=inline.replace(sv.survey.legacy_expand(bytes((4,code)),dd),bytes((4,code)))
            assert sv.survey.legacy_expand(inline,dd)==literal
            pf[ordinal]=inline
        # Protect every other root and its transitive dictionary dependencies.
        protected=set(range(1,157))|set(pd.RUNTIME_RESERVED_DICTIONARY_CODES)
        for i in (0,3,5):protected|=refs(image[s[i]:s[i+1]],dd)
        for i,b in enumerate(cn,1):
            if i not in menu:protected|=refs(b,dd)
        for i,b in enumerate(pf):
            if i not in frames:protected|=refs(b,dd)
        free=[c for c in range(157,240) if c not in protected]
        rows=list(dd);changed=[]
        for kind,choices in (('menu',menu),('presentation',frames)):
            for ordinal,text in choices.items():
                raw=encode(text) if kind=='menu' else presentation_raw(text,dd)
                if kind=='menu':
                    source=next(x for x in doc['menu'] if x['row']==ordinal)
                    js=doc['source_sections'];jd=pd._split_dictionary(sv.read_cooked(sv.ORIGINAL,js[4],js[5]-js[4]))
                    expected=sv.survey.legacy_expand(bytes.fromhex(source['source_hex']),jd)
                    assert cr.legacy_signature(raw)==cr.legacy_signature(expected),(n,ordinal,'menu source operands')
                    widths=cc.condition_line_widths(text)
                    assert len(widths)==1 and widths[0]<=176,(n,ordinal,widths,text)
                    assert source['current'] and source['original'],(n,ordinal,'blank ownership')
                    before=source['current']
                else:
                    assert cr.legacy_signature(raw)==cr.legacy_signature(sv.survey.legacy_expand(old_pf[ordinal],dd)),(n,ordinal,'frame control')
                    visible=text.replace('{page}','').replace('{wait:07}','')
                    widths=cc.condition_line_widths(visible);assert max(widths)<=176 and len(widths)<=4,(n,ordinal,widths)
                    before=next(f['current'] for f in doc['presentation'] if f['frame']==ordinal)
                code=None
                compress=(sum(len(b)+1 for b in cn)>s[7]-s[6]) if kind=='menu' else (sum(map(len,pf))+1>s[8]-s[7])
                if compress:
                    assert free,(n,'unused dictionary capacity')
                    code=max(free,key=lambda c:(len(rows[c-1]),-c));free.remove(code);rows[code-1]=raw
                    if kind=='menu':cn[ordinal-1]=bytes((4,code))
                    else:pf[ordinal]=bytes((4,code))+b'\x06\x07';rows[code-1]=raw.removesuffix(b'\x06\x07')
                changed.append(dict(kind=kind,row=ordinal,before=before,after=text,code=code,widths=widths))
        cleared=[]
        for code in sorted(free,key=lambda c:(-len(rows[c-1]),c)):
            if sum(len(b)+1 for b in rows)<=s[5]-s[4]:break
            if rows[code-1]:rows[code-1]=b'';cleared.append(code)
        dictionary=b''.join(b+b'\0' for b in rows)
        assert len(dictionary)<=s[5]-s[4],(n,'dictionary bytes',len(dictionary),s[5]-s[4])
        assert all(rows[c-1]==dd[c-1] for c in protected)
        block=b'\0'.join(cn)+b'\0';pres=b''.join(pf)+suffix
        # The presentation suffix has only post-terminator zeros. It can be
        # resized inside the existing allocation without touching section8.
        if frames:
            live_suffix=suffix.rstrip(b'\0');assert not live_suffix,(n,'presentation suffix')
            pres=b''.join(pf)+b'\0'
        assert len(block)<=s[7]-s[6] and len(pres)<=s[8]-s[7],(n,'fixed pool capacity')
        assert len(cn)==len(old_cn) and [bool(b) for b in cn]==[bool(b) for b in old_cn]
        assert len(pf)==len(old_pf)
        for i,b in enumerate(cn,1):
            expected=encode(menu[i]) if i in menu else sv.survey.legacy_expand(old_cn[i-1],dd)
            assert sv.survey.legacy_expand(b,rows)==expected,(n,i,'menu expansion')
        for i,b in enumerate(pf):
            expected=presentation_raw(frames[i],dd) if i in frames else sv.survey.legacy_expand(old_pf[i],dd)
            assert sv.survey.legacy_expand(b,rows)==expected,(n,i,'presentation expansion')
        before_live=live(image,s,dd);assert before_live==live(image,s,rows),(n,'unrelated consumer change')
        for a,b,new,label in ((s[4],s[5],dictionary,'dictionary'),(s[6],s[7],block,'menu'),(s[7],s[8],pres,'presentation')):
            new=new.ljust(b-a,b'\0')
            if new!=image[a:b]:writes.append((a,bytes(image[a:b]),new,f'conditions310/{n}/{label}'))
        audit.append(dict(native=n,changed=changed,unrelated_text_exact=True,cleared_unreferenced=cleared,protected_codes=sorted(protected),dictionary_used=len(dictionary),dictionary_capacity=s[5]-s[4]))
    return writes,dict(all_tables=98,changes=audit,menu_rows=sum(c['kind']=='menu' for r in audit for c in r['changed']),presentation_frames=sum(c['kind']=='presentation' for r in audit for c in r['changed']))

if __name__=='__main__':
    w,a=plan(sv.BASE.read_bytes());p=sv.HERE/'preflight310.json';p.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({k:v for k,v in a.items() if k!='changes'}))
