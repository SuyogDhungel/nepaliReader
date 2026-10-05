# -*- coding: utf-8 -*-
# Nepali Reader for NVDA
# Reads Preeti / Kantipur / Sagarmatha / Himali / PCS Nepali and Kruti Dev (Hindi)
# legacy-font text as Devanagari, repairs jumbled Devanagari from PDFs, and provides
# offline Nepali/Hindi/English OCR with Tesseract. Licensed under the GNU GPL v2 or later.
#
# Only DOCUMENT TEXT is touched: the add-on wraps NVDA's getTextInfoSpeech, which is what
# speaks text under the caret / review cursor, say all and browse mode. Menus, dialogs,
# buttons and NVDA's own messages never pass through it.

import ctypes
import hashlib
import os
import pickle
import threading
import time
import zlib
from collections import OrderedDict

import addonHandler
import api
import config
import globalPluginHandler
import textInfos
import tones
import ui
import wx
from gui import guiHelper
from gui.settingsDialogs import NVDASettingsDialog, SettingsPanel
from logHandler import log
from scriptHandler import script

from . import detector
from . import devanagariRepair
from . import glyphRefs
from . import legacyFonts
from . import neLexicon
from . import pdfText
from . import tesseractOcr
from . import visualScript
from . import diag

addonHandler.initTranslation()

CONF_SECTION = "nepaliReader"
CONF_SPEC = {
	"enabled": "boolean(default=True)",
	"pdfFile": "boolean(default=True)",
	"mode": "option('off', 'auto', 'always', default='auto')",
	"encoding": "option('preeti', 'kantipur', 'sagarmatha', 'himali', 'pcs', 'krutidev', default='preeti')",
	"autoDetectKruti": "boolean(default=True)",
	"useFontNames": "boolean(default=True)",
	"repairUnicode": "boolean(default=True)",
	"switchLanguage": "boolean(default=True)",
	"visualCheck": "boolean(default=True)",
	"webFontOnly": "boolean(default=True)",
	"lastOnMode": "option('auto', 'always', default='auto')",
	"tesseractPath": "string(default='')",
	"ocrLanguages": "string(default='nep+hin+eng')",
}
config.conf.spec[CONF_SECTION] = CONF_SPEC

MODES = ("off", "auto", "always")
MODE_LABELS = {
	# Translators: legacy font conversion mode
	"off": _("off"),
	# Translators: legacy font conversion mode
	"auto": _("automatic"),
	# Translators: legacy font conversion mode
	"always": _("always convert"),
}
ENCODING_LABELS = OrderedDict([
	("preeti", "Preeti"),
	("kantipur", "Kantipur"),
	("sagarmatha", "Sagarmatha"),
	("himali", "Fontasy Himali"),
	("pcs", "PCS Nepali"),
	("krutidev", "Kruti Dev (Hindi)"),
])

# Translators: input gestures category
CATEGORY = _("Nepali Reader")

CONTEXT_SECONDS = 300.0  # a window stays "known legacy" this long after confirmed legacy text
CHECK_INTERVAL = 0.2     # seconds between "is this a web page" lookups
VISUAL_SLOW = 0.05       # a screen check slower than this is switched off for that window class for a minute

# Web browsers and chat apps: text there is Unicode, so only convert when the page names a legacy font.
WEB_APPS = {
	"chrome", "msedge", "firefox", "brave", "opera", "vivaldi", "iexplore", "msedgewebview2",
	"whatsapp", "whatsapp.root", "discord", "telegram", "slack", "ms-teams", "teams", "messenger",
	"signal", "viber", "skype", "zoom",
}

PDF_APPS = {"acrord32", "acrobat", "foxitreader", "foxitpdfreader", "foxitphantompdf", "sumatrapdf", "pdfxedit", "nitropdf"}

# Unicode Devanagari fonts: text in these is real Unicode (or plain English), never legacy
UNICODE_DEVANAGARI_FONTS = (
	"mangal", "kalimati", "nirmala", "noto sans devanagari", "noto serif devanagari", "aparajita",
	"kokila", "utsaah", "sanskrit text", "arial unicode", "lohit", "mukta", "hind", "annapurna",
	"devanagari", "kanchan", "madan",
)

# characters that carry letters in Preeti / Kruti Dev (letters, digits and the symbol keys)
_LEGACY_TRIGGER = frozenset(
	"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789[]{};'\\/|`~\"<>?!@#$%^&*()_+=-"
)


def conf():
	return config.conf[CONF_SECTION]


_ON = [None]  # Nepali mode on/off, the same in every NVDA configuration profile


def isOn():
	if _ON[0] is None:
		try:
			base = config.conf.profiles[0].get(CONF_SECTION, {})
			v = base.get("enabled", True)
			_ON[0] = v not in (False, "False", "false", "0", 0)
		except Exception:
			_ON[0] = bool(conf()["enabled"])
	return _ON[0]


def setOn(value):
	_ON[0] = bool(value)
	try:
		conf()["enabled"] = bool(value)
	except Exception:
		pass
	try:
		prof = config.conf.profiles[0]
		if CONF_SECTION not in prof:
			prof[CONF_SECTION] = {}
		prof[CONF_SECTION]["enabled"] = bool(value)
	except Exception:
		pass


_menuSync = [lambda: None]  # set by the plugin so the settings panel can update the menu check mark


class _LRU(OrderedDict):
	def __init__(self, size=4000):
		super().__init__()
		self.size = size

	def get_(self, key):
		try:
			self.move_to_end(key)
			return self[key]
		except KeyError:
			return None

	def put(self, key, value):
		self[key] = value
		self.move_to_end(key)
		if len(self) > self.size:
			self.popitem(last=False)


class _DocState:
	"""Is this document's text layer damaged? Decided once per window from what is read:
	a fault mark that never occurs in correct text, or - over at least 40 words - a trial repair
	that turns 10% or more of the words from unknown into dictionary words."""

	def __init__(self):
		self.broken = False
		self.decided = False
		self.gain = 0
		self.words = 0
		self.known = 0
		self.seenWords = 0
		self.afterKnown = 0
		self.afterWords = 0
		self.warned = False
		self.unicodeWords = 0  # real Unicode Devanagari words seen in this window
		self.swaps = []        # this document's own letter swaps, learned from its whole text
		self.learning = False

	@property
	def isUnicodeDocument(self):
		"""A window showing real Unicode Nepali/Hindi: its English letters are English, not Preeti."""
		return self.unicodeWords >= 15

	def observe(self, text):
		if self.decided:
			return
		if devanagariRepair.isBroken(text):
			self.broken = self.decided = True
			return
		k, w = devanagariRepair.wordStats(text)
		self.known += k
		self.seenWords += w
		if self.seenWords >= 60 and self.known < 0.5 * self.seenWords:
			# most "words" are not words at all: a damaged text layer (real text: 75-90% are words)
			self.broken = self.decided = True
			return
		before, after, n = devanagariRepair.repairGain(text)
		self.gain += before - after
		self.words += n
		if (self.words >= 40 and self.gain >= 0.10 * self.words) or (before - after >= 2 and before - after >= 0.3 * n):
			# enough evidence over the document, or one line where repair clearly turns
			# several unknown words into real words
			self.broken = self.decided = True
		elif self.words >= 300:
			self.decided = True

	def afterRepair(self, fixed):
		"""If even the repaired text has few real words, suggest OCR once."""
		if self.warned:
			return
		k, n = devanagariRepair.wordStats(fixed)
		self.afterKnown += k
		self.afterWords += n
		if self.afterWords >= 80 and self.afterKnown < 0.6 * self.afterWords:
			self.warned = True
			# Translators: said once when a document's text cannot be repaired well
			wx.CallLater(800, ui.message, _(
				"The text in this document is damaged. For the most accurate reading, "
				"press NVDA+Alt+O to read the page with OCR."
			))


class _ConvertingTextInfo:
	"""Wraps a TextInfo for getTextInfoSpeech: same object, but getTextWithFields returns converted text."""

	def __init__(self, info, plugin):
		self.__dict__["_nrInfo"] = info
		self.__dict__["_nrPlugin"] = plugin

	def __getattr__(self, name):
		return getattr(self.__dict__["_nrInfo"], name)

	def __setattr__(self, name, value):
		setattr(self.__dict__["_nrInfo"], name, value)

	@property
	def text(self):
		if not isOn():
			return self.__dict__["_nrInfo"].text
		info = self.__dict__["_nrInfo"]
		raw = info.text
		if not raw or len(raw) > 5000:
			return raw
		return self.__dict__["_nrPlugin"]._plainText(info)

	def getTextWithFields(self, formatConfig=None):
		if not isOn():
			return self.__dict__["_nrInfo"].getTextWithFields(formatConfig)
		return self.__dict__["_nrPlugin"]._convertFields(self.__dict__["_nrInfo"], formatConfig)

	def copy(self):
		if not isOn():
			return self.__dict__["_nrInfo"].copy()
		return _ConvertingTextInfo(self.__dict__["_nrInfo"].copy(), self.__dict__["_nrPlugin"])

	def setEndPoint(self, other, which):
		return self.__dict__["_nrInfo"].setEndPoint(_unwrap(other), which)

	def compareEndPoints(self, other, which):
		return self.__dict__["_nrInfo"].compareEndPoints(_unwrap(other), which)

	def isOverlapping(self, other):
		return self.__dict__["_nrInfo"].isOverlapping(_unwrap(other))


class _PlainTextInfo:
	"""Wraps a TextInfo for speaking selections: .text gives the real (converted) text."""

	def __init__(self, info, plugin):
		self.__dict__["_nrInfo"] = info
		self.__dict__["_nrPlugin"] = plugin

	def __getattr__(self, name):
		return getattr(self.__dict__["_nrInfo"], name)

	def __setattr__(self, name, value):
		setattr(self.__dict__["_nrInfo"], name, value)

	@property
	def text(self):
		if not isOn():
			return self.__dict__["_nrInfo"].text
		info = self.__dict__["_nrInfo"]
		raw = info.text
		if not raw or len(raw) > 5000:
			return raw  # a very large selection is announced as it is (fast)
		return self.__dict__["_nrPlugin"]._plainText(info)

	def getTextWithFields(self, formatConfig=None):
		if not isOn():
			return self.__dict__["_nrInfo"].getTextWithFields(formatConfig)
		return self.__dict__["_nrPlugin"]._convertFields(self.__dict__["_nrInfo"], formatConfig)

	def copy(self):
		if not isOn():
			return self.__dict__["_nrInfo"].copy()
		return _PlainTextInfo(self.__dict__["_nrInfo"].copy(), self.__dict__["_nrPlugin"])

	def setEndPoint(self, other, which):
		return self.__dict__["_nrInfo"].setEndPoint(_unwrap(other), which)

	def compareEndPoints(self, other, which):
		return self.__dict__["_nrInfo"].compareEndPoints(_unwrap(other), which)

	def isOverlapping(self, other):
		return self.__dict__["_nrInfo"].isOverlapping(_unwrap(other))


def keyOf_(info):
	try:
		return pdfText.keyOf(info.text or "")
	except Exception:
		return ""


def _realObj(obj):
	"""In browse mode NVDA gives a tree interceptor (virtual buffer): use its document object."""
	return getattr(obj, "rootNVDAObject", None) or obj


def _appName(obj):
	try:
		return (_realObj(obj).appModule.appName or "").lower()
	except Exception:
		try:
			return (api.getForegroundObject().appModule.appName or "").lower()
		except Exception:
			return ""


def _unwrap(info):
	while isinstance(info, (_PlainTextInfo, _ConvertingTextInfo)):
		info = info.__dict__["_nrInfo"]
	return info


class _PdfState:
	"""The PDF file behind one viewer window, and its rebuilt text."""

	def __init__(self):
		self.status = "new"   # new, building, ready, none
		self.index = None
		self.location = None


class _Yield:
	"""Background work gives NVDA the processor often: after about 10 ms of work it rests 15 ms,
	so speech and keys stay quick while a PDF is being read."""

	def __init__(self, work=0.010, rest=0.015):
		self.work = work
		self.rest = rest
		self.last = time.perf_counter()

	def __call__(self):
		now = time.perf_counter()
		if now - self.last >= self.work:
			time.sleep(self.rest)
			self.last = time.perf_counter()


def _cacheDir():
	try:
		import globalVars
		base = globalVars.appArgs.configPath
	except Exception:
		base = os.path.expanduser("~")
	return os.path.join(base, "nepaliReader")


class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._cache = _LRU()
		self._contextWindow = None
		self._contextEncoding = None
		self._contextUntil = 0.0
		self._recognizerClass = None
		self._visCache = _LRU(600)
		self._visSlow = {}
		self._webCheckTime = 0.0
		self._webResult = False
		self._patched = []
		self._docs = _LRU(50)  # window -> _DocState (is this document's text layer damaged?)
		self._pdfs = _LRU(30)  # window -> _PdfState (the PDF file and its rebuilt text)
		self._ready = False
		threading.Thread(target=self._loadDictionary, name="NepaliReaderDict", daemon=True).start()
		diag.start(_cacheDir())
		self._patchTextInfoSpeech()
		try:
			self._patchCopyAndSelection()
		except Exception:
			log.error("Nepali Reader: could not hook copying", exc_info=True)
		NVDASettingsDialog.categoryClasses.append(NepaliReaderSettingsPanel)
		self._menu = None
		try:
			wx.CallAfter(self._createMenu)
		except Exception:
			log.debugWarning("Nepali Reader: could not add menu", exc_info=True)
		try:
			# after every add-on has loaded, give up any key another command already uses
			wx.CallAfter(self._avoidGestureClashes)
			wx.CallLater(3000, self._checkHooks)
		except Exception:
			log.debugWarning("Nepali Reader: gesture check failed", exc_info=True)

	def _checkHooks(self):
		try:
			import speech
			import speech.speech as sm
			from speech import sayAll
			diag.write("hooks: speech.speech=%s speech=%s sayAll=%s mode=%s enabled=%s" % (
				sm.getTextInfoSpeech is self._patchedGetTextInfoSpeech,
				getattr(speech, "getTextInfoSpeech", None) is self._patchedGetTextInfoSpeech,
				getattr(sayAll.SayAllHandler, "_getTextInfoSpeech", None) is self._patchedGetTextInfoSpeech,
				conf()["mode"], conf()["enabled"]))
		except Exception:
			diag.exception("hook check")

	def _avoidGestureClashes(self):
		"""Never take a key that NVDA itself, another add-on or the user has assigned.
		A clashing key is dropped from this add-on (the command stays in Input Gestures,
		where the user can give it a free key)."""
		import globalCommands
		import inputCore
		owners = [globalCommands.commands]
		owners += [p for p in globalPluginHandler.runningPlugins if p is not self]
		norm = getattr(inputCore, "normalizeGestureIdentifier", lambda g: g.lower())
		for ident in list(getattr(self, "_gestureMap", {}).keys()):
			key = norm(ident)
			taken = None
			for o in owners:
				gmap = getattr(o, "_gestureMap", None) or {}
				if key in gmap or ident in gmap:
					taken = type(o).__module__
					break
			if taken is None:
				try:
					for module, cls, scriptName in inputCore.manager.userGestureMap.getScriptsForGesture(key):
						if not (module or "").startswith("globalPlugins.nepaliReader"):
							taken = module
							break
				except Exception:
					pass
			if taken and key in ("kb:control+c", "kb:c+control"):
				# another add-on (clipspeak, Clipboard Enhancement...) copies: keep it, and fix the
				# copied text right after it
				self._chainCopy(key, ident)
			if taken:
				try:
					self.removeGestureBinding(ident)
				except Exception:
					self._gestureMap.pop(ident, None)
				log.info("Nepali Reader: %s is already used by %s, so it was left free" % (ident, taken))

	def _chainCopy(self, key, ident):
		plugin = self
		for o in globalPluginHandler.runningPlugins:
			if o is self:
				continue
			gmap = getattr(o, "_gestureMap", None) or {}
			name = gmap.get(key) or gmap.get(ident)
			if not name:
				continue
			attr = "script_" + (name if isinstance(name, str) else getattr(name, "__name__", "")[7:])
			orig = getattr(o, attr, None)
			if not callable(orig) or getattr(orig, "_nrChained", False):
				continue

			def chained(gesture, _orig=orig):
				res = _orig(gesture)
				if isOn():
					wx.CallLater(400, plugin._fixClipboard, None)
				return res

			chained._nrChained = True
			for k in ("__doc__", "category", "__name__", "resumeSayAllMode", "speakOnDemand", "canPropagate", "bypassInputHelp", "allowInSleepMode"):
				if hasattr(orig, k):
					try:
						setattr(chained, k, getattr(orig, k))
					except Exception:
						pass
			setattr(o, attr, chained)
			log.info("Nepali Reader: copying with %s now gives the real Nepali text" % type(o).__module__)

	def terminate(self):
		self._unpatch()
		self._removeMenu()
		try:
			NVDASettingsDialog.categoryClasses.remove(NepaliReaderSettingsPanel)
		except ValueError:
			pass
		super().terminate()

	# ------------------------------------------------------------------
	# NVDA menu > Tools > Nepali Reader
	# ------------------------------------------------------------------

	def _createMenu(self):
		import gui
		toolsMenu = gui.mainFrame.sysTrayIcon.toolsMenu
		menu = wx.Menu()
		# Translators: menu item that turns the add-on on or off
		self._onOffItem = menu.AppendCheckItem(wx.ID_ANY, _("&Nepali mode (NVDA+Ctrl+Shift+Space)"))
		self._onOffItem.Check(isOn())
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self._onMenuToggle, self._onOffItem)
		# Translators: menu item
		item = menu.Append(wx.ID_ANY, _("Convert selected text or clipboard (NVDA+Alt+U)"))
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, lambda e: wx.CallLater(300, self.script_convertSelection, None), item)
		# Translators: menu item
		item = menu.Append(wx.ID_ANY, _("&Settings..."))
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self._onMenuSettings, item)
		# Translators: name of the add-on's submenu in NVDA's Tools menu
		self._menu = toolsMenu.AppendSubMenu(menu, _("&Nepali Reader"))
		_menuSync[0] = self._syncMenu

	def _removeMenu(self):
		try:
			if self._menu is not None:
				import gui
				gui.mainFrame.sysTrayIcon.toolsMenu.Remove(self._menu)
				self._menu = None
		except Exception:
			pass

	def _syncMenu(self):
		try:
			self._onOffItem.Check(isOn())
		except Exception:
			pass

	def _toggleEnabled(self):
		c = conf()
		newVal = not isOn()
		setOn(newVal)
		if newVal and c["mode"] == "off":
			c["mode"] = c["lastOnMode"]
		self._cache.clear()
		self._clearContext()
		if not newVal:
			self._docs.clear()
			self._pdfs.clear()
			devanagariRepair.setDocumentSwaps([], None)
		self._syncMenu()
		return newVal

	def _onMenuToggle(self, evt):
		on = self._toggleEnabled()
		# Translators: announced when Nepali mode is switched on or off
		wx.CallLater(300, ui.message, _("Nepali mode on") if on else _("Nepali mode off"))

	def _onMenuSettings(self, evt):
		import gui
		wx.CallAfter(gui.mainFrame.popupSettingsDialog, NVDASettingsDialog, NepaliReaderSettingsPanel)

	def _loadDictionary(self):
		try:
			count = detector.loadDictionary()
			count += neLexicon.load()
			devanagariRepair.loadConfusions()
			glyphRefs.load(cacheDir=_cacheDir())
			self._ready = True
			self._cache.clear()
			log.debug("Nepali Reader: loaded %d English words" % count)
		except Exception:
			log.error("Nepali Reader: could not load English dictionary", exc_info=True)

	# ------------------------------------------------------------------
	# hooking document speech
	# ------------------------------------------------------------------

	def _patchTextInfoSpeech(self):
		import speech
		import speech.speech as speechModule
		orig = speechModule.getTextInfoSpeech
		plugin = self

		def getTextInfoSpeech(info, *args, **kwargs):
			c = conf()
			if not isOn():
				return orig(_unwrap(info), *args, **kwargs)
			if c["mode"] != "off" or c["repairUnicode"] or c["switchLanguage"]:
				info = _ConvertingTextInfo(_unwrap(info), plugin)
			return orig(info, *args, **kwargs)

		self._origGetTextInfoSpeech = orig
		self._patchedGetTextInfoSpeech = getTextInfoSpeech
		speechModule.getTextInfoSpeech = getTextInfoSpeech
		self._patched.append((speechModule, "getTextInfoSpeech"))
		if getattr(speech, "getTextInfoSpeech", None) is orig:
			speech.getTextInfoSpeech = getTextInfoSpeech
			self._patched.append((speech, "getTextInfoSpeech"))
		try:
			from speech import sayAll
			handler = sayAll.SayAllHandler
			if handler is not None and getattr(handler, "_getTextInfoSpeech", None) is orig:
				handler._getTextInfoSpeech = getTextInfoSpeech
				self._patched.append((handler, "_getTextInfoSpeech"))
		except Exception:
			log.debugWarning("Nepali Reader: could not hook say all", exc_info=True)

	def _unpatch(self):
		for owner, name in self._patched:
			try:
				if getattr(owner, name, None) is self._patchedGetTextInfoSpeech:
					setattr(owner, name, self._origGetTextInfoSpeech)
			except Exception:
				log.debugWarning("Nepali Reader: could not unhook %s" % name, exc_info=True)
		self._patched = []
		for owner, name, orig, new in getattr(self, "_patched2", []):
			try:
				if getattr(owner, name, None) is new:
					setattr(owner, name, orig)
			except Exception:
				pass
		self._patched2 = []

	def _patchCopyAndSelection(self):
		"""Copying (browse mode Ctrl+C, NVDA's review copy) and speaking a selection
		(Shift+arrows) use the real text too."""
		self._patched2 = []
		plugin = self
		origCopy = textInfos.TextInfo.copyToClipboard

		def copyToClipboard(info, notify=False):
			try:
				if isOn():
					text = plugin._plainText(info)
					if diag.wanted():
						try:
							diag.write("copy: %r -> %r" % ((_unwrap(info).text or "")[:60], (text or "")[:60]))
						except Exception:
							pass
					if text:
						return api.copyToClip(textInfos.convertToCrlf(text), notify)
			except Exception:
				log.debugWarning("Nepali Reader: copy failed", exc_info=True)
			return origCopy(_unwrap(info), notify)

		textInfos.TextInfo.copyToClipboard = copyToClipboard
		self._patched2.append((textInfos.TextInfo, "copyToClipboard", origCopy, copyToClipboard))
		try:
			import speech
			import speech.speech as speechModule
			origSel = speechModule.speakSelectionChange

			def speakSelectionChange(oldInfo, newInfo, *args, **kwargs):
				if isOn():
					try:
						oldInfo = _PlainTextInfo(_unwrap(oldInfo), plugin)
						newInfo = _PlainTextInfo(_unwrap(newInfo), plugin)
					except Exception:
						pass
				else:
					oldInfo = _unwrap(oldInfo)
					newInfo = _unwrap(newInfo)
				return origSel(oldInfo, newInfo, *args, **kwargs)

			speechModule.speakSelectionChange = speakSelectionChange
			self._patched2.append((speechModule, "speakSelectionChange", origSel, speakSelectionChange))
			if getattr(speech, "speakSelectionChange", None) is origSel:
				speech.speakSelectionChange = speakSelectionChange
				self._patched2.append((speech, "speakSelectionChange", origSel, speakSelectionChange))
		except Exception:
			log.debugWarning("Nepali Reader: could not hook selection speech", exc_info=True)

	def _plainText(self, info):
		"""The real text of a TextInfo (Preeti converted, PDF text rebuilt), as plain text."""
		info = _unwrap(info)
		if not isOn():
			return info.text
		try:
			fields = self._convertFields(info, None)
		except Exception:
			return info.text
		return "".join(f for f in fields if isinstance(f, str))

	# ------------------------------------------------------------------
	# the PDF file itself: rebuild its text from the glyphs
	# ------------------------------------------------------------------

	def _pdfIndex(self, obj):
		"""The rebuilt text of the PDF in the foreground window, once ready (else None)."""
		c = conf()
		if not c["pdfFile"] or not self._ready:
			return None
		key = self._foregroundKey()
		st = self._pdfs.get_(key)
		if st is None:
			st = _PdfState()
			self._pdfs.put(key, st)
			try:
				import pdfLocateShim  # noqa: F401  (tests)
			except ImportError:
				pass
			try:
				from . import pdfLocate
				fg = api.getForegroundObject()
				url = pdfLocate._urlFromObject(obj)
				title = (fg.name or "") if fg else ""
				pid = getattr(fg, "processID", None)
			except Exception:
				log.debugWarning("Nepali Reader: could not look at the PDF window", exc_info=True)
				diag.exception("could not look at the PDF window")
				st.status = "none"
				return None
			st.status = "building"
			threading.Thread(target=self._buildPdf, args=(st, url, title, pid), name="NepaliReaderPdf", daemon=True).start()
			return None
		return st.index if st.status == "ready" else None

	def _buildPdf(self, st, url, title, pid):
		from . import pdfLocate
		try:
			try:
				import comtypes
				comtypes.CoInitialize()
			except Exception:
				pass
			loc = pdfLocate._pathFromUrl(url)
			if not loc or not (loc.startswith("http") or os.path.isfile(loc)):
				loc = pdfLocate.findFromTitle(title, pid)
			diag.write("pdf: url=%r title=%r -> %r" % (url, title, loc))
			data = None
			if loc:
				st.location = loc
				data = pdfLocate.readPdf(loc)
			if not data:
				loc2 = pdfLocate.findFromTitle(title, pid)
				if loc2 and loc2 != loc:
					diag.write("pdf fallback from title: %r -> %r" % (title, loc2))
					st.location = loc2
					data = pdfLocate.readPdf(loc2)
			if not data:
				log.debug("Nepali Reader: PDF file not found or could not be read for %r" % title)
				st.status = "none"
				return
			digest = hashlib.md5(data).hexdigest()
			cdir = _cacheDir()
			cfile = os.path.join(cdir, "pdf_%s_%d.idx" % (digest, pdfText.INDEX_VERSION))
			idx = None
			if os.path.exists(cfile):
				try:
					with open(cfile, "rb") as f:
						idx = pdfText.DocIndex.restore(pickle.loads(zlib.decompress(f.read())))
				except Exception:
					idx = None
			if idx is None:
				t0 = time.monotonic()
				pause = _Yield()
				if len(data) > 400 * 1024:
					# a long document: the first pages first, so reading can start at once
					try:
						first = pdfText.DocIndex.build(data, detector=detector, pause=pause, isWord=neLexicon.isWord, maxPages=6)
						st.index = first
						st.status = "ready"
						self._cache.clear()
						diag.write("pdf: first pages ready in %.1f s" % (time.monotonic() - t0))
					except Exception:
						diag.exception("first pages")
				idx = pdfText.DocIndex.build(data, detector=detector, pause=pause, isWord=neLexicon.isWord)
				log.info("Nepali Reader: rebuilt %s in %.1f s: %r" % (loc, time.monotonic() - t0, idx.stats))
				diag.write("pdf: rebuilt in %.1f s: %r" % (time.monotonic() - t0, idx.stats))
				try:
					os.makedirs(cdir, exist_ok=True)
					old = sorted((os.path.getmtime(os.path.join(cdir, n)), n) for n in os.listdir(cdir) if n.startswith("pdf_"))
					for _t, n in old[:-60]:
						try:
							os.remove(os.path.join(cdir, n))
						except OSError:
							pass
					with open(cfile, "wb") as f:
						f.write(zlib.compress(pickle.dumps(idx.dump(), protocol=4), 6))
				except Exception:
					log.debugWarning("Nepali Reader: could not save the PDF index", exc_info=True)
			st.index = idx
			st.status = "ready"
			self._cache.clear()
		except Exception:
			log.debugWarning("Nepali Reader: could not rebuild the PDF text", exc_info=True)
			diag.exception("could not rebuild the PDF text")
			st.status = "none"

	def _indexText(self, info, idx, text):
		"""The real text for one run of what the viewer gave, or None if the index doesn't know it."""
		key = pdfText.keyOf(text)
		if not key:
			return None
		lines = text.splitlines(True)
		if len(lines) > 2:
			# several lines (a paragraph, a selection, select all): line by line, keeping the line breaks
			out = []
			found = False
			for ln in lines:
				body = ln.rstrip("\r\n")
				end = ln[len(body):]
				new = self._indexText(None, idx, body) if pdfText.keyOf(body) else None
				if new is not None:
					found = True
					out.append(new + end)
				else:
					out.append(ln)
			return "".join(out) if found else None
		pieces = None
		if info is not None and len(key) <= 100 and keyOf_(info) == key:
			# a character, word, or short line selection: find it through its line
			ctx = self._lineContext(info)
			if ctx:
				lineText, offset = ctx
				if pdfText.keyOf(lineText) != key:
					pieces = idx.spanAt(lineText, offset, len(info.text or text))
		if pieces is None:
			pieces = idx.lookup(text)
		if not pieces or not any(ok for _p, ok in pieces):
			return None
		out = []
		for piece, ok in pieces:
			if not piece:
				continue
			if not ok:
				if devanagariRepair.hasDevanagari(piece):
					piece = devanagariRepair.repair(piece, broken=True)
				elif any(c.isascii() and c.isalpha() for c in piece) and not detector.isEnglishWord(detector._core(piece)):
					cand = legacyFonts.convert(piece, "preeti")
					if cand and (devanagariRepair.hasDevanagari(cand) and (neLexicon.isWord(cand.strip(".,:;!?()")) or detector.wordScore(piece, "preeti") >= 3.0)):
						piece = cand
			out.append(piece)
		lead = text[: len(text) - len(text.lstrip())]
		trail = text[len(text.rstrip()):]
		return lead + " ".join(out) + trail

	def _legacyAkshar(self, info, text, enc):
		"""The syllable a Preeti / Kruti Dev character belongs to, from the word around it."""
		ctx = self._lineContext(info)
		if not ctx:
			return None
		line, off = ctx
		if off >= len(line):
			return None
		ws = max(line.rfind(" ", 0, off), line.rfind("\t", 0, off)) + 1
		we = len(line)
		for sep in (" ", "\t", "\r", "\n"):
			k = line.find(sep, off)
			if k >= 0:
				we = min(we, k)
		word = line[ws:we]
		if not word or word == text.strip() or len(word) > 40:
			return None
		conv = legacyFonts.convert(word, enc) or ""
		aks = pdfText.aksharas(conv)
		if not aks:
			return None
		end = off - ws + len(text)
		if text.strip() == ("f" if enc == "krutidev" else "l"):
			end += 1  # the short i is typed before its consonant: it belongs to the next syllable
		upto = legacyFonts.convert(word[:end], enc) or ""
		k = min(max(len(pdfText.aksharas(upto)) - 1, 0), len(aks) - 1)
		return aks[k]

	@staticmethod
	def _lineContext(info):
		"""(text of the line holding info, offset of info in it) or None."""
		try:
			rawInfo = _unwrap(info)
			line = rawInfo.copy()
			line.expand(textInfos.UNIT_LINE)
			pre = line.copy()
			pre.setEndPoint(rawInfo, "endToStart")
			return line.text, len(pre.text)
		except Exception:
			return None

	# ------------------------------------------------------------------
	# context
	# ------------------------------------------------------------------

	def _foregroundKey(self):
		try:
			fg = api.getForegroundObject()
			if not fg:
				return None
			title = (fg.name or "").strip()
			return (fg.windowHandle, title)
		except Exception:
			return None

	def _inContext(self):
		if self._contextEncoding is None or time.monotonic() > self._contextUntil:
			return None
		if self._foregroundKey() != self._contextWindow:
			return None
		return self._contextEncoding

	def _setContext(self, encoding):
		self._contextWindow = self._foregroundKey()
		self._contextEncoding = encoding
		self._contextUntil = time.monotonic() + CONTEXT_SECONDS

	def _clearContext(self):
		self._contextEncoding = None

	def _isPdfWindow(self, obj):
		"""Same answer for the same window for half a second (it is asked several times per line)."""
		now = time.monotonic()
		memo = getattr(self, "_pdfMemo", None)
		try:
			hwnd = api.getForegroundObject().windowHandle
		except Exception:
			hwnd = None
		if memo and memo[0] == hwnd and now - memo[1] < 0.5:
			return memo[2]
		res = self._isPdfWindowUncached(obj)
		self._pdfMemo = (hwnd, now, res)
		return res

	def _isPdfWindowUncached(self, obj):
		"""A PDF viewer, or a browser showing a PDF: fonts are usually not reported here."""
		try:
			app = _appName(obj)
			if app in PDF_APPS:
				return True
			fg = api.getForegroundObject()
			rawTitle = (fg.name if fg else "") or ""
			title = rawTitle.lower()
			if ".pdf" in title:
				return True
			if app not in WEB_APPS:
				return False
			# a browser tab whose title is the PDF's own title: look at the document address
			key = (fg.windowHandle if fg else None, title)
			if not hasattr(self, "_pdfTabs"):
				self._pdfTabs = _LRU(100)
			cached = self._pdfTabs.get_(key)
			if cached is None:
				from . import pdfLocate
				url = (pdfLocate._urlFromObject(obj) or "").lower()
				cached = pdfLocate._isPdfUrl(url)
				if not cached:
					cached = self._isPdfViewerObj(obj)
				if not cached:
					cached = bool(pdfLocate.findFromTitle(rawTitle, getattr(fg, "processID", None)))
				self._pdfTabs.put(key, cached)
			return cached
		except Exception:
			return False

	@staticmethod
	def _isPdfViewerObj(obj):
		"""Detects if an object is inside Chrome/Edge PDF viewer from UI cues."""
		try:
			o = getattr(obj, "rootNVDAObject", None) or obj
			seen = 0
			while o is not None and seen < 15:
				seen += 1
				name = (getattr(o, "name", None) or "").lower()
				val = (getattr(o, "value", None) or "").lower()
				if any(marker in name or marker in val for marker in (
					"pdf is inaccessible", "add text annotations", "save to google drive",
					"application/pdf", "finished loading pdf"
				)):
					return True
				try:
					ia = getattr(o, "IAccessibleObject", None)
					if ia:
						accName = (ia.accName(getattr(o, "IAccessibleChildID", 0)) or "").lower()
						if any(marker in accName for marker in ("pdf is inaccessible", "add text annotations", "finished loading pdf")):
							return True
				except Exception:
					pass
				o = getattr(o, "parent", None)
		except Exception:
			pass
		return False

	def _isWebNonPdf(self, obj):
		"""True in a browser or chat app showing a normal page (not a PDF)."""
		try:
			app = _appName(obj)
			if app in WEB_APPS:
				return not self._isPdfWindow(obj)
		except Exception:
			pass
		return False

	# ------------------------------------------------------------------
	# screen check
	# ------------------------------------------------------------------

	@staticmethod
	def _grab(left, top, width, height):
		width = min(width, 2400)
		height = min(height, 160)
		import screenBitmap
		pixels = screenBitmap.ScreenBitmap(width, height).captureImage(left, top, width, height)
		raw = ctypes.string_at(ctypes.addressof(pixels), width * height * 4)
		verdict = visualScript.classifyBgra(raw, width, height)
		if verdict is None:
			# GDI capture is black while Screen Curtain is on; newer NVDA can capture through it
			try:
				from contentRecog import RecogImageInfo, recogUi
				if getattr(recogUi, "_isScreenCurtainActive", lambda: False)():
					pixels = recogUi._captureImage(RecogImageInfo(left, top, width, height, 1))
					raw = ctypes.string_at(ctypes.addressof(pixels), width * height * 4)
					verdict = visualScript.classifyBgra(raw, width, height)
			except Exception:
				pass
		return verdict

	def _visualVerdict(self, info, text):
		"""Pixels of exactly the text being spoken: DEVANAGARI / LATIN / None."""
		if len(text.strip()) < 2:
			return None
		key = (self._foregroundKey(), text)
		cached = self._visCache.get_(key)
		if cached is not None:
			return cached or None
		now = time.monotonic()
		wcls = ""
		try:
			wcls = getattr(_realObj(info.obj), "windowClassName", "")
			if self._visSlow.get(wcls, 0) > now:
				return None
			start = time.perf_counter()
			verdicts = []
			for r in list(info.boundingRects)[:6]:
				if r.width > 4 and r.height > 4:
					v = self._grab(r.left, r.top, r.width, r.height)
					if v:
						verdicts.append(v)
			if time.perf_counter() - start > VISUAL_SLOW:
				self._visSlow[wcls] = now + 60
		except Exception:
			log.debugWarning("Nepali Reader: screen check failed", exc_info=True)
			self._visSlow[wcls] = now + 60
			return None
		verdict = None
		if verdicts:
			deva = verdicts.count(visualScript.DEVANAGARI)
			verdict = visualScript.DEVANAGARI if (deva * 2 >= len(verdicts) and deva) else (visualScript.LATIN if visualScript.LATIN in verdicts else None)
		self._visCache.put(key, verdict or "")
		return verdict

	# ------------------------------------------------------------------
	# conversion of one TextInfo's fields
	# ------------------------------------------------------------------

	def _convertFields(self, info, formatConfig):
		c = conf()
		if not isOn():
			return info.getTextWithFields(formatConfig)
		if diag.wanted():
			fields = self._convertFieldsInner(info, formatConfig, c)
			try:
				before = info.text
			except Exception:
				before = "?"
			after = "".join(f for f in fields if isinstance(f, str))
			st = self._pdfs.get_(self._foregroundKey())
			diag.write("read app=%s pdf=%s pdfState=%s mode=%s ready=%s | %r -> %r" % (
				_appName(info.obj), self._isPdfWindow(info.obj), st.status if st else None,
				c["mode"], self._ready, (before or "")[:70], after[:70]))
			return fields
		return self._convertFieldsInner(info, formatConfig, c)

	def _convertFieldsInner(self, info, formatConfig, c):
		wantFont = c["useFontNames"] and c["mode"] != "off"
		fc = formatConfig
		if wantFont:
			fc = dict(formatConfig or config.conf["documentFormatting"])
			fc["reportFontName"] = True
		fields = info.getTextWithFields(fc)
		try:
			return self._convertFieldList(info, fields, c)
		except Exception:
			log.error("Nepali Reader: conversion failed", exc_info=True)
			diag.exception("conversion failed")
			return fields

	@staticmethod
	def _mergeRuns(fields):
		"""Word and other apps cut a line into pieces at spelling-error marks, bookmarks and similar
		format changes. A Preeti/Devanagari word cut in the middle cannot be converted, so the pieces
		of one line that share the same font are joined into the first piece."""
		out = list(fields)
		groups = []
		cur = None
		key = (None, None)
		lastWasText = False
		for i, item in enumerate(out):
			if isinstance(item, str):
				if not item:
					continue
				if cur is not None and cur[0] == key and lastWasText:
					cur[1].append(i)
				else:
					cur = (key, [i])
					groups.append(cur)
				lastWasText = True
			elif isinstance(item, textInfos.FieldCommand) and item.command == "formatChange":
				name = item.field.get("font-name") if item.field else None
				newKey = ((name or "").split(",")[0].strip().lower() or None, legacyFonts.encodingForFontName(name) if name else None)
				if newKey != key:
					key = newKey
					lastWasText = False
				# same font: spelling-error and similar marks do not break the line
			else:
				lastWasText = False
				cur = None
		for _key, idx in groups:
			if len(idx) > 1:
				out[idx[0]] = "".join(out[k] for k in idx)
				for k in idx[1:]:
					out[k] = ""
		return out

	def _learnDocument(self, obj, st):
		"""Read the damaged document's whole text once and learn its letter swaps in the background."""
		if not self._isPdfWindow(obj):
			return
		try:
			ti = getattr(obj, "treeInterceptor", None)
			src = ti if ti is not None else obj
			text = src.makeTextInfo(textInfos.POSITION_ALL).text or ""
		except Exception:
			log.debugWarning("Nepali Reader: could not read the whole document", exc_info=True)
			return
		text = text[:300000]

		def work():
			try:
				st.swaps = devanagariRepair.learnDocumentSwaps(text)
				log.debug("Nepali Reader: learned %d swaps for this document" % len(st.swaps))
				if st.swaps:
					# Translators: said once when the add-on has worked out a damaged document's pattern
					wx.CallAfter(ui.message, _("Nepali Reader: learned this document's letter pattern"))
			except Exception:
				log.error("Nepali Reader: learning failed", exc_info=True)

		threading.Thread(target=work, name="NepaliReaderLearn", daemon=True).start()

	def _docState(self):
		key = self._foregroundKey()
		st = self._docs.get_(key)
		if st is None:
			st = _DocState()
			self._docs.put(key, st)
		return st

	def _isBrokenDoc(self):
		st = self._docs.get_(self._foregroundKey())
		return bool(st and st.broken)

	def _convertFieldList(self, info, fields, c):
		mode = c["mode"]
		repair = c["repairUnicode"]
		fields = self._mergeRuns(fields)
		# 1. find each text run and the font that applies to it
		runs = []  # (index, text, fontKnown, encoding)
		fontKnown = False
		curEnc = None
		unicodeFont = False
		for i, item in enumerate(fields):
			if isinstance(item, str):
				if item:
					runs.append((i, item, "unicode" if unicodeFont else fontKnown, curEnc))
			elif isinstance(item, textInfos.FieldCommand) and item.command == "formatChange":
				name = item.field.get("font-name") if item.field else None
				fontKnown = bool(name)
				curEnc = legacyFonts.encodingForFontName(name) if name else None
				lower = (name or "").lower()
				unicodeFont = bool(name) and any(f in lower for f in UNICODE_DEVANAGARI_FONTS)
		if not runs:
			return fields
		out = list(fields)
		changed = False
		rebuilt = {}  # index -> True when the text came from the PDF file itself
		if self._isPdfWindow(info.obj):
			idx = self._pdfIndex(info.obj)
			if idx is not None:
				# text pieces that belong together: a line cut by format changes is joined, but
				# never across headings, links, list items or other controls (joining those put
				# one heading's text into another and left the other empty)
				groups = []
				cur = []
				runAt = {r[0]: r for r in runs}
				for i, item in enumerate(fields):
					if i in runAt:
						cur.append(runAt[i])
					elif isinstance(item, textInfos.FieldCommand) and item.command == "formatChange":
						continue
					elif isinstance(item, str):
						continue
					else:
						if cur:
							groups.append(cur)
						cur = []
				if cur:
					groups.append(cur)
				for grp in groups:
					whole = "".join(t for _i, t, _k, _e in grp)
					try:
						new = self._indexText(info if len(groups) == 1 else None, idx, whole)
					except Exception:
						log.debugWarning("Nepali Reader: PDF text lookup failed", exc_info=True)
						new = None
					if new is None:
						continue
					first = grp[0][0]
					rebuilt[first] = bool(new and (devanagariRepair.hasDevanagari(new) or new != whole))
					if new != whole:
						out[first] = new
						for i, _t, _k, _e in grp[1:]:
							out[i] = ""
						changed = True
					for i, _t, _k, _e in grp[1:]:
						rebuilt[i] = False
				runs = [r for r in runs if r[0] not in rebuilt]
				if rebuilt and not runs:
					return self._withLanguage(out, rebuilt, c)
		if repair and self._isPdfWindow(info.obj) and not self._isWebNonPdf(info.obj):
			# only PDF text layers are damaged; Unicode Nepali on web pages and in documents is
			# correct and must never be "repaired" (it turned भनसुन into निसान on news sites)
			st = self._docState()
			devanagariRepair.setDocumentSwaps(st.swaps, (id(st), len(st.swaps)))
			for k, (i, text, known, enc) in enumerate(runs):
				if enc is None and devanagariRepair.hasDevanagari(text):
					st.unicodeWords += sum(1 for w in text.split() if devanagariRepair.hasDevanagari(w))
					st.observe(text)
					fixed = devanagariRepair.repair(text, broken=True if st.broken else None)
					if st.broken:
						st.afterRepair(fixed)
						pst = self._pdfs.get_(self._foregroundKey())
						if not st.learning and (pst is None or pst.status == "none"):
							st.learning = True
							wx.CallAfter(self._learnDocument, info.obj, st)
					if fixed != text:
						out[i] = fixed
						runs[k] = (i, fixed, known, enc)
						changed = True
		if mode == "off":
			if rebuilt or (c["switchLanguage"] and any(devanagariRepair.hasDevanagari(x) for x in out if isinstance(x, str))):
				return self._withLanguage(out, rebuilt, c)
			return out if changed else fields
		# 2. decide which runs are legacy text and with which encoding
		convert = {}  # index -> (encoding, protectEnglish)
		unknown = []
		anyKnownFont = False
		inPdf = self._isPdfWindow(info.obj)
		ctxEnc = self._inContext()
		for i, text, known, enc in runs:
			if not any(ch in _LEGACY_TRIGGER for ch in text):
				continue
			if enc:
				convert[i] = (enc, False)  # the font says so
			elif mode == "always":
				convert[i] = (self._inContext() or c["encoding"], False)
			elif known == "unicode":
				continue  # Mangal, Kalimati, Nirmala...: real Unicode text
			elif devanagariRepair.hasDevanagari(text):
				if any(ch.isascii() and ch.isalpha() for ch in text):
					anyKnownFont = anyKnownFont or bool(known)
					unknown.append((i, text))
				continue
			elif not any(ch.isascii() and ch.isalpha() for ch in text):
				# numbers/symbols: if in confirmed legacy context, convert!
				if ctxEnc and any(ch in "!@#$%^&*()+=~`_{}[]\\|/<>?" for ch in text):
					useEnc = ctxEnc
					conv = legacyFonts.convert(text, useEnc)
					if conv and conv != text:
						convert[i] = (useEnc, False)
				continue
			else:
				# no font, or an ordinary font (Calibri, Arial...): Preeti text is often left in
				# the wrong font, so the text itself is checked
				anyKnownFont = anyKnownFont or bool(known)
				unknown.append((i, text))
		if unknown:
			isUniDoc = self._docState().isUnicodeDocument
			isWeb = self._isWebNonPdf(info.obj)
			if not (c["webFontOnly"] and isWeb):
				self._decideUnknown(info, unknown, convert, c, allowVisual=not anyKnownFont, isUnicodeDoc=isUniDoc)
			else:
				# Web non-PDF: convert only if strongly legacy
				self._decideUnknown(info, unknown, convert, c, allowVisual=False, isUnicodeDoc=True)
		if not convert:
			if rebuilt or (c["switchLanguage"] and any(devanagariRepair.hasDevanagari(x) for x in out if isinstance(x, str))):
				return self._withLanguage(out, rebuilt, c)
			return out if changed else fields
		# 3. convert, marking the language so the voice can switch
		result = []
		lastFormat = None
		switchLang = c["switchLanguage"]
		usedEnc = None
		count = 0
		for i, item in enumerate(out):
			if isinstance(item, textInfos.FieldCommand) and item.command == "formatChange":
				lastFormat = item.field
				result.append(item)
				continue
			if i in convert and isinstance(item, str):
				enc, protect = convert[i][0], convert[i][1]
				if len(convert[i]) > 2:
					newText = detector.convertTokens(convert[i][2], lambda t: legacyFonts.convert(t, enc) or t)
				else:
					newText = self._convertRun(item, enc, protect)
				if newText != item and 0 < len(item.strip()) <= 3 and " " not in item.strip():
					# moving by character: say the whole syllable (कि, र्मा), not half of it
					ak = self._legacyAkshar(info, item, enc)
					if ak:
						newText = ak
				if newText != item:
					count += len(newText.split())
					usedEnc = enc
					if switchLang:
						result.append(self._formatWithLanguage(lastFormat, legacyFonts.languageForEncoding(enc)))
						result.append(newText)
						result.append(self._formatWithLanguage(lastFormat, None, restore=True))
					else:
						result.append(newText)
					continue
			if switchLang and isinstance(item, str) and (rebuilt.get(i) or devanagariRepair.hasDevanagari(item)):
				curLang = (lastFormat.get("language") or "").lower() if lastFormat else ""
				if not curLang.startswith(("ne", "hi")):
					result.append(self._formatWithLanguage(lastFormat, "ne"))
					result.append(item)
					result.append(self._formatWithLanguage(lastFormat, None, restore=True))
					continue
			result.append(item)
		if usedEnc and c["mode"] == "auto" and count >= 2:
			self._setContext(usedEnc)
		return result

	def _withLanguage(self, out, rebuilt, c):
		"""Mark text containing Devanagari (including rebuilt PDF text) as Nepali so synthesizers speak text and numbers."""
		if not c["switchLanguage"]:
			return out
		result = []
		lastFormat = None
		for i, item in enumerate(out):
			if isinstance(item, textInfos.FieldCommand) and item.command == "formatChange":
				lastFormat = item.field
				result.append(item)
				continue
			if isinstance(item, str) and (rebuilt.get(i) or devanagariRepair.hasDevanagari(item)):
				curLang = (lastFormat.get("language") or "").lower() if lastFormat else ""
				if not curLang.startswith(("ne", "hi")):
					result.append(self._formatWithLanguage(lastFormat, "ne"))
					result.append(item)
					result.append(self._formatWithLanguage(lastFormat, None, restore=True))
					continue
			result.append(item)
		return result

	@staticmethod
	def _formatWithLanguage(baseField, language, restore=False):
		field = textInfos.FormatField()
		if baseField:
			field.update(baseField)
		if not restore:
			field["language"] = language
		return textInfos.FieldCommand("formatChange", field)

	def _convertRun(self, text, encoding, protectEnglish):
		key = ("run", text, encoding, protectEnglish)
		cached = self._cache.get_(key)
		if cached is not None:
			return cached
		lead = text[: len(text) - len(text.lstrip())]
		trail = text[len(text.rstrip()):]
		core = text.strip()
		if not core:
			return text
		decisions = detector.forceDecide(core, protectEnglish=protectEnglish)
		newText = lead + detector.convertTokens(decisions, lambda s: legacyFonts.convert(s, encoding) or s) + trail
		self._cache.put(key, newText)
		return newText

	def _decideUnknown(self, info, unknown, convert, c, allowVisual=True, isUnicodeDoc=False):
		"""Runs with no font information (most PDFs): detector, window context and the screen check."""
		joined = detector.cleanGluedTokens("".join(t for _, t in unknown))
		# window memory ("this document is Preeti") only for text without font information;
		# text in an ordinary font (Calibri...) is judged on its own words
		ctxEnc = self._inContext() if allowVisual else None
		encoding = ctxEnc or c["encoding"]
		used, decisions = self._detect(joined, encoding, bool(ctxEnc), c["autoDetectKruti"])
		legacyWords = sum(1 for t, f in decisions if f and not t.isspace())
		words = len(joined.split())
		verdict = None
		allEnglish = all(detector.isEnglishWord(detector._core(w)) for w in joined.split() if detector._core(w))
		if allEnglish:
			return
		if isUnicodeDoc and (legacyWords < 2 and legacyWords * 2 < words):
			hasStrong = any(f and (detector.wordScore(t, used) >= detector.MIXED_WORD or detector._strongAlone(t, detector.wordScore(t, used), used)) for t, f in decisions if not t.isspace())
			if not hasStrong:
				return
		inPdf = self._isPdfWindow(info.obj)
		if allowVisual and c["visualCheck"] and not allEnglish and (legacyWords or (ctxEnc and words <= 3) or inPdf):
			if legacyWords < 2 and not (legacyWords * 2 >= words and legacyWords >= 1):
				verdict = self._visualVerdict(info, joined)
		if verdict == visualScript.LATIN:
			return
		if verdict == visualScript.DEVANAGARI and self._mostlyLowerOrSymbols(joined):
			if not legacyWords:
				used = self._guessEncoding(joined, encoding, c["autoDetectKruti"])
			for i, _t in unknown:
				convert[i] = (used, False)
			return
		if ctxEnc and words == 1 and not detector.isEnglishWord(joined.strip().strip(".,:;")):
			# a single word / letter inside a document already confirmed as legacy (arrowing by character)
			for i, _t in unknown:
				convert[i] = (used, False)
			return
		if not legacyWords:
			return
		hasDeva = any("\u0900" <= c <= "\u097f" for c in joined)
		lineIsLegacy = not hasDeva and (legacyWords * 2 >= words or legacyWords >= 2)
		for i, text in unknown:
			if lineIsLegacy:
				# a Preeti line: convert its words, but keep words that clearly read as English
				part = detector.decide(text, used, context=True)
				if any(f for _, f in part):
					convert[i] = (used, True, part)
			else:
				# mixed line: convert only the words the detector picked
				part = detector.decide(text, used, context=False)
				if any(f for _, f in part):
					convert[i] = (used, True, part)

	@staticmethod
	def _mostlyLowerOrSymbols(text):
		letters = [ch for ch in text if ch.isascii() and ch.isalpha()]
		if not letters:
			return True
		return sum(1 for ch in letters if ch.isupper()) < 0.5 * len(letters)

	@staticmethod
	def _guessEncoding(text, default, autoKruti):
		if not autoKruti:
			return default
		words = text.split()
		other = "krutidev" if default != "krutidev" else "preeti"
		a = sum(detector.wordScore(w, default) for w in words)
		b = sum(detector.wordScore(w, other) for w in words)
		return other if b > a + 6 else default

	def _detect(self, text, encoding, inContext, autoKruti):
		key = ("det", text, encoding, inContext, autoKruti)
		cached = self._cache.get_(key)
		if cached is not None:
			return cached
		decisions = detector.decide(text, encoding, context=inContext)
		used = encoding
		if autoKruti and not any(f for _, f in decisions):
			other = "krutidev" if encoding != "krutidev" else "preeti"
			alt = detector.decide(text, other, context=False)
			if any(f for _, f in alt):
				decisions, used = alt, other
		result = (used, decisions)
		self._cache.put(key, result)
		return result


	# ------------------------------------------------------------------
	# scripts
	# ------------------------------------------------------------------

	@script(
		# Translators: input help for a command
		description=_("Turns Nepali mode on or off (reading Preeti, Kruti Dev and damaged Nepali PDFs correctly)"),
		category=CATEGORY,
		gesture="kb:NVDA+control+shift+space",
	)
	def script_toggleNepaliMode(self, gesture):
		on = self._toggleEnabled()
		tones.beep(880 if on else 330, 50)
		# Translators: announced when Nepali mode is switched on or off
		ui.message(_("Nepali mode on") if on else _("Nepali mode off"))

	@script(
		# Translators: input help for a command
		description=_("Copies the selection; in Nepali mode the copied text is the correct Unicode Nepali"),
		category=CATEGORY,
		gesture="kb:control+c",
	)
	def script_copyFixed(self, gesture):
		if not isOn():
			gesture.send()
			return
		try:
			focus = api.getFocusObject()
			ti = getattr(focus, "treeInterceptor", None)
			if ti is not None and not getattr(ti, "passThrough", True) and hasattr(ti, "script_copyToClipboard"):
				ti.script_copyToClipboard(gesture)  # browse mode: NVDA copies, through our copy hook
				return
		except Exception:
			log.debugWarning("Nepali Reader: copy", exc_info=True)
			focus = None
		gesture.send()
		if focus is not None:
			wx.CallLater(300, self._fixClipboard, focus)

	def _fixClipboard(self, focus):
		"""After the application copied a selection of Preeti / damaged text, put the real text on
		the clipboard instead (only when the clipboard holds exactly that selection)."""
		try:
			if focus is None:
				focus = api.getFocusObject()
			src = focus
			ti = getattr(focus, "treeInterceptor", None)
			if ti is not None and not getattr(ti, "passThrough", True):
				src = ti  # browse mode: the selection is in the virtual document
			info = src.makeTextInfo(textInfos.POSITION_SELECTION)
			if info.isCollapsed:
				return
			raw = info.text or ""
			new = self._plainText(info)
			if not new or new == raw:
				return
			clip = api.getClipData() or ""
			same = "".join(clip.split()) == "".join(raw.split())
			diag.write("copy after app: same=%s %r -> %r" % (same, raw[:50], new[:50]))
			if same:
				api.copyToClip(textInfos.convertToCrlf(new))
		except Exception:
			log.debugWarning("Nepali Reader: could not fix the copied text", exc_info=True)

	@script(
		# Translators: input help for a command
		description=_("Cycles legacy Nepali/Hindi font reading between automatic, always convert and off"),
		category=CATEGORY,
		gesture="kb:NVDA+alt+p",
	)
	def script_cycleMode(self, gesture):
		c = conf()
		mode = MODES[(MODES.index(c["mode"]) + 1) % len(MODES)]
		c["mode"] = mode
		if mode != "off":
			c["lastOnMode"] = mode
		self._syncMenu()
		self._cache.clear()
		self._clearContext()
		tones.beep({"off": 330, "auto": 660, "always": 880}[mode], 60)
		# Translators: announced when the conversion mode changes
		ui.message(_("Legacy fonts: {mode}").format(mode=MODE_LABELS[mode]))

	@script(
		# Translators: input help for a command
		description=_("Cycles the default legacy font: Preeti, Kantipur, Sagarmatha, Himali, PCS Nepali, Kruti Dev"),
		category=CATEGORY,
		gesture="kb:NVDA+alt+shift+p",
	)
	def script_cycleEncoding(self, gesture):
		c = conf()
		keys = list(ENCODING_LABELS)
		enc = keys[(keys.index(c["encoding"]) + 1) % len(keys)]
		c["encoding"] = enc
		self._cache.clear()
		self._clearContext()
		ui.message(ENCODING_LABELS[enc])

	@script(
		# Translators: input help for a command
		description=_(
			"Converts the selected text (or the clipboard if nothing is selected) from Preeti or Kruti Dev "
			"to Unicode, copies the result to the clipboard and reads it"
		),
		category=CATEGORY,
		gesture="kb:NVDA+alt+u",
	)
	def script_convertSelection(self, gesture):
		text = ""
		try:
			obj = api.getFocusObject()
			ti = getattr(obj, "treeInterceptor", None)
			if ti and not getattr(ti, "passThrough", True):
				obj = ti
			info = obj.makeTextInfo(textInfos.POSITION_SELECTION)
			if not info.isCollapsed:
				text = info.text
		except Exception:
			pass
		if not text:
			try:
				text = api.getClipData()
			except Exception:
				text = ""
		if not text or text.isspace():
			# Translators: reported when there is nothing to convert
			ui.message(_("No selection or clipboard text to convert"))
			return
		c = conf()
		encoding = self._inContext() or c["encoding"]
		result = devanagariRepair.repair(text, broken=True if self._isBrokenDoc() else None)
		decisions = detector.decide(result, encoding, context=True)
		if any(f for _, f in decisions):
			result = detector.convertTokens(decisions, lambda s: legacyFonts.convert(s, encoding) or s)
		elif any(ch.isascii() and ch.isalpha() for ch in result):
			# the user explicitly asked: convert everything except URLs and NVDA words
			result = detector.convertTokens(detector.forceDecide(result), lambda s: legacyFonts.convert(s, encoding) or s)
		api.copyToClip(result)
		ui.message(result)

	@script(
		# Translators: input help for a command
		description=_("Recognizes the navigator object (for example a PDF page) with offline Nepali, Hindi and English OCR"),
		category=CATEGORY,
		gesture="kb:NVDA+alt+o",
	)
	def script_ocr(self, gesture):
		exe = tesseractOcr.findTesseract(conf()["tesseractPath"])
		if not exe:
			# Translators: reported when the OCR engine is missing
			ui.message(_(
				"Tesseract OCR engine not found. Install Tesseract for Windows, "
				"or set its path in NVDA settings, Nepali Reader."
			))
			return
		try:
			from contentRecog import recogUi
			if self._recognizerClass is None:
				self._recognizerClass = tesseractOcr.makeRecognizerClass()
			recogUi.recognizeNavigatorObject(self._recognizerClass(exe, conf()["ocrLanguages"] or "nep+hin+eng"))
		except Exception:
			log.error("Nepali Reader: OCR failed to start", exc_info=True)
			# Translators: reported when OCR fails
			ui.message(_("OCR failed"))


class NepaliReaderSettingsPanel(SettingsPanel):
	# Translators: title of the settings panel
	title = _("Nepali Reader")

	def makeSettings(self, settingsSizer):
		c = conf()
		helper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		# Translators: settings label
		self.enabledCheck = helper.addItem(wx.CheckBox(self, label=_("Nepali mode (NVDA+Ctrl+Shift+Space)")))
		self.enabledCheck.SetValue(isOn())
		# Translators: settings label
		self.pdfCheck = helper.addItem(wx.CheckBox(self, label=_("For PDFs, read the PDF file itself to get the exact Nepali text")))
		self.pdfCheck.SetValue(c["pdfFile"])
		# Translators: settings label
		self.modeChoice = helper.addLabeledControl(_("Legacy font reading:"), wx.Choice, choices=[MODE_LABELS[m] for m in MODES])
		self.modeChoice.SetSelection(MODES.index(c["mode"]))
		# Translators: settings label
		self.encChoice = helper.addLabeledControl(_("Default legacy font:"), wx.Choice, choices=list(ENCODING_LABELS.values()))
		self.encChoice.SetSelection(list(ENCODING_LABELS).index(c["encoding"]))
		# Translators: settings label
		self.krutiCheck = helper.addItem(wx.CheckBox(self, label=_("Also detect Hindi Kruti Dev text automatically")))
		self.krutiCheck.SetValue(c["autoDetectKruti"])
		# Translators: settings label
		self.fontCheck = helper.addItem(wx.CheckBox(self, label=_("Use font names (Preeti, Kantipur, Kruti Dev...) when the application reports them")))
		self.fontCheck.SetValue(c["useFontNames"])
		# Translators: settings label
		self.repairCheck = helper.addItem(wx.CheckBox(self, label=_("Repair jumbled Unicode Devanagari from PDFs")))
		self.repairCheck.SetValue(c["repairUnicode"])
		# Translators: settings label
		self.langCheck = helper.addItem(wx.CheckBox(self, label=_("Mark converted text as Nepali/Hindi so the voice can switch language")))
		self.langCheck.SetValue(c["switchLanguage"])
		# Translators: settings label
		self.visualCheck = helper.addItem(wx.CheckBox(self, label=_("Check the screen to confirm Nepali/Hindi lines when no font name is available")))
		self.visualCheck.SetValue(c["visualCheck"])
		# Translators: settings label
		self.webCheck = helper.addItem(wx.CheckBox(self, label=_("On web pages and chat apps, convert only text whose font is Preeti, Kruti Dev or similar")))
		self.webCheck.SetValue(c["webFontOnly"])
		# Translators: settings label
		self.tessPath = helper.addLabeledControl(_("Tesseract OCR program (leave empty to find it automatically):"), wx.TextCtrl)
		self.tessPath.SetValue(c["tesseractPath"])
		# Translators: settings label
		self.ocrLangs = helper.addLabeledControl(_("OCR languages:"), wx.TextCtrl)
		self.ocrLangs.SetValue(c["ocrLanguages"])

	def onSave(self):
		c = conf()
		setOn(self.enabledCheck.GetValue())
		c["pdfFile"] = self.pdfCheck.GetValue()
		c["mode"] = MODES[self.modeChoice.GetSelection()]
		if c["mode"] != "off":
			c["lastOnMode"] = c["mode"]
		c["encoding"] = list(ENCODING_LABELS)[self.encChoice.GetSelection()]
		c["autoDetectKruti"] = self.krutiCheck.GetValue()
		c["useFontNames"] = self.fontCheck.GetValue()
		c["repairUnicode"] = self.repairCheck.GetValue()
		c["switchLanguage"] = self.langCheck.GetValue()
		c["visualCheck"] = self.visualCheck.GetValue()
		c["webFontOnly"] = self.webCheck.GetValue()
		c["tesseractPath"] = self.tessPath.GetValue().strip().strip('"')
		c["ocrLanguages"] = self.ocrLangs.GetValue().strip() or "nep+hin+eng"
		_menuSync[0]()
