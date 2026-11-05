# Typed Unicode (web pages, Word) and the Preeti converter: faults found on real Nepali websites and
# in other open-source converters' test vectors. Run from the source folder: python tests/test_typed.py
import sys, time, types
sys.path.insert(0, 'tests/fakenvda'); import setup_fake as F
sys.path.insert(0, 'addon/globalPlugins')
F.sys.modules['config'].conf.profiles = [{}]
import nepaliReader as NR, speech.speech as SS
from nepaliReader import devanagariRepair as dr, legacyFonts as lf, neLexicon

failures = []


def check(name, got, want):
    ok = got == want
    print(('ok   ' if ok else 'FAIL ') + f'{name}: {got}' + ('' if ok else f'   (want {want})'))
    if not ok:
        failures.append(name)


neLexicon.load()
print('== typed Unicode: faults from old Preeti converters, as counted on 72,000 news articles')
for bad, good in [
    ('केन्दि्रत', 'केन्द्रित'), ('लोकपि्रय', 'लोकप्रिय'), ('टि्वटरमा', 'ट्विटरमा'), ('मडि्रडको', 'मड्रिडको'),
    ('अर्काे', 'अर्को'), ('भएकोे', 'भएको'), ('काठमाडाैं', 'काठमाडौं'), ('स्मार्टफोनकेा', 'स्मार्टफोनको'), ('युराोपियन', 'युरोपियन'),
    ('गर्दैै', 'गर्दै'), ('सुुरु', 'सुरु'), ('नंं', 'नं'), ('विद्युत््', 'विद्युत्'),
    ('हँुदै', 'हुँदै'), ('बंैक', 'बैंक'), ('सधँै', 'सधैँ'),
    ('नयाा', 'नयाँ'), ('पााच', 'पाँच'), ('बााकी', 'बाँकी'), ('लाागि', 'लागि'),
    ('पु¥याउने', 'पुर्‍याउने'), ('ग¥यो', 'गर्‍यो'), ('२०७३÷७४', '२०७३/७४'),
    ('अाफ्नो', 'आफ्नो'), ('सीइअो', 'सीइओ'),
    ('जिल्ल्ाा', 'जिल्ला'), ('स्व्ाास्थ्य', 'स्वास्थ्य'),
    ('निणर्ायक', 'निर्णायक'), ('वषर्ीय', 'वर्षीय'),
    ('दु्रतगतिको', 'द्रुतगतिको'), ('गु्रप', 'ग्रुप'), ('थुपै्र', 'थुप्रै'),
    ('लािग', 'लागि'), ('छुटृाछुट्टै', 'छुट्टाछुट्टै'),
    ('समय ः ५ बजे', 'समय : ५ बजे'),
]:
    check(bad, dr.repairTyped(bad), good)

print('== correct text is never changed')
for good in ['गरेपछि केन्द्रित', 'देउतीको निक्कै नहुने', 'दुबै खासै लगतै एकै पूरै राम्रै', 'यहाँको यसैले सहितको सघाउँछ गरें',
             'गर्नुपर्ने पुनःनिर्माण किनकि स्मार्टफोनमा', 'गर्‍यो पुर्‍याउने र्‍याली', 'दृष्टि कर्तृत्व हृदय',
             'अतः पुनः दुःख', 'ँ ं ः', 'रूपान्तरण रुपान्तरण', 'वि.सं. २०८३ साल', '२’को ‘ए’को']:
    check(good, dr.repairTyped(good), good)
    if good != 'ँ ं ः':  # (a list of the signs: looked at, and kept)
        check('no fault seen in ' + good, dr.hasTypedFault(good), False)

print('== a web page in Chrome: faults fixed, every other word as written')
p = NR.GlobalPlugin()
while not p._ready:
    time.sleep(0.05)
F.state['app'] = 'chrome'; F.state['title'] = 'Online Khabar - Google Chrome'


class D:
    def __init__(s, t):
        s.t = t
        s.obj = types.SimpleNamespace(rootNVDAObject=types.SimpleNamespace(appModule=types.SimpleNamespace(appName='chrome')))

    def getTextWithFields(s, fc):
        return [s.t]
    text = property(lambda s: s.t)
    boundingRects = []


def spoken(t):
    return ''.join(x for x in next(SS.getTextInfoSpeech(D(t))) if isinstance(x, str))


check('news line with a converter fault', spoken('सरकार केन्दि्रत भएपछि गरेपछि देउतीको निक्कै नहुने अर्काे'), 'सरकार केन्द्रित भएपछि गरेपछि देउतीको निक्कै नहुने अर्को')
check('later lines of the same page', spoken('दुबै खासै लगतै एकै पूरै सहितको गरें नगर्ने एकजना'), 'दुबै खासै लगतै एकै पूरै सहितको गरें नगर्ने एकजना')
check('eyelash ra from a Preeti key', spoken('काम ग¥यो र पु¥याउने'), 'काम गर्‍यो र पुर्‍याउने')

print('== Preeti converter (cases where other converters\' test vectors and the font itself disagreed with us)')
for keys, want in [("k|:'tt", 'प्रस्तुत'), ('k6[L', 'पट्टी'), ('c8[f', 'अड्डा'), ('¿kfGt/0f', 'रूपान्तरण'), ('lgs¿~h', 'निकुञ्ज'),
                   ('x¿', 'हरू'), ("b'¿kof]u", 'दुरूपयोग'), ('c+‍u|]h', 'अं‍ग्रेज'), ('¥of', 'र्‍या'), ('ug{', 'गर्न')]:
    check(repr(keys), lf.convert(keys, 'preeti'), want)

print(f'\n{"all passed" if not failures else str(len(failures)) + " failed"}')
sys.exit(1 if failures else 0)
