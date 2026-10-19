# Nepali eSpeak: the synthesizer switches between its Nepali and English voices by script and never
# changes the text; the Nepali Reader built into it is always on and works only in PDFs and Word.
import sys, os, time, types, importlib.util
sys.path.insert(0, 'tests/fakenvda'); import setup_fake as F
sys.path.insert(0, 'addon/globalPlugins')
FC, FF = F.FieldCommand, F.FormatField
bad = 0


def check(name, got, want):
	global bad
	ok = got == want
	bad += not ok
	print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else '\n     got  %r\n     want %r' % (got, want)))


# -- the synthesizer --------------------------------------------------------------------------
class LangChangeCommand:
	def __init__(self, lang):
		self.lang = lang

	def __repr__(self):
		return 'Lang(%s)' % self.lang


class CharacterModeCommand:
	def __init__(self, state):
		self.state = state


cmds = F.mod('speech.commands', LangChangeCommand=LangChangeCommand, CharacterModeCommand=CharacterModeCommand)
sys.modules['speech'].commands = cmds
said = []


class Espeak:
	_language = 'en'

	def speak(self, seq):
		said.append(seq)


F.mod('synthDrivers.espeak', SynthDriver=Espeak)
spec = importlib.util.spec_from_file_location('nepaliEspeakSynth', os.path.join('espeak', 'synthDrivers', 'nepaliEspeak.py'))
NE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(NE)


def show(seq):
	return ' '.join('<%s>' % x.lang if isinstance(x, LangChangeCommand) else x if isinstance(x, str) else type(x).__name__ for x in seq)


synth = NE.SynthDriver()
check('synth name', (synth.name, synth.description), ('nepaliEspeak', 'Nepali eSpeak'))


def speak(*items, voice='en'):
	synth._language = voice
	said.clear()
	synth.speak(list(items))
	return show(said[0])


check('English voice: Nepali words in the Nepali voice', speak('Hello नमस्ते world'), 'Hello  <ne> नमस्ते  <None> world')
check('numbers go with the words beside them', speak('२०८३ साल 10:00 बजे, then 5 pm'), '<ne> २०८३ साल 10:00 बजे,  <None> then 5 pm')
check('a number alone stays in the voice\'s language', speak('25'), '25')
check('Devanagari digits are Nepali', speak('१ / ४३'), '<ne> १ / ४३')
check('the text itself is never changed', speak('g]kfn ;/sf/'), 'g]kfn ;/sf/')
check('Nepali voice: English in the English voice', speak('नेपाल Nepal', voice='ne'), 'नेपाल  <en> Nepal')
check('a page that says its text is English', speak(LangChangeCommand('en-US'), 'Login लगइन'), '<en-US> Login  <ne> लगइन')
check('a page that says its Devanagari is Hindi', speak(LangChangeCommand('hi'), 'नमस्ते'), '<hi> नमस्ते')
check('other scripts keep what the page says', speak(LangChangeCommand('ar'), 'مرحبا'), '<ar> مرحبا')
check('spelling a character', speak(CharacterModeCommand(True), 'क', CharacterModeCommand(False)), 'CharacterModeCommand <ne> क CharacterModeCommand')
check('several strings, one switch', speak('नेपाल ', 'सरकार', ' Office'), '<ne> नेपाल  सरकार <None>  Office')

# -- the reader inside Nepali eSpeak ------------------------------------------------------------
here = os.path.join('addon', 'globalPlugins', 'nepaliReader')
spec = importlib.util.spec_from_file_location('nepaliEspeakReader', os.path.join(here, '__init__.py'), submodule_search_locations=[here])
ER = importlib.util.module_from_spec(spec)
sys.modules['nepaliEspeakReader'] = ER
spec.loader.exec_module(ER)
check('embedded mode', ER.EMBEDDED, True)
running = []
sys.modules['addonHandler'].getRunningAddons = lambda: [types.SimpleNamespace(name=n) for n in running]
panels = list(F.NVDASettingsDialog.categoryClasses)
p = ER.GlobalPlugin()
time.sleep(0.5)
check('no settings panel', F.NVDASettingsDialog.categoryClasses, panels)
fg = {}
F.sys.modules['api'].getForegroundObject = lambda: types.SimpleNamespace(windowHandle=fg['h'], name=fg['title'], appModule=types.SimpleNamespace(appName=fg['app']), processID=1)


def front(app, title, h):
	fg.update(app=app, title=title, h=h)
	F.state['app'] = app
	F.state['title'] = title
	ER._KIND[0] = None


class Doc:
	def __init__(self, fields):
		self.fields = fields
		self.obj = types.SimpleNamespace(windowClassName='X', appModule=types.SimpleNamespace(appName=fg['app']))

	def getTextWithFields(self, fc=None):
		return list(self.fields)

	@property
	def text(self):
		return ''.join(f for f in self.fields if isinstance(f, str))


def font(n):
	return FC('formatChange', FF({'font-name': n}))


def spoken(fields):
	import speech.speech as SS
	return ''.join(x for x in next(SS.getTextInfoSpeech(Doc(fields))) if isinstance(x, str))


front('chrome', 'Nepal News - Google Chrome', 11)
check('web page: off', ER.isOn(), False)
check('web page: Preeti font text left as it is', spoken([font('Preeti'), 'g]kfn ;/sf/']), 'g]kfn ;/sf/')
check('web page: Unicode left as it is', spoken(['नेपाल सरकार']), 'नेपाल सरकार')
check('web page: names left as they are', p._filterSpeechSequence(['g]kfn']), ['g]kfn'])
front('notepad', 'notes - Notepad', 12)
check('other app: off', ER.isOn(), False)
front('explorer', 'pdf files', 13)
check('a folder named pdf is not a PDF', ER.isOn(), False)
front('winword', 'notice.docx - Word', 14)
check('Word: on', ER.isOn(), True)
check('Word: Preeti read as Nepali', spoken([font('Preeti'), 'g]kfn ;/sf/']), 'नेपाल सरकार')
check('Word: English left as it is', spoken([font('Calibri'), 'Office of the Prime Minister']), 'Office of the Prime Minister')
check('Word: Unicode is not repaired', ER.conf()['repairUnicode'], False)
front('chrome', 'notice.pdf - Google Chrome', 11)
check('PDF in Chrome: on', ER.isOn(), True)
check('PDF: Unicode repaired', ER.conf()['repairUnicode'], True)
check('the reader adds no language changes (the synthesizer does)', ER.conf()['switchLanguage'], False)
front('acrord32', 'notice.pdf - Adobe Acrobat Reader', 15)
check('PDF reader: on', ER.isOn(), True)
ER.setOn(False)
check('nothing to switch off', ER.isOn(), True)

# the separate Nepali Reader add-on is running: it does the work, the built-in reader stays out
running.append('nepaliReader')
p2 = ER.GlobalPlugin()
check('defers to the separate add-on', ER.isOn(), False)
ER._DEFER[0] = False

print('FAILED' if bad else 'ALL OK', bad)
sys.exit(1 if bad else 0)
