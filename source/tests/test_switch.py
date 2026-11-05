# NVDA+Ctrl+Shift+Space switches the add-on completely off and on again (mock NVDA, not Windows).
# Run from the source folder: python tests/test_switch.py
import os, sys, tempfile, threading, time
sys.path.insert(0, 'tests/fakenvda'); import setup_fake as F
sys.path.insert(0, 'addon/globalPlugins')
import speech, speech.speech as SS, textInfos, api, cursorManager, virtualBuffers, documentBase
if not hasattr(speech, 'filter_speechSequence'):
    speech.filter_speechSequence = F.Filter()
if not hasattr(api, 'copyToClip'):
    api.copyToClip = lambda text, notify=False: True
import inputCore
inputCore.decide_executeGesture = F.Filter()  # NVDA's "a key is about to be handled"
import nepaliReader as NR

FC, FF = F.FieldCommand, F.FormatField
failures = []


def check(name, ok, detail=''):
    print(('ok   ' if ok else 'FAIL ') + name + (('  ' + str(detail)) if detail and not ok else ''))
    if not ok:
        failures.append(name)


# Everything the add-on may replace while it is on
WATCH = [(SS, 'getTextInfoSpeech'), (speech, 'getTextInfoSpeech'), (speech.sayAll.SayAllHandler, '_getTextInfoSpeech'),
         (textInfos.TextInfo, 'copyToClipboard'), (cursorManager.CursorManager, 'script_copyToClipboard'), (api, 'copyToClip'),
         (SS, 'speakSelectionChange'), (speech, 'speakSelectionChange')]
for cls in (virtualBuffers.VirtualBuffer, virtualBuffers.VirtualBufferTextInfo, documentBase.DocumentWithTableNavigation):
    for name in list(vars(cls)):
        if not name.startswith('__'):
            WATCH.append((cls, name))
ORIGINAL = {(id(o), n): getattr(o, n, None) for o, n in WATCH}


def hooked():
    return sorted(f'{getattr(o, "__name__", type(o).__name__)}.{n}' for o, n in WATCH if getattr(o, n, None) is not ORIGINAL[(id(o), n)])


class Doc:
    def __init__(s, fields):
        s.fields = fields
        s.obj = F.types.SimpleNamespace(windowClassName='_WwG', appModule=F.types.SimpleNamespace(appName='winword'), treeInterceptor=None)

    def getTextWithFields(s, fc):
        return list(s.fields)

    def copy(s):
        return s


def reads():
    return ''.join(x for x in next(SS.getTextInfoSpeech(Doc([FC('formatChange', FF({'font-name': 'Preeti'})), 'g]kfn ;/sf/']))) if isinstance(x, str))


def threads(prefix='NepaliReader'):
    return [t.name for t in threading.enumerate() if t.name.startswith(prefix)]


# --- started while on ------------------------------------------------------------
F.conf['nepaliReader']['enabled'] = True
NR._ON[0] = None
p = NR.GlobalPlugin()
time.sleep(2)
check('on at start: speech and other hooks attached', 'getTextInfoSpeech.getTextInfoSpeech' not in hooked() and len(hooked()) >= 4, hooked())
check('on at start: Preeti is read as Nepali', reads() == 'नेपाल सरकार', reads())
check('on at start: speech filter registered', len(speech.filter_speechSequence.h) == 1)
check('on at start: keys watched (background work rests while NVDA answers a key)', len(inputCore.decide_executeGesture.h) == 1)

p._toggleEnabled()
check('off: every hook removed', hooked() == [], hooked())
check('off: speech filter removed', speech.filter_speechSequence.h == [])
check('off: keys no longer watched', inputCore.decide_executeGesture.h == [])
check('off: Preeti is read as typed (NVDA alone)', reads() == 'g]kfn ;/sf/', reads())
check('off: no Nepali Reader thread running', threads() == [], threads())
check('off: overlay class not used', (lambda l: (p.chooseNVDAObjectOverlayClasses(None, l), l)[1])([]) == [])

p._toggleEnabled()
check('on again: hooks attached', len(hooked()) >= 4, hooked())
check('on again: Preeti is read as Nepali', reads() == 'नेपाल सरकार', reads())
check('on again: one speech filter, not two', len(speech.filter_speechSequence.h) == 1)
for _ in range(3):
    p._toggleEnabled(); p._toggleEnabled()
check('after switching six more times: still one filter and reading right', len(speech.filter_speechSequence.h) == 1 and reads() == 'नेपाल सरकार')
check('after switching six more times: one key watch, not several', len(inputCore.decide_executeGesture.h) == 1)

# --- a PDF being read when switched off ------------------------------------------
pdf = os.environ.get('SWITCH_TEST_PDF')
if pdf and os.path.isfile(pdf):
    cache = NR._cacheDir()
    before = set(os.listdir(cache)) if os.path.isdir(cache) else set()
    st = NR._PdfState(); st.status = 'building'
    t = threading.Thread(target=p._buildPdf, args=(st, 'file:///' + os.path.abspath(pdf).lstrip('/'), os.path.basename(pdf), None, p._generation), name='NepaliReaderPdf')
    t.start(); time.sleep(1.5)
    p._toggleEnabled(); t0 = time.monotonic(); t.join(10)
    took = time.monotonic() - t0
    after = set(os.listdir(cache)) if os.path.isdir(cache) else set()
    check('off while a PDF is read: the work stops within half a second', not t.is_alive() and took < 0.5, f'{took:.2f} s')
    # (a long PDF's first two pages may already have been ready while the mode was on)
    check('off while a PDF is read: the whole text is neither published nor saved', st.status == 'none' and not st.full and after == before, (st.status, st.full, after - before))
    p._toggleEnabled()
else:
    print('skip PDF stop test (set SWITCH_TEST_PDF to a large PDF)')

# --- settings dialog ---------------------------------------------------------------
NR.setOn(False)
check('settings OK with Nepali mode unchecked: every hook removed', hooked() == [] and speech.filter_speechSequence.h == [])
NR.setOn(True)
check('settings OK with Nepali mode checked: attached again', len(hooked()) >= 4 and reads() == 'नेपाल सरकार')
p.terminate()
check('NVDA exit: every hook removed', hooked() == [] and speech.filter_speechSequence.h == [] and inputCore.decide_executeGesture.h == [])

# --- started while off ---------------------------------------------------------------
F.conf['nepaliReader']['enabled'] = False
NR._ON[0] = None
q = NR.GlobalPlugin()
time.sleep(0.3)
check('off at start: nothing attached', hooked() == [] and speech.filter_speechSequence.h == [], hooked())
check('off at start: no work started (word lists not even loaded)', threads() == [] and not q._ready and not q._dictLoading)
q._toggleEnabled(); time.sleep(2)
check('switched on after an off start: attached and reading right', len(hooked()) >= 4 and reads() == 'नेपाल सरकार', reads())
q.terminate()

print(f'\n{"all passed" if not failures else str(len(failures)) + " failed"}')
sys.exit(1 if failures else 0)
