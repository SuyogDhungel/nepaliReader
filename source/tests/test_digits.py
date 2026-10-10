# Digits, brackets and signs are read as shown; a digit becomes a letter only where the dictionary proves it.
import sys, time
sys.path.insert(0, 'tests/fakenvda'); import setup_fake as F
sys.path.insert(0, 'addon/globalPlugins')
import nepaliReader as NR, speech.speech as SS
from nepaliReader import devanagariRepair as DR, neLexicon, legacyFonts
p = NR.GlobalPlugin()
for _ in range(100):
    if neLexicon.isLoaded(): break
    time.sleep(0.1)
bad = 0
def check(name, got, want):
    global bad
    ok = got == want; bad += not ok
    print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else '\n     got  %r\n     want %r' % (got, want)))

# real digits stay digits
for t in ['ना२ख ९७५७', 'वि.सं. १९८० मा', 'धारा ९ र (९) र (क)', 'नं.पा.-१२', 'राम्रो! कस्तो% स्रोत*', 'गोरखा-९']:
    check('repair keeps ' + t, DR.repair(t, broken=True), t)
    check('isBroken ' + t, DR.isBroken(t), False)
# a number plate is not a damaged word
check('plan: plate', DR.gluedDigitPlan('ना२ख'), None)
# a Preeti digit key inside a word is a letter only if that makes the word
check('plan: बा६ -> बाट', ''.join(DR.gluedDigitPlan('बा६') or []), 'बाट')
check('plan: यु४ -> युद्ध', ''.join(DR.gluedDigitPlan('यु४') or []), 'युद्ध')
check('repair: बा६ रेक८', DR.repair('बा६ रेक८ १९८०', broken=True).split()[0], 'बाट')

# the Preeti keys ( ) between two Preeti words are the digit keys
check('lone ( is ९', legacyFonts.convert('vf; ( hgf', 'preeti'), 'खास ९ जना')
check('( ) of a clause stay brackets', legacyFonts.convert('(s) v', 'preeti'), '(क) ख')

# character and word reading of numbers
F.state['app'] = 'winword'
class Info:
    def __init__(s, text, a, b=None):
        s.full = text; s.start = a; s.end = a + 1 if b is None else b
        s.obj = F.types.SimpleNamespace(windowClassName='_WwG', appModule=F.types.SimpleNamespace(appName='winword'), treeInterceptor=None)
    def copy(s): return Info(s.full, s.start, s.end)
    def expand(s, unit):
        if unit == 'line': s.start, s.end = 0, len(s.full)
        elif unit == 'word':
            a = s.start
            while a > 0 and not s.full[a-1].isspace(): a -= 1
            b = s.start
            while b < len(s.full) and not s.full[b].isspace(): b += 1
            s.start, s.end = a, b
        else: s.end = s.start + 1
    def setEndPoint(s, o, w): s.end = o.start
    def move(s, unit, n): s.start += n; s.end = s.start + 1; return n if 0 <= s.start < len(s.full) else 0
    @property
    def text(s): return s.full[s.start:s.end]
    def getTextWithFields(s, fc): return [s.text]
def said(i, unit): return ''.join(x for x in next(SS.getTextInfoSpeech(i, unit=unit)) if isinstance(x, str))
def chars(t): return [said(Info(t, i), 'character') for i in range(len(t))]
def word(t, i):
    x = Info(t, i); x.expand('word'); return said(x, 'word').strip()
line = 'वि.सं. १९८० मा धारा ९ र (९) र ५०% छ'
check('Unicode digits by character', ''.join(chars(line)), line)
line = 'g]kfnsf] ;+ljwfg @)&@ ;fndf hf/L eof]'
check('Preeti year by word', word(line, line.index('@')), '२०७२')
check('Preeti year by character', ''.join(chars(line)[line.index('@'):line.index('@') + 4]), '२०७२')
line = 'Section 9 (a) of the Act, call (01) 4411234'
check('English numbers by character', ''.join(chars(line)), line)
# Preeti overlay key m after प / भ, stray reph, extra halant (rebuilt PDF words)
for w, want in [('आप्mना', 'आफ्ना'), ('बुभ्mदा', 'बुझ्दा'), ('समेतलार्ई', 'समेतलाई'), ('कार्य्विधिको', 'कार्यविधिको'), ('mobile', None), ('हुनेछ।', None)]:
    got = DR.finalClean(w, neLexicon.isWord)
    check('finalClean ' + w, got, want)

# Fontasy Himali: digit keys are digits, Shift+digits are letters, ' and " are ू and ु
from nepaliReader import legacyFonts as LF
for k, want in [('lnld^]*sf]', 'लिमिटेडको'), ('1= sDkgLsf]', '१. कम्पनीको'), ("b'/;+rf/", 'दूरसंचार'), ('x"g]%', 'हुनेछ'),
		('sf&df*f}+ j*f g+=11', 'काठमाडौं वडा नं.११'), ('-ldlt 2065.12.30_', '(मिति २०६५।१२।३०)'), ('p@]Zo', 'उद्देश्य'), ('P)^]gf', 'एण्टेना')]:
	check('Fontasy ' + k, LF.convert(k, 'fontasy'), want)
check('Fontasy font name', LF.encodingForFontName('FPKWHC+FONTASY_HIMALI_TT'), 'fontasy')
check('Himalb is Preeti layout', LF.encodingForFontName('ABCDEE+Himalb'), 'himali')
check('Preeti ;+3 is संघ', LF.convert(';+3 ;+:yf', 'preeti'), 'संघ संस्था')
check('Preeti year', LF.convert('@)&( ;fn', 'preeti'), '२०७९ साल')
check('real words in a file name stay', DR.cleanShuffled('१.नेपाल-राष्ट्र-बैङ्क-ऐन-२०५८.pdf'), '१.नेपाल-राष्ट्र-बैङ्क-ऐन-२०५८.pdf')
# Fontasy Himali's ¶ glyph is ठ्ठ (closed ठ on top, telecom.pdf), as in Preeti
check('Fontasy ¶ is ठ्ठ', LF.convert('n¶f', 'fontasy'), 'लठ्ठा')
# Sumod-Acharya: Preeti layout but its own glyphs (checked on the font in paper3/rajnitik/deuki.pdf)
for fn in ('BCDFEE+Sumod-Acharya', 'ABCDEE+Sumod Acharya', 'ABCEEE+Sumodbold'):
	check('Sumod font name ' + fn, LF.encodingForFontName(fn), 'sumod')
for k, want in [("d'NofËg4f/f", 'मुल्याङ्कनद्धारा'), ('n}lÍs', 'लैङ्गिक'), ("-tfKn]h'Ísf]", '(ताप्लेजुङ्गको'),
		('lr¶L', 'चिट्ठी'), ('s~rgh∙f', 'कञ्चनजङ्गा'), ('n ¤', 'ल !'), ('cfˆgf]', 'आनो'), ('ˆÇofS;,', 'फ्याक्स,'),
		('kG„', 'पन्'), ('>L…', 'श्री'), ('-ef}lts¸', '(भौतिक'), ('‘k|r08’', '‘प्रचण्ड’'), ("k'¥ofpg", 'पुर्‍याउन'),
		('dxŒj', 'महत्त्व'), ('leœofpg]', 'भित्र्याउने'), ("¿kdf", 'रूपमा')]:
	check('Sumod ' + k, LF.convert(k, 'sumod'), want)
check('Sumod keys as Preeti keys', LF.convert(LF.asPreetiKeys('k|f;l', 'sumod') + 'ª\\s', 'preeti'), 'प्रासङ्कि')
# other Preeti-layout fonts (their glyphs in deuki.pdf match Preeti); Annapurna SIL is a Unicode font
check('Ganesh is Preeti', LF.encodingForFontName('ABCDEE+Ganesh'), 'preeti')
check('HimChuli is Preeti', LF.encodingForFontName('ABCDEE+HimChuli'), 'preeti')
check('Annapurna SIL is not legacy', LF.encodingForFontName('Annapurna SIL'), None)

# correct Unicode is never changed (निर्माण was read र्निमाण, कार्की र्काकी on web pages)
neLexicon.isWord('नेपाल')
for t in ['निर्माण कार्य', 'शर्मा र कार्की', 'मार्का', 'पुनर्निर्माण', 'व्रत', 'ऋतम्', 'नेपाल[१] र भूगोल[सम्पादन]',
		'पनि · अर्को', 'कक्षा १०A', 'दर ४ %', 'सरकार को निर्णय', 'कोभिड19को', 'गर्‍यो']:
	check('correct text kept: ' + t, (DR.cleanShuffled(t), DR.repair(t)), (t, t))
# broken text from PDFs is still repaired where the dictionary proves it
for t, want in [('पाठ्यव्रम', 'पाठ्यक्रम'), ('गनर्', 'गर्न'), ('प्राधिcकरण', 'प्राधिकरण'), ('गाउँपा)लका', 'गाउँपालिका'),
		('जोखि8म', 'जोखिम'), ('रेकडर्', 'रेकर्ड'), ('सं&ा', 'संा')]:
	check('broken repaired: ' + t, DR.repair(t, broken=True), want)

# Devanagari file names shown as mojibake (UTF-8 read as Windows-1252)
check('mojibake title', DR.decodeMojibake('à¤¨à¥‡à¤ªà¤¾à¤² à¤°à¤¾à¤·à¥_à¤Ÿà¥_à¤°.pdf'), 'नेपाल राष्ट्र.pdf')
check('mojibake lost byte proven', DR.decodeMojibake('1632_à¤§à¤°à¥_à¤® x'), '1632_धर्म x')
check('mojibake lost byte unproven stays', DR.decodeMojibake('à¤¸à¤¸à¥_à¤_à¥_à¤¤'), 'à¤¸à¤¸à¥_à¤_à¥_à¤¤')
check('French stays', DR.decodeMojibake('café à la carte'), 'café à la carte')

# text a PDF draws twice for a bold look is read once (नेपाल पर्यटन बोर्ड ऐन heading in Brave)
from nepaliReader import pdfText as PT
class _Doc(PT.DocIndex):
	def __init__(s, B): s.B = B
_d = _Doc("g]kfnko{6gaf]8{sf]:yfkgf/Joj:yfug{ag]sf]P]gkl/R5]b-!k|f/lDes")  # (B holds keys folded by _NORM: – is -)
check('drop repeat exact', _d._dropRepeats("g]kfn ko{6g af]8{sf] g]kfn ko{6g af]8{sf]"), "g]kfn ko{6g af]8{sf]")
check('drop repeat glued to the next text', _d._dropRepeats("kl/R5]b – kl/R5]b –!"), "kl/R5]b – !")
check('drop repeat cut by the line end', _d._dropRepeats("g]kfn ko{6g af]8{sf] :yfkgf / Joj:yf ug{ ag]sf] P]g g]kfn ko{6g af]8{sf] :yfkgf / Joj:yf ug{ ag]sf]"),
	"g]kfn ko{6g af]8{sf] :yfkgf / Joj:yf ug{ ag]sf] P]g")
_d2 = _Doc("kmkmlkmlkmkm/fd/fd/fdkm")
check('a real repeat stays', _d2._dropRepeats("/fd /fd /fd"), "/fd /fd /fd")
check('glyph name variant', PT._glyphNameToText('eight.alt'), '8')
print('FAILED' if bad else 'ALL OK', bad)
sys.exit(1 if bad else 0)
