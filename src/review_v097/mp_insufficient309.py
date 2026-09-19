"""Use native two-byte MP glyphs, retaining the fixed common-root extent."""
import magic_charm_name as charm
OLD=bytes.fromhex('4d50f1e6f1f6f24e814000')
NEW=bytes.fromhex('826c826f05f1f6f24e0500')
def plan(image):
    bases=charm.offsets(image);places=[]
    for base in bases:
        # Common magic-name base has a pinned +0xE5 origin from section0.
        p=image.find(OLD,base,base+0x300)
        assert p>=0 and image.find(OLD,p+len(OLD),base+0x300)<0
        places.append(p)
    found=[];p=0
    while (p:=image.find(OLD,p))>=0:found.append(p);p+=len(OLD)
    assert found==places and len(OLD)==len(NEW) and NEW.count(0)==1
    return [(p,OLD,NEW,f'mp-insufficient309/{i:03d}') for i,p in enumerate(places)],dict(copies=len(places),text='MP 부족',locations=places,
        native_paired_MP=True,original_NUL_and_allocation=True,code_font_spell_cost_unchanged=True)
