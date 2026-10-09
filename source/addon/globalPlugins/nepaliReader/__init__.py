# -*- coding: utf-8 -*-
# Nepali Reader for NVDA
# Reads Preeti / Kantipur / Sagarmatha / Himali / PCS Nepali and Kruti Dev (Hindi)
# legacy-font text as Devanagari, and repairs jumbled Devanagari from PDFs.
# Licensed under the GNU GPL v2 or later.
#
# Only DOCUMENT TEXT is touched: the add-on wraps NVDA's getTextInfoSpeech, which is what
# speaks text under the caret / review cursor, say all and browse mode. Menus, dialogs,
# buttons and NVDA's own messages never pass through it.

import bisect
import ctypes
import hashlib
import os
import pickle
import re
import threading
import time
import zlib
from collections import OrderedDict

import addonHandler
import api
import config
import globalPluginHandler
import NVDAObjects
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
from . import visualScript
from . import diag
from . import multilangIntegration

addonHandler.initTranslation()

CONF_SECTION = "nepaliReader"
CONF_SPEC = {
	"enabled": "boolean(default=True)",
	"pdfFile": "boolean(default=True)",
	"mode": "option('off', 'auto', 'always', default='auto')",
	"encoding": "option('preeti', 'kantipur', 'sagarmatha', 'himali', 'fontasy', 'pcs', 'krutidev', default='preeti')",
	"autoDetectKruti": "boolean(default=True)",
	"useFontNames": "boolean(default=True)",
	"repairUnicode": "boolean(default=True)",
	"switchLanguage": "boolean(default=True)",
	"visualCheck": "boolean(default=True)",
	"webFontOnly": "boolean(default=True)",
	"lastOnMode": "option('auto', 'always', default='auto')",
	"autoCheckUpdate": "boolean(default=True)",
	"lastUpdateCheck": "float(default=0.0)",
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
	("himali", "Himali (Himalb, Himalli)"),
	("fontasy", "Fontasy Himali"),
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
	# other Chromium / Firefox browsers
	"chromium", "thorium", "yandex", "arc", "duckduckgo", "librewolf", "waterfox", "floorp", "zen",
	"palemoon", "maxthon",
}

PDF_APPS = {
	"acrord32", "acrord64", "acrobat", "foxitreader", "foxitpdfreader", "foxitpdfeditor", "foxitphantompdf",
	"sumatrapdf", "pdfxedit", "pdfxcview", "nitropdf", "nitropdfreader", "pdfelement", "pdfgear", "drawboardpdf",
}

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
		self.totalWords = 0    # total words observed in this window
		self.swaps = []        # this document's own letter swaps, learned from its whole text
		self.learning = False

	@property
	def isUnicodeDocument(self):
		"""A window showing real Unicode Nepali/Hindi: its English letters are English, not Preeti.
		If >= 20% of observed words are Unicode Devanagari (with at least 5 words), or >= 15 words:
		the document is a confirmed native Unicode document."""
		if self.unicodeWords >= 5 and (self.unicodeWords / max(1, self.totalWords) >= 0.20):
			return True
		return self.unicodeWords >= 15

	def recordWords(self, text):
		if not text:
			return
		ws = text.split()
		if not ws:
			return
		self.totalWords += len(ws)
		self.unicodeWords += sum(1 for w in ws if devanagariRepair.hasDevanagari(w))

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
		"""Tracks repair statistics for the document."""
		k, n = devanagariRepair.wordStats(fixed)
		self.afterKnown += k
		self.afterWords += n


class _ConvertingTextInfo:
	"""Wraps a TextInfo for getTextInfoSpeech: same object, but getTextWithFields returns converted text."""

	def __init__(self, info, plugin, unit=None):
		self.__dict__["_nrInfo"] = info
		self.__dict__["_nrPlugin"] = plugin
		self.__dict__["_nrUnit"] = unit

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
		return self.__dict__["_nrPlugin"]._convertFields(self.__dict__["_nrInfo"], formatConfig, unit=self.__dict__.get("_nrUnit"))

	def copy(self):
		if not isOn():
			return self.__dict__["_nrInfo"].copy()
		return _ConvertingTextInfo(self.__dict__["_nrInfo"].copy(), self.__dict__["_nrPlugin"], unit=self.__dict__.get("_nrUnit"))

	def setEndPoint(self, other, which):
		return self.__dict__["_nrInfo"].setEndPoint(_unwrap(other), which)

	def compareEndPoints(self, other, which):
		return self.__dict__["_nrInfo"].compareEndPoints(_unwrap(other), which)

	def isOverlapping(self, other):
		return self.__dict__["_nrInfo"].isOverlapping(_unwrap(other))


class _PlainTextInfo:
	"""Wraps a TextInfo for speaking selections: .text gives the real (converted) text, as reading
	says it (a character as character reading, a word as word reading)."""

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
		return self.__dict__["_nrPlugin"]._selectionText(info)

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


_PLAIN_NUMBER = re.compile(r"^[/(]?[0-9]+(?:[.,:/\-][0-9]+)*[%)]?$|^[/(]?[0-9]*[.,/][0-9]+[%)]?$")

_OWN_COPY = [False]


def _ownCopy(text, notify=False):
	"""Puts text the add-on has already made right on the clipboard: the api.copyToClip hook
	passes it through untouched (looking it up or converting it a second time could change it)."""
	_OWN_COPY[0] = True
	try:
		return api.copyToClip(text, notify=notify)
	finally:
		_OWN_COPY[0] = False


def _formatCopy(formatConfig=None):
	"""A plain dict of document formatting settings. NVDA's own settings section cannot be given
	to dict() (it iterates its keys only), so it is copied item by item."""
	src = formatConfig if formatConfig is not None else config.conf["documentFormatting"]
	if isinstance(src, dict):
		return dict(src)
	try:
		return dict(src.items())
	except Exception:
		pass
	try:
		return {k: src[k] for k in src}
	except Exception:
		return {}


def _isEnglishOutside(idx, piece):
	for tok in (piece or "").split():
		core = tok.strip(".,;:!?()[]{}\"'")
		if len(core) >= 3 and core.isascii() and core.isalpha() and detector.isEnglishWord(core.lower()) and not idx.knows(core):
			return True
	return False


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


class _NepaliNormalizedObject(NVDAObjects.NVDAObject):
	"""Overlay class ensuring that object names (such as files in File Explorer,
	window titles, browser tabs) have their Devanagari text and stripped-matra slugs normalized."""

	def _get_name(self):
		try:
			getter = getattr(super(), "_get_name", None)
			orig = getter() if getter else None
		except Exception:
			orig = None
		if not orig:
			try:
				orig = getattr(super(), "name", None)
			except Exception:
				orig = None
		if not orig or not isOn():
			return orig
		if "\u00e0" in orig:
			orig = devanagariRepair.decodeMojibake(orig)
		if devanagariRepair.hasDevanagari(orig):
			return devanagariRepair.cleanShuffled(orig)
		return orig


class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	def chooseNVDAObjectOverlayClasses(self, obj, clsList):
		if isOn():
			clsList.insert(0, _NepaliNormalizedObject)

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
		self._registerSpeechFilter()
		try:
			multilangIntegration.install()
		except Exception:
			log.debugWarning("Nepali Reader: MultiLang initialization failed", exc_info=True)
		try:
			self._patchCopyAndSelection()
		except Exception:
			log.error("Nepali Reader: could not hook copying", exc_info=True)
		try:
			self._patchWordUnits()
		except Exception:
			log.debugWarning("Nepali Reader: could not hook word units", exc_info=True)
		NVDASettingsDialog.categoryClasses.append(NepaliReaderSettingsPanel)
		self._menu = None
		try:
			wx.CallAfter(self._createMenu)
		except Exception:
			log.debugWarning("Nepali Reader: could not add menu", exc_info=True)
		try:
			# after every add-on has loaded, give up any key another command already uses
			wx.CallAfter(self._avoidGestureClashes)
			wx.CallLater(2000, multilangIntegration.install)
			wx.CallLater(3000, self._checkHooks)
			wx.CallLater(3500, self._startupReminder)
			if conf().get("autoCheckUpdate", True):
				try:
					from . import updater
					updater.startAutoUpdateCheck(conf())
				except Exception:
					pass
		except Exception:
			log.debugWarning("Nepali Reader: gesture check failed", exc_info=True)

	def _startupReminder(self):
		if isOn():
			# Translators: reminder spoken on NVDA startup
			ui.message(_(
				"Nepali Reader active. "
				"Recommendation: Keep Nepali mode off (NVDA+Ctrl+Shift+Space) when typing in English or navigating system menus, "
				"and turn it on when reading Nepali documents or PDFs."
			))

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

		# Check for ClipSpeak or any other clipboard add-on explicitly
		hasClipAddon = any(
			("clipspeak" in type(p).__module__.lower() or "clipboard" in type(p).__module__.lower())
			for p in globalPluginHandler.runningPlugins if p is not self
		)

		for ident in list(getattr(self, "_gestureMap", {}).keys()):
			key = norm(ident)
			taken = None
			if key in ("kb:control+c", "kb:c+control") and hasClipAddon:
				taken = "clipspeak"
			if taken is None:
				for o in owners:
					gmap = getattr(o, "_gestureMap", None) or {}
					for k in gmap.keys():
						if norm(str(k)).lower() == key:
							taken = type(o).__module__
							break
					if taken:
						break
			if taken is None:
				try:
					for module, cls, scriptName in inputCore.manager.userGestureMap.getScriptsForGesture(key):
						if not (module or "").startswith("globalPlugins.nepaliReader"):
							taken = module
							break
				except Exception:
					pass

			if taken:
				try:
					self.removeGestureBinding(ident)
				except Exception:
					pass
				try:
					self._gestureMap.pop(ident, None)
				except Exception:
					pass
				log.info("Nepali Reader: %s is already used by %s, so it was left free" % (ident, taken))

	def terminate(self):
		self._unpatch()
		try:
			multilangIntegration.uninstall()
		except Exception:
			pass
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
		item = menu.Append(wx.ID_ANY, _("Convert selected text or clipboard"))
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, lambda e: wx.CallLater(300, self.script_convertSelection, None), item)
		# Translators: menu item
		item = menu.Append(wx.ID_ANY, _("&Settings... (NVDA+Ctrl+L)"))
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self._onMenuSettings, item)
		# Translators: menu item to check for updates
		itemUpdate = menu.Append(wx.ID_ANY, _("&Check for updates..."))
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, lambda e: self._onCheckUpdates(), itemUpdate)
		# Translators: name of the add-on's submenu in NVDA's Tools menu
		self._menu = toolsMenu.AppendSubMenu(menu, _("&Nepali Reader"))
		_menuSync[0] = self._syncMenu

	def _onCheckUpdates(self):
		from . import updater
		updater.checkUpdate(manual=True, configRef=conf())

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
		if newVal:
			if not getattr(self, "_speechFilterRegistered", False):
				self._registerSpeechFilter()
		else:
			self._docs.clear()
			self._pdfs.clear()
			devanagariRepair.setDocumentSwaps([], None)
			if getattr(self, "_speechFilterRegistered", False):
				try:
					import speech
					speech.filter_speechSequence.unregister(self._filterSpeechSequence)
				except Exception:
					pass
				self._speechFilterRegistered = False
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
			unit = kwargs.get("unit")
			if unit is None:
				for a in args:
					if isinstance(a, str) and a.startswith("unit_"):
						unit = a
						break
					elif hasattr(textInfos, "UNIT_CHARACTER") and a in (
						textInfos.UNIT_CHARACTER, textInfos.UNIT_WORD, textInfos.UNIT_LINE, textInfos.UNIT_PARAGRAPH
					):
						unit = a
						break
			if c["mode"] != "off" or c["repairUnicode"] or c["switchLanguage"]:
				info = _ConvertingTextInfo(_unwrap(info), plugin, unit=unit)
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
		if getattr(self, "_speechFilterRegistered", False):
			try:
				import speech
				speech.filter_speechSequence.unregister(self._filterSpeechSequence)
			except Exception:
				pass
			self._speechFilterRegistered = False

	def _registerSpeechFilter(self):
		self._speechFilterRegistered = False
		try:
			import speech
			if hasattr(speech, "filter_speechSequence") and hasattr(speech.filter_speechSequence, "register"):
				speech.filter_speechSequence.register(self._filterSpeechSequence)
				self._speechFilterRegistered = True
		except Exception:
			log.debugWarning("Nepali Reader: could not register speechSequence filter", exc_info=True)

	def _filterSpeechSequence(self, speechSequence):
		"""Ensures repeated table headers, cell navigation headers, object names,
		and selection announcements are converted and spoken with proper language tagging."""
		if not isOn():
			return speechSequence
		c = conf()
		if c["mode"] == "off" and not c["repairUnicode"] and not c["switchLanguage"]:
			return speechSequence
		mode = c["mode"]
		repair = c["repairUnicode"]
		switchLang = c["switchLanguage"]
		if any(type(x).__name__ == "CharacterModeCommand" for x in speechSequence):
			# character by character speech (arrow keys, typing echo) is resolved from the document
			# text itself in _resolveCharacter; English letters must stay English here
			return speechSequence
		ctxEnc = self._inContext()
		defaultEnc = ctxEnc or c["encoding"]
		out = []
		try:
			from speech.commands import LangChangeCommand
		except ImportError:
			LangChangeCommand = None

		for item in speechSequence:
			if not isinstance(item, str):
				out.append(item)
				continue
			if not item or item.isspace():
				out.append(item)
				continue
			if "\u00e0" in item:
				item = devanagariRepair.decodeMojibake(item)  # a Devanagari file name shown as à¤§à¤°...
			text = item
			# If it looks like legacy text (e.g. repeated table headers, cell labels, selection)
			try:
				fg = api.getForegroundObject()
				isPdf = self._isPdfWindow(fg)
			except Exception:
				isPdf = False
			inCtx = bool(ctxEnc or isPdf)
			if mode != "off":
				# a short piece (a table header, a cell) only in a Preeti document or a PDF, and never a
				# plain number or page count ("/14", "100%", "1.5" are what they say)
				if (len(text.strip()) <= 4 and inCtx and not _PLAIN_NUMBER.match(text.strip())
						and not detector.isEnglishWord(detector._core(text).lower())):
					conv_short = legacyFonts.convert(text.strip(), defaultEnc)
					if conv_short and (devanagariRepair.hasDevanagari(conv_short) or conv_short in (":", "५", "१", "२", "३", "४", "६", "७", "८", "९", "०")):
						if (neLexicon.isLoaded() and neLexicon.isWord(conv_short.strip(".,:;!?()[]{}"))) or any(ch in "!@#$%^&*()+=~`_{}[]\\|/<>?;'-" for ch in text) or conv_short in (":", "५", "१", "२", "३", "४", "६", "७", "८", "९", "०"):
							text = conv_short
				if text == item and detector.looksLegacy(text, defaultEnc, context=inCtx):
					conv = detector.convertMixed(text, lambda t: legacyFonts.convert(t, defaultEnc) or t, encoding=defaultEnc, context=inCtx)
					if conv != text:
						text = conv
						if len(text.split()) >= 2 and mode == "auto":
							self._setContext(defaultEnc)
			if devanagariRepair.hasDevanagari(text) or any(ch in "%M" for ch in text):
				text = devanagariRepair.cleanShuffled(text)
				if repair and (isPdf or self._isBrokenDoc() or devanagariRepair.isBroken(text)):
					text = devanagariRepair.repair(text, broken=True)

			if switchLang and LangChangeCommand and devanagariRepair.hasDevanagari(text):
				if any(type(x).__name__ == "CharacterModeCommand" for x in speechSequence):
					out.append(text)
					continue
				isNe = multilangIntegration.isNepaliDevanagari(text)
				targetLang = "ne" if isNe else "hi"
				prevIsLang = bool(out and isinstance(out[-1], LangChangeCommand) and getattr(out[-1], "lang", "") == targetLang)
				if not prevIsLang:
					out.append(LangChangeCommand(targetLang))
					out.append(text)
					out.append(LangChangeCommand(None))
					continue
			out.append(text)
		return out

	def _patchCopyAndSelection(self):
		"""Copying (browse mode Ctrl+C, NVDA's review copy) and speaking a selection
		(Shift+arrows) use the real text too."""
		self._patched2 = []
		plugin = self
		origCopy = textInfos.TextInfo.copyToClipboard

		def copyToClipboard(info, notify=False):
			try:
				if isOn():
					raw = _unwrap(info).text or ""
					text = plugin._plainText(info)
					target = text if (text and text != raw) else raw
					central = plugin._centralText(info)
					if central is not None:
						# the PDF's own text: nothing may "repair" it a second time
						diag.write("copy (pdf) %r -> %r" % (raw[:80], (central or "")[:80]))
						if central != raw:
							return _ownCopy(textInfos.convertToCrlf(central), notify)
						return origCopy(_unwrap(info), notify)
					if devanagariRepair.hasDevanagari(target):
						cleaned = devanagariRepair.cleanShuffled(target)
						if plugin._isPdfWindow(info.obj) or devanagariRepair.isBroken(target) or plugin._isBrokenDoc():
							cleaned = devanagariRepair.repair(cleaned, broken=True)
						if cleaned and cleaned != raw:
							return _ownCopy(textInfos.convertToCrlf(cleaned), notify)
					elif text and text != raw:
						return _ownCopy(textInfos.convertToCrlf(text), notify)
			except Exception:
				log.debugWarning("Nepali Reader: copy failed", exc_info=True)
			return origCopy(_unwrap(info), notify)

		textInfos.TextInfo.copyToClipboard = copyToClipboard
		self._patched2.append((textInfos.TextInfo, "copyToClipboard", origCopy, copyToClipboard))

		try:
			from cursorManager import CursorManager
			origCursorCopy = CursorManager.script_copyToClipboard

			def cursorCopyToClipboard(mgr, gesture):
				if isOn():
					try:
						info = mgr.makeTextInfo(textInfos.POSITION_SELECTION)
						if not info.isCollapsed:
							raw = info.text or ""
							text = plugin._plainText(info)
							target = text if (text and text != raw) else raw
							central = plugin._centralText(info)
							if central is not None:
								diag.write("copy (pdf cursor) %r -> %r" % (raw[:80], (central or "")[:80]))
								if central != raw:
									_ownCopy(textInfos.convertToCrlf(central), notify=True)
									return
								return origCursorCopy(mgr, gesture)
							if devanagariRepair.hasDevanagari(target):
								cleaned = devanagariRepair.cleanShuffled(target)
								if plugin._isPdfWindow(mgr) or devanagariRepair.isBroken(target) or plugin._isBrokenDoc():
									cleaned = devanagariRepair.repair(cleaned, broken=True)
								if cleaned and cleaned != raw:
									_ownCopy(textInfos.convertToCrlf(cleaned), notify=True)
									return
							if not text or text == raw:
								c = conf()
								ctxEnc = plugin._inContext()
								defaultEnc = ctxEnc or c["encoding"]
								if c["mode"] != "off" and not plugin._docState().isUnicodeDocument:
									isPdf = plugin._isPdfWindow(mgr)
									conv = detector.convertMixed(raw, lambda t: legacyFonts.convert(t, defaultEnc) or t, encoding=defaultEnc, context=bool(ctxEnc or isPdf))
									if conv and conv != raw:
										text = conv
								if c["repairUnicode"] and text and devanagariRepair.hasDevanagari(text):
									text = devanagariRepair.repair(text, broken=True if (plugin._isPdfWindow(mgr) or plugin._isBrokenDoc()) else None)
							if text and text != raw:
								_ownCopy(textInfos.convertToCrlf(text), notify=True)
								return
					except Exception:
						log.debugWarning("Nepali Reader: cursor copy failed", exc_info=True)
				return origCursorCopy(mgr, gesture)

			CursorManager.script_copyToClipboard = cursorCopyToClipboard
			self._patched2.append((CursorManager, "script_copyToClipboard", origCursorCopy, cursorCopyToClipboard))
		except Exception:
			log.debugWarning("Nepali Reader: could not hook CursorManager copy", exc_info=True)

		try:
			origCopyToClip = api.copyToClip

			def copyToClip(text, notify=False):
				try:
					if isOn() and not _OWN_COPY[0] and isinstance(text, str) and text:
						viaIndex = plugin._pdfTextOfString(text)
						if viaIndex is not None:
							text = viaIndex.replace("\r\n", "\n").replace("\n", "\r\n") if "\n" in viaIndex else viaIndex
						elif devanagariRepair.hasDevanagari(text):
							cleaned = devanagariRepair.cleanShuffled(text)
							if devanagariRepair.isBroken(text) or plugin._isBrokenDoc():
								cleaned = devanagariRepair.repair(cleaned, broken=True)
							if cleaned:
								text = cleaned
						elif conf()["mode"] != "off" and plugin._inContext() and detector.looksLegacy(text, plugin._inContext(), context=True):
							# (only in a Preeti document: other add-ons copy all kinds of text)
							enc = plugin._inContext()
							conv = detector.convertMixed(text, lambda t: legacyFonts.convert(t, enc) or t, encoding=enc, context=True)
							if conv:
								text = conv
				except Exception:
					pass
				return origCopyToClip(text, notify=notify)

			api.copyToClip = copyToClip
			self._patched2.append((api, "copyToClip", origCopyToClip, copyToClip))
		except Exception:
			log.debugWarning("Nepali Reader: could not hook api.copyToClip", exc_info=True)

		try:
			import speech
			import speech.speech as speechModule
			origSel = speechModule.speakSelectionChange

			def speakSelectionChange(oldInfo, newInfo, speakSelected=True, speakUnselected=True, generalize=False, priority=None, *args, **kwargs):
				rawOld, rawNew = _unwrap(oldInfo), _unwrap(newInfo)
				if not isOn():
					return origSel(rawOld, rawNew, speakSelected, speakUnselected, generalize, priority, *args, **kwargs)
				# NVDA's own selection speech (selected / unselected / selected instead, a single
				# character spelled), with every piece's text taken from the real text
				try:
					return origSel(_PlainTextInfo(rawOld, plugin), _PlainTextInfo(rawNew, plugin), speakSelected, speakUnselected, generalize, priority, *args, **kwargs)
				except Exception:
					diag.exception("selection speech")
				return origSel(rawOld, rawNew, speakSelected, speakUnselected, generalize, priority, *args, **kwargs)

			speechModule.speakSelectionChange = speakSelectionChange
			self._patched2.append((speechModule, "speakSelectionChange", origSel, speakSelectionChange))
			speech.speakSelectionChange = speakSelectionChange
			self._patched2.append((speech, "speakSelectionChange", origSel, speakSelectionChange))
		except Exception:
			log.debugWarning("Nepali Reader: could not hook selection speech", exc_info=True)

	def _patchWordUnits(self):
		"""Word navigation and word selection (Ctrl+Arrow, Ctrl+Shift+Arrow) step over whole words:
		a PDF word the viewer breaks into pieces (मलु कु ी; Preeti btf{ split at its { key) is one
		word, as the page shows it."""
		plugin = self
		local = threading.local()
		owners = []
		try:
			import textInfos.offsets as tio
			owners.append(tio.OffsetsTextInfo)
		except Exception:
			pass
		try:
			import virtualBuffers
			owners.append(virtualBuffers.VirtualBufferTextInfo)
		except Exception:
			pass

		def make(orig):
			def _getWordOffsets(ti, offset):
				if getattr(local, "busy", False):
					return orig(ti, offset)
				local.busy = True
				try:
					res = orig(ti, offset)
					if not isOn():
						return res
					try:
						new = plugin._realWordOffsets(ti, offset, res)
					except Exception:
						diag.exception("word offsets")
						new = None
					return new if new is not None else res
				finally:
					local.busy = False
			return _getWordOffsets

		for owner in owners:
			orig = owner.__dict__.get("_getWordOffsets")
			if orig is None:
				continue
			new = make(orig)
			setattr(owner, "_getWordOffsets", new)
			self._patched2.append((owner, "_getWordOffsets", orig, new))

	def _realWordOffsets(self, ti, offset, res):
		"""(start, end) of the whole real word at `offset`, or None to keep the viewer's word."""
		start, end = res[0], res[1]
		lineStart, lineEnd = ti._getLineOffsets(offset)
		if not (lineStart <= offset < lineEnd) or lineEnd - lineStart > 4000:
			return None
		lineText = ti._getTextRange(lineStart, lineEnd)
		if not lineText or len(lineText) != lineEnd - lineStart:
			return None  # offsets are not one per character (characters outside the BMP)
		rel = offset - lineStart
		if lineText[rel].isspace():
			return None
		idx = self._readyIndex(getattr(ti, "obj", None))
		if idx is not None:
			span = self._indexWordSpan(idx, lineText, rel)
		else:
			span = self._legacyWordSpan(lineText, rel)
		if span is None:
			return None
		ns = min(start, lineStart + span[0])
		ne = max(end, lineStart + span[1])
		if (ns, ne) == (start, end):
			return None
		return (ns, ne)

	def _indexWordSpan(self, idx, lineText, rel):
		"""The word of the PDF's real text that the character at `rel` of the viewer's line belongs
		to, as (start, end) in the line (with its trailing spaces), or None."""
		cache = getattr(self, "_wordSpans", None)
		if cache is None:
			cache = self._wordSpans = _LRU(64)
		ck = (id(idx), lineText)
		spans = cache.get_(ck)
		if spans is None:
			spans = []
			key = pdfText.matchKey(lineText)
			p = idx._find(key) if key else -1
			if p >= 0:
				starts = idx.starts
				cur = s0 = last = None
				q = p
				for i, ch in enumerate(lineText):
					k = pdfText.keyOf(ch)
					if not k:
						continue
					wi = bisect.bisect_right(starts, q) - 1
					q += len(k)
					if wi != cur:
						if cur is not None:
							spans.append((s0, last + 1))
						cur, s0 = wi, i
					last = i
				if cur is not None:
					spans.append((s0, last + 1))
			cache.put(ck, spans)
		for s, e in spans:
			if s <= rel < e:
				while e < len(lineText) and lineText[e] in " \t\xa0":
					e += 1
				return (s, e)
		return None

	def _legacyWordSpan(self, lineText, rel):
		"""A Preeti word that NVDA breaks at one of its sign keys (btf{, a'em\\g'): the whole word
		between spaces, or None for anything else (English keeps NVDA's own words)."""
		c = conf()
		if c["mode"] == "off":
			return None
		s = rel
		while s > 0 and not lineText[s - 1].isspace():
			s -= 1
		e = rel
		while e < len(lineText) and not lineText[e].isspace():
			e += 1
		run = lineText[s:e]
		if len(run) > 40 or not run.isascii() or run.isalnum() or not any(ch.isalpha() for ch in run):
			return None
		core = detector._core(run)
		if not core or detector.isEnglishWord(core.lower()):
			return None
		ctxEnc = self._inContext()
		if not ctxEnc and not detector.looksLegacy(run, c["encoding"], context=False):
			return None
		while e < len(lineText) and lineText[e] in " \t\xa0":
			e += 1
		return (s, e)

	def _selectionText(self, info):
		"""What a selected or unselected piece says: a character as character reading says it, a
		word as word reading says it, more as line reading (the PDF's real text when known)."""
		info = _unwrap(info)
		raw = info.text or ""
		if not raw or raw.isspace():
			return raw
		for unit in (textInfos.UNIT_CHARACTER, getattr(textInfos, "UNIT_WORD", "word")):
			try:
				u = info.copy()
				u.collapse()
				u.expand(unit)
				same = u.compareEndPoints(info, "startToStart") == 0 and u.compareEndPoints(info, "endToEnd") == 0
			except Exception:
				same = False
			if same:
				try:
					fields = self._convertFields(info, None, unit=unit)
					text = "".join(f for f in fields if isinstance(f, str))
					diag.write("select %s %r -> %r" % (unit, raw[:60], text[:60]))
					return text
				except Exception:
					diag.exception("selection by %s" % unit)
				break
		central = self._centralText(info)
		if central is not None:
			diag.write("select (pdf) %r -> %r" % (raw[:80], central[:80]))
			return central
		if devanagariRepair.hasDevanagari(raw):
			conv = devanagariRepair.cleanShuffled(raw)
			if self._isPdfWindow(info.obj) or devanagariRepair.isBroken(raw):
				conv = devanagariRepair.repair(conv, broken=True)
			return conv
		conv = self._plainText(info)
		if not conv or conv == raw:
			c = conf()
			ctxEnc = self._inContext()
			defaultEnc = ctxEnc or c["encoding"]
			if c["mode"] != "off" and not self._docState().isUnicodeDocument:
				inCtx = bool(ctxEnc or self._isPdfWindow(info.obj))
				if inCtx:
					c_mixed = detector.convertMixed(raw, lambda t: legacyFonts.convert(t, defaultEnc) or t, encoding=defaultEnc, context=inCtx)
					if c_mixed and c_mixed != raw:
						conv = c_mixed
			if c["repairUnicode"] and conv and devanagariRepair.hasDevanagari(conv):
				conv = devanagariRepair.repair(conv, broken=True)
		diag.write("select %r -> %r" % (raw[:80], (conv or "")[:80]))
		return conv

	def _centralText(self, info):
		"""In a PDF whose real text is known, the one text every way of reading (line, word,
		character, selection, copy) shares: what the index says. None when there is no index."""
		try:
			info = _unwrap(info)
			if not isOn() or not self._isPdfWindow(info.obj):
				return None
			idx = self._pdfIndex(info.obj)
			if idx is None:
				return None
			raw = info.text or ""
		except Exception:
			diag.exception("central text")
			return None
		if not raw.strip():
			return raw
		# straight to the index, the same lookup word and line reading use (no field conversion
		# in between that could quietly hand the raw text back)
		new = None
		try:
			if "\n" in raw or "\r" in raw:
				out = []
				found = False
				for ln in raw.splitlines(True):
					body = ln.rstrip("\r\n")
					end = ln[len(body):]
					got = self._indexText(None, idx, body) if pdfText.keyOf(body) else None
					if got is not None:
						found = True
						out.append(got + end)
					else:
						out.append(ln)
				new = "".join(out) if found else None
			else:
				new = self._indexText(info, idx, raw)
		except Exception:
			diag.exception("central text lookup")
			new = None
		if new is None:
			try:
				new = self._plainText(info)
			except Exception:
				diag.exception("central text fallback")
				new = raw
		return new

	def _pdfTextOfString(self, text):
		"""The real text of a plain string that is being copied out of a PDF viewer (other
		add-ons copy the raw text themselves): found through the index, or None."""
		try:
			if not isOn() or not isinstance(text, str) or not text.strip():
				return None
			obj = api.getFocusObject()
			if obj is None or not self._isPdfWindow(obj):
				return None
			idx = self._pdfIndex(obj)
			if idx is None:
				return None
			new = self._indexText(None, idx, text)
			diag.write("copy (string) %r -> %r" % (text[:80], (new or "")[:80]))
			return new
		except Exception:
			diag.exception("pdf string text")
			return None

	def _plainText(self, info):
		"""The real text of a TextInfo (Preeti converted, PDF text rebuilt), as plain text."""
		info = _unwrap(info)
		if not isOn():
			return info.text
		try:
			fields = self._convertFields(info, None)
		except Exception:
			diag.exception("plain text of a selection")
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
		if st.status == "building" and not getattr(st, "waited", False):
			# The first words of a PDF are spoken before the real text is known and would be guesses
			# (संशोिन, मलुकी): wait once, briefly, for the first pages instead of speaking them.
			st.waited = True
			t0 = time.monotonic()
			while st.status == "building" and time.monotonic() - t0 < 3.0:
				time.sleep(0.04)
			diag.write("pdf: waited %.1f s for the first pages (%s)" % (time.monotonic() - t0, st.status))
		return st.index if st.status == "ready" else None

	def _readyIndex(self, obj):
		"""The PDF index of the foreground window if it is already built (never starts or waits)."""
		try:
			if not conf()["pdfFile"] or not self._ready:
				return None
			st = self._pdfs.get_(self._foregroundKey())
			if st is None or st.status != "ready":
				return None
			if obj is not None and not self._isPdfWindow(obj):
				return None
			return st.index
		except Exception:
			return None

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
		for pre in ("Finished loading PDF", "Loading PDF"):
			# Brave/Chrome put their status message in front of the first line of the page
			if text.startswith(pre) and len(text) > len(pre):
				rest = text[len(pre):]
				got = self._indexText(None, idx, rest) if pdfText.keyOf(rest) else None
				return pre + (got if got is not None else rest)
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
		if pieces and any(not ok and _isEnglishOutside(idx, pc) for pc, ok in pieces):
			# an English word the document does not have: this is the viewer's own text (a "Fit to
			# page" button), not the page - a short word of it must not be read as Preeti (to = तय)
			pieces = None
		if not pieces or not any(ok for _p, ok in pieces):
			try:
				diag.write("index miss: %r key=%r" % (text[:90], key[:60]))
			except Exception:
				pass
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
		# spaces and signs the index has no letters for (a ▪ bullet) stay as the viewer shows them
		i = 0
		while i < len(text) and (text[i].isspace() or not pdfText.keyOf(text[i])):
			i += 1
		j = len(text)
		while j > i and (text[j - 1].isspace() or not pdfText.keyOf(text[j - 1])):
			j -= 1
		lead = text[:i]
		trail = text[j:]
		result_text = lead + " ".join(out) + trail
		if devanagariRepair.hasDevanagari(result_text):
			# what the PDF itself says is final: nothing downstream may "repair" it again (the
			# pieces the index did not know were already repaired one by one above)
			goodToks = set()
			allGood = True
			for pc, good in pieces:
				if not pc:
					continue
				if good:
					goodToks.update(pc.split())
				else:
					allGood = False
			devanagariRepair.markExact(" ".join(t for t in result_text.split() if allGood or t in goodToks))
		return result_text


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

	@staticmethod
	def _wordContext(info):
		"""(text of the word holding info, offset of info in it) or None."""
		try:
			rawInfo = _unwrap(info)
			word = rawInfo.copy()
			word.expand(textInfos.UNIT_WORD)
			pre = word.copy()
			pre.setEndPoint(rawInfo, "endToStart")
			return word.text, len(pre.text)
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
			if app not in WEB_APPS:
				return ".pdf" in title
			# a browser: decided once per tab and title (answers that say "no" are asked again after
			# a few seconds, while a PDF may still be loading)
			key = (fg.windowHandle if fg else None, title)
			if not hasattr(self, "_pdfTabs"):
				self._pdfTabs = _LRU(100)
			now = time.monotonic()
			cached = self._pdfTabs.get_(key)
			if cached is not None and (cached[0] or now < cached[1]):
				return cached[0]
			from . import pdfLocate
			url = (pdfLocate._urlFromObject(obj) or "").lower()
			if url:
				# the address decides: a web page whose title mentions a .pdf is not a PDF
				res = pdfLocate._isPdfUrl(url) or self._isPdfViewerObj(obj)
			else:
				res = ".pdf" in title or self._isPdfViewerObj(obj)
				if not res and not (cached is not None and cached[2]):
					# last resort, from the title alone: it may search folders and read files, so it
					# runs in the background and never holds up speech
					self._lookUpTitleLater(key, rawTitle, getattr(fg, "processID", None))
			self._pdfTabs.put(key, (res, now + 5.0, True))
			return res
		except Exception:
			return False

	def _lookUpTitleLater(self, key, title, pid):
		from . import pdfLocate

		def work():
			try:
				found = pdfLocate.findFromTitle(title, pid)
			except Exception:
				found = None
			if found:
				self._pdfTabs.put(key, (True, 0.0, True))
				self._pdfMemo = None
				diag.write("pdf window from its title: %r -> %r" % (title, found))

		threading.Thread(target=work, name="NepaliReaderPdfTitle", daemon=True).start()

	@staticmethod
	def _isPdfViewerObj(obj):
		"""Detects if an object is inside Chrome/Edge/Brave PDF viewer from UI cues."""
		try:
			o = getattr(obj, "rootNVDAObject", None) or obj
			seen = 0
			while o is not None and seen < 20:
				seen += 1
				name = (getattr(o, "name", None) or "").lower()
				val = (getattr(o, "value", None) or "").lower()
				desc = (getattr(o, "description", None) or "").lower()
				if any(marker in name or marker in val or marker in desc for marker in (
					"pdf is inaccessible", "add text annotations", "save to google drive",
					"application/pdf", "finished loading pdf", "rotate counterclockwise",
					"fit to page", "fit to width", "zoom in", "zoom out",
					"chrome-extension://mhjfbmdgcfjbbpaeojofohoefgiehjai", "pdf viewer", "pdf plugin"
				)):
					return True
				try:
					ia = getattr(o, "IAccessibleObject", None)
					if ia:
						accName = (ia.accName(getattr(o, "IAccessibleChildID", 0)) or "").lower()
						accVal = (ia.accValue(getattr(o, "IAccessibleChildID", 0)) or "").lower()
						if any(marker in accName or marker in accVal for marker in (
							"pdf is inaccessible", "add text annotations", "finished loading pdf",
							"rotate counterclockwise", "fit to page", "application/pdf", "pdf viewer"
						)):
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

	def _convertFields(self, info, formatConfig, unit=None):
		c = conf()
		if not isOn():
			return info.getTextWithFields(formatConfig)
		if diag.wanted():
			fields = self._convertFieldsInner(info, formatConfig, c, unit=unit)
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
		return self._convertFieldsInner(info, formatConfig, c, unit=unit)

	def _resolveCharacter(self, info, formatConfig, c):
		"""Resolves a single character during Left/Right Arrow navigation, repairing hybrid residue,
		decomposed matras, glued digit keys, Preeti keys, and inverted reph from word context."""
		fields = info.getTextWithFields(formatConfig)
		orig_char = info.text or ""
		if not orig_char:
			return fields

		# Check DocIndex first if reading a PDF
		if self._isPdfWindow(info.obj):
			idx = self._pdfIndex(info.obj)
			if idx is not None:
				ctx = self._lineContext(info)
				if ctx:
					line, off = ctx
					chAt = idx.charAt(line, off, len(orig_char))
					if chAt and devanagariRepair.hasDevanagari(chAt):
						chAt = devanagariRepair.cleanForCharNav(chAt)
						for i, item in enumerate(fields):
							if isinstance(item, str):
								fields[i] = chAt
						return fields
					if chAt and chAt.isascii() and orig_char.isascii() and chAt == orig_char:
						# English letter, digit or sign: the PDF itself says it is not Preeti
						return fields

		ctx = self._lineContext(info)
		word = None
		char_off = 0
		if ctx:
			line, off = ctx
			if 0 <= off < len(line) and line[off] not in (" ", "\t", "\r", "\n", "।", "॥"):
				ws = max(line.rfind(" ", 0, off), line.rfind("\t", 0, off)) + 1
				we = len(line)
				for sep in (" ", "\t", "\r", "\n", "।", "॥"):
					k = line.find(sep, off)
					if k >= 0:
						we = min(we, k)
				if ws <= off < we:
					word = line[ws:we]
					char_off = off - ws
		if not word:
			wctx = self._wordContext(info)
			if wctx:
				w_cand, w_off = wctx
				if w_cand and 0 <= w_off < len(w_cand) and w_cand[w_off] not in (" ", "\t", "\r", "\n", "।", "॥"):
					word = w_cand.strip()
					char_off = min(w_off, max(0, len(word) - 1))

		verdict = None
		if orig_char.isascii() and not orig_char.isspace():
			verdict = self._lineTokenVerdict(info, c, ctx)
			if verdict is False:
				return fields
			if verdict is None and word and word.isascii() and not self._wordLooksLegacy(word, c):
				return fields

		ptext = ""
		ntext = ""
		try:
			raw = _unwrap(info)
			prev = raw.copy()
			if prev.move(textInfos.UNIT_CHARACTER, -1) != 0:
				prev.expand(textInfos.UNIT_CHARACTER)
				ptext = prev.text or ""
			nxt = raw.copy()
			if nxt.move(textInfos.UNIT_CHARACTER, 1) != 0:
				nxt.expand(textInfos.UNIT_CHARACTER)
				ntext = nxt.text or ""
		except Exception:
			pass

		ctxEnc = self._inContext()
		isPdf = self._isPdfWindow(info.obj)
		enc = ctxEnc or c["encoding"]
		inLegacy = bool(ctxEnc or verdict is True or (word and detector.looksLegacy(word, enc, context=bool(ctxEnc or verdict is True))))

		res = None

		# 1. A digit is a digit. It stands for a Preeti letter (बा६ -> बाट, यु४ -> युद्ध) only where the
		#    dictionary proves the word is that letter's word and not a word with a digit in it
		if orig_char in devanagariRepair._GLUED_DIGIT_MAP:
			if word and devanagariRepair.hasDevanagariLetters(word):
				plan = devanagariRepair.gluedDigitPlan(word)
				if plan and len(plan) == len(word) and 0 <= char_off < len(plan):
					res = plan[char_off]
				elif not orig_char.isascii():
					res = orig_char
			elif not orig_char.isascii():
				res = orig_char  # a Devanagari digit among digits or punctuation

		# 2. Preeti shifted number row symbols (% -> ५, ! -> १, @ -> २, etc.)
		elif orig_char in devanagariRepair._PREETI_SHIFT_DIGIT_MAP:
			# only where the line reading itself turns this word into Nepali (a "!" or "%" after
			# a Unicode word is punctuation, not a digit key)
			res = devanagariRepair._PREETI_SHIFT_DIGIT_MAP[orig_char] if inLegacy else orig_char

		# 3. Preeti colon: M -> :
		elif orig_char == "M":
			if inLegacy or devanagariRepair.hasDevanagari(ptext) or (word and devanagariRepair.hasDevanagari(word)):
				res = ":"

		# 4. Preeti matra keys: ], }, [, ¬, {, |
		elif orig_char == "]":
			p = (word[char_off - 1] if word and char_off > 0 else "") or ptext
			if devanagariRepair.hasDevanagari(p):
				if any(p.endswith(s) for s in ("ो", "ौ", "े", "ै")):
					res = ""
				elif p.endswith("ा"):
					res = "ो"
				else:
					res = "े"
		elif orig_char == "}":
			p = (word[char_off - 1] if word and char_off > 0 else "") or ptext
			if devanagariRepair.hasDevanagari(p):
				if any(p.endswith(s) for s in ("ो", "ौ", "े", "ै")):
					res = ""
				elif p.endswith("ा"):
					res = "ौ"
				else:
					res = "ै"
		elif orig_char in ("[", "¬", "\u00ac"):
			p = (word[char_off - 1] if word and char_off > 0 else "") or ptext
			if devanagariRepair.hasDevanagari(p):
				res = "ृ" if orig_char == "[" else "ु"
		elif orig_char == "{":
			res = "र्"
		elif orig_char == "|":
			res = "्र"

		# 5. Keystroke resolution inside a word
		if res is None and word:
			# A. Legacy / Preeti word (ASCII)
			if not devanagariRepair.hasDevanagari(word) and c["mode"] != "off":
				conv = legacyFonts.convert(word, enc)
				if conv and (devanagariRepair.hasDevanagari(conv) or (neLexicon.isLoaded() and neLexicon.isWord(conv.strip(".,:;!?()[]{}"))) or inLegacy):
					c_cur = word[char_off] if 0 <= char_off < len(word) else orig_char
					p_cur = word[char_off - 1] if char_off > 0 else ""
					n_cur = word[char_off + 1] if char_off + 1 < len(word) else ""
					if c_cur == 'f' and n_cur == ']': res = 'ो'
					elif c_cur == ']' and p_cur == 'f': res = ''
					elif c_cur == 'f' and n_cur == '}': res = 'ौ'
					elif c_cur == '}' and p_cur == 'f': res = ''
					elif c_cur == 'P' and n_cur == ']': res = 'ऐ'
					elif c_cur == ']' and p_cur == 'P': res = ''
					elif c_cur == 'c' and n_cur == 'f': res = 'आ'
					elif c_cur == 'f' and p_cur == 'c': res = ''
					elif c_cur == '|': res = '्र'
					elif c_cur == '{': res = 'र्'
					elif c_cur == ']': res = 'े'
					elif c_cur == '}': res = 'ै'
					elif c_cur == '[': res = 'ृ'
					elif c_cur in ('\u00ac', '¬'): res = 'ु'
					elif c_cur == 'M': res = ':'
					elif c_cur in legacyFonts.PREETI_MAP: res = legacyFonts.PREETI_MAP[c_cur]
					else: res = c_cur

			# B. Devanagari or hybrid word
			elif devanagariRepair.hasDevanagari(word):
				cleaned_word = devanagariRepair.cleanForCharNav(word)
				c_cur = word[char_off] if 0 <= char_off < len(word) else orig_char
				p_cur = word[char_off - 1] if char_off > 0 else ""
				if c_cur == ']' and any(p_cur.endswith(s) for s in ('ो', 'ौ', 'े', 'ै')):
					res = ''
				elif c_cur == '}' and any(p_cur.endswith(s) for s in ('ो', 'ौ', 'े', 'ै')):
					res = ''
				elif c_cur in ('g', 'x') and devanagariRepair.hasDevanagari(p_cur) and char_off == len(word) - 1:
					res = ''
				elif cleaned_word:
					if len(word) == len(cleaned_word):
						res = cleaned_word[char_off] if 0 <= char_off < len(cleaned_word) else orig_char
					else:
						import difflib
						sm = difflib.SequenceMatcher(None, word, cleaned_word)
						for tag, alo, ahi, blo, bhi in sm.get_opcodes():
							if alo <= char_off < ahi:
								if tag == "equal":
									res = cleaned_word[blo + (char_off - alo)]
								elif tag in ("replace", "insert"):
									sub_len = bhi - blo
									offset = char_off - alo
									res = cleaned_word[blo + offset] if offset < sub_len else ""
								elif tag == "delete":
									res = ""
								break

		# 6. Fallback standalone character mapping
		if res is None:
			if inLegacy and orig_char in legacyFonts.PREETI_MAP:
				res = legacyFonts.PREETI_MAP.get(orig_char)
			elif devanagariRepair.hasDevanagari(orig_char):
				res = devanagariRepair.composeMatras(orig_char)

		if res is not None:
			# converter-internal markers must never reach the speech
			res = res.replace("\ue001", "\u093f").replace("\ue002", "\u0930\u094d").replace("\ue003", "")
			for idx, item in enumerate(fields):
				if isinstance(item, str):
					fields[idx] = res
		return fields

	def _lineToken(self, info, c, ctx):
		"""(word as written, word as the line reading says it) for the word under `info`, or None
		when that cannot be told. Character and word navigation use this so they always agree with
		line reading."""
		if not ctx:
			return None
		line, off = ctx
		try:
			raw = _unwrap(info)
			if self._readyIndex(raw.obj) is not None:
				# a PDF whose real text is known: words come from it, not from lining up tokens
				return None
			li = raw.copy()
			li.expand(textInfos.UNIT_LINE)
			fc = _formatCopy()
			fc["reportFontName"] = True
			fields = li.getTextWithFields(fc)
			orig = "".join(f for f in fields if isinstance(f, str))
			key = ("tokverdict", orig, self._inContext(), c["mode"], c["encoding"])
			cached = self._cache.get_(key)
			if cached is None:
				out = self._convertFieldList(li, list(fields), c, unit=textInfos.UNIT_LINE)
				conv = "".join(f for f in out if isinstance(f, str))
				cached = (orig, conv)
				self._cache.put(key, cached)
			orig, conv = cached
			if orig.rstrip("\r\n") != line.rstrip("\r\n"):
				return None
			toks = [m for m in re.finditer(r"\S+", orig)]
			ctoks = conv.split()
			if len(toks) != len(ctoks):
				return None
			for m, ct in zip(toks, ctoks):
				t = m.group(0)
				if ct != t and not any(ch.isascii() or "\u0900" <= ch <= "\u097f" for ch in t):
					return None  # the tokens do not line up (a bullet or sign left out of the reading)
				if m.start() <= off < m.end():
					return m.group(0), ct
		except Exception:
			log.debugWarning("Nepali Reader: could not decide the word for navigation", exc_info=True)
		return None

	def _lineTokenVerdict(self, info, c, ctx):
		"""True if the word under `info` is converted when its line is read, False if reading the line
		leaves it as it is (English, numbers), None if that cannot be told."""
		tok = self._lineToken(info, c, ctx)
		if tok is None:
			return None
		return tok[1] != tok[0]

	def _wordLooksLegacy(self, word, c):
		"""Fallback when the line cannot be examined: is this ASCII word Preeti?"""
		try:
			core = detector._core(word)
			if not core or not any(ch.isascii() and ch.isalpha() for ch in core):
				return False
			if detector.isEnglishWord(core.lower()):
				return False
			return detector.looksLegacy(word, self._inContext() or c["encoding"], context=bool(self._inContext()))
		except Exception:
			return True

	def _convertFieldsInner(self, info, formatConfig, c, unit=None):
		try:
			rawText = info.text or ""
			if rawText:
				self._docState().recordWords(rawText)
		except Exception:
			rawText = ""

		if unit == textInfos.UNIT_CHARACTER:
			return self._resolveCharacter(info, formatConfig, c)

		if unit == getattr(textInfos, "UNIT_WORD", "word") and rawText.strip() and rawText.isascii() and c["mode"] != "off":
			# a word is read as the line reading reads it: English stays English, Preeti is converted
			# (also a number such as !(*) or @)&@ that the word alone cannot show to be Preeti)
			tok = self._lineToken(info, c, self._lineContext(info))
			if tok is not None:
				orig, conv = tok
				if conv == orig:
					return info.getTextWithFields(formatConfig)
				if rawText.strip() == orig:
					fields = list(info.getTextWithFields(formatConfig))
					done = False
					for i, f in enumerate(fields):
						if isinstance(f, str):
							if not done:
								fields[i] = f.replace(orig, conv) if orig in f else conv
								done = True
							else:
								fields[i] = ""
					if done:
						return fields

		wantFont = c["useFontNames"] and c["mode"] != "off"
		fc = formatConfig
		if wantFont:
			fc = _formatCopy(formatConfig or None)
			fc["reportFontName"] = True
		fields = info.getTextWithFields(fc)
		try:
			return self._convertFieldList(info, fields, c, unit=unit)
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

	def _convertFieldList(self, info, fields, c, unit=None):
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
				if item and "\u00e0" in item:
					dec = devanagariRepair.decodeMojibake(item)
					if dec != item:
						fields[i] = item = dec
				if item:
					runs.append((i, item, "unicode" if unicodeFont else fontKnown, curEnc))
			elif isinstance(item, textInfos.FieldCommand) and item.command == "formatChange":
				name = item.field.get("font-name") if item.field else None
				fontKnown = bool(name)
				curEnc = legacyFonts.encodingForFontName(name) if name else None
				lower = (name or "").lower()
				unicodeFont = bool(name) and any(f in lower for f in UNICODE_DEVANAGARI_FONTS)
			elif isinstance(item, textInfos.FieldCommand) and item.command == "controlStart" and item.field:
				for attr in ("table-rowheadertext", "table-columnheadertext", "name", "description"):
					val = item.field.get(attr)
					if isinstance(val, str) and val:
						if curEnc:
							conv = legacyFonts.convert(val, curEnc)
							if conv and conv != val:
								item.field[attr] = conv
						elif self._isPdfWindow(info.obj) and detector.looksLegacy(val, "preeti"):
							conv = detector.convertMixed(val, legacyFonts.preetiFamilyToUnicode)
							if conv and conv != val:
								item.field[attr] = conv
						elif devanagariRepair.hasDevanagari(val):
							val_clean = devanagariRepair.cleanShuffled(val)
							if val_clean and val_clean != val:
								item.field[attr] = val_clean
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
					return self._withLanguage(out, rebuilt, c, unit=unit)
		if repair:
			for k, (i, text, known, enc) in enumerate(runs):
				if devanagariRepair.hasDevanagari(text):
					cl = devanagariRepair.cleanShuffled(text)
					if cl != text:
						out[i] = cl
						runs[k] = (i, cl, known, enc)
						changed = True
		if repair and ((self._isPdfWindow(info.obj) and not self._isWebNonPdf(info.obj)) or any(devanagariRepair.isBroken(t) for _, t, _, _ in runs)):
			# only PDF text layers are damaged; Unicode Nepali on web pages and in documents is
			# correct and must never be "repaired" (it turned भनसुन into निसान on news sites)
			st = self._docState()
			devanagariRepair.setDocumentSwaps(st.swaps, (id(st), len(st.swaps)))
			for k, (i, text, known, enc) in enumerate(runs):
				if devanagariRepair.hasDevanagari(text):
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
						runs[k] = (i, fixed, known, None)
						changed = True

		if mode == "off":
			if rebuilt or (c["switchLanguage"] and any(devanagariRepair.hasDevanagari(x) for x in out if isinstance(x, str))):
				return self._withLanguage(out, rebuilt, c, unit=unit)
			return out if changed else fields
		# 2. decide which runs are legacy text and with which encoding
		convert = {}  # index -> (encoding, protectEnglish)
		unknown = []
		symRuns = []
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
				# numbers/symbols alone: they are Preeti only when the text next to them is Preeti
				# (decided below), never next to Unicode Nepali or English: "(राजनीतिक)" keeps "("
				isUniDoc = self._docState().isUnicodeDocument
				if not isUniDoc and ctxEnc and any(ch in "!@#$%^&*()+=~`_{}[]\\|/<>?0123456789." for ch in text):
					symRuns.append((i, text, ctxEnc))
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
		if symRuns:
			order = [r[0] for r in runs]
			texts = {r[0]: r[1] for r in runs}
			for i, text, useEnc in symRuns:
				k = order.index(i)
				near = [order[j] for j in (k - 1, k + 1) if 0 <= j < len(order)]
				if not near or any(devanagariRepair.hasDevanagari(texts[j]) for j in near):
					continue
				if all(j in convert for j in near):
					conv = legacyFonts.convert(text, useEnc)
					if conv and conv != text:
						convert[i] = (useEnc, False)
		if not convert:
			if rebuilt or (c["switchLanguage"] and any(devanagariRepair.hasDevanagari(x) for x in out if isinstance(x, str))):
				return self._withLanguage(out, rebuilt, c, unit=unit)
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
				if newText != item:
					count += len(newText.split())
					usedEnc = enc
					if switchLang:
						if unit == textInfos.UNIT_CHARACTER:
							result.append(newText)
						else:
							result.append(self._formatWithLanguage(lastFormat, legacyFonts.languageForEncoding(enc)))
							result.append(newText)
							result.append(self._formatWithLanguage(lastFormat, None, restore=True))
					else:
						result.append(newText)
					continue
			if switchLang and isinstance(item, str) and (rebuilt.get(i) or devanagariRepair.hasDevanagari(item)):
				if unit == textInfos.UNIT_CHARACTER:
					result.append(item)
					continue
				curLang = (lastFormat.get("language") or "").lower() if lastFormat else ""
				isNe = multilangIntegration.isNepaliDevanagari(item) or bool(rebuilt.get(i))
				if not curLang.startswith("ne") and (isNe or not curLang.startswith("hi")):
					result.append(self._formatWithLanguage(lastFormat, "ne"))
					result.append(item)
					result.append(self._formatWithLanguage(lastFormat, None, restore=True))
					continue
			result.append(item)
		if usedEnc and c["mode"] == "auto" and count >= 2:
			self._setContext(usedEnc)
		return result

	def _withLanguage(self, out, rebuilt, c, unit=None):
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
				if unit == textInfos.UNIT_CHARACTER:
					result.append(item)
					continue
				curLang = (lastFormat.get("language") or "").lower() if lastFormat else ""
				isNe = multilangIntegration.isNepaliDevanagari(item) or bool(rebuilt.get(i))
				if not curLang.startswith("ne") and (isNe or not curLang.startswith("hi")):
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
		if devanagariRepair.hasDevanagari(newText):
			newText = devanagariRepair.cleanShuffled(newText)
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
			# English-looking words ("eft", "ag") are still Preeti when the screen shows Devanagari
			if not (allowVisual and c["visualCheck"] and words <= 3
					and self._visualVerdict(info, joined) == visualScript.DEVANAGARI):
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
			if words == 1 and neLexicon.isLoaded() and not detector.isEnglishWord(joined.strip().strip(".,:;").lower()):
				conv_w = legacyFonts.convert(joined.strip(), used)
				if conv_w and (neLexicon.isWord(conv_w.strip(".,:;!?()[]{}")) or conv_w in (":", "५", "१", "२", "३", "४", "६", "७", "८", "९", "०")):
					for i, _t in unknown:
						convert[i] = (used, False)
					return
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
			# switch only when the other layout really reads better ("/fd ag" is Preeti राम बन)
			if any(f for _, f in alt) and self._guessEncoding(text, encoding, True) == other:
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
		ui.message(_("Nepali mode on. Turn off with NVDA+Ctrl+Shift+Space for English typing or menus.") if on else _("Nepali mode off"))

	@script(
		# Translators: input help for a command
		description=_("Copies the selection; in Nepali mode the copied text is the correct Unicode Nepali"),
		category=CATEGORY,
		gesture="kb:control+c",
	)
	def script_copyFixed(self, gesture):
		focus = api.getFocusObject()
		ti = getattr(focus, "treeInterceptor", None) if focus else None
		# 1. BROWSE MODE:
		# Always delegate directly to NVDA's native treeInterceptor copy.
		# When Nepali mode is ON, our CursorManager / TextInfo hooks will automatically convert it.
		# When Nepali mode is OFF, native NVDA browse mode copies normally without interference.
		if ti is not None and not getattr(ti, "passThrough", True):
			if hasattr(ti, "script_copyToClipboard"):
				ti.script_copyToClipboard(gesture)
				return
			gesture.send()
			return

		# 2. FOCUS MODE:
		if not isOn():
			gesture.send()
			return

		src = focus
		info = None
		if src is not None:
			try:
				info = src.makeTextInfo(textInfos.POSITION_SELECTION)
			except Exception:
				info = None
		if info is not None and not info.isCollapsed:
			raw = info.text or ""
			new = self._plainText(info)
			target = new if (new and new != raw) else raw
			if devanagariRepair.hasDevanagari(target):
				cleaned = devanagariRepair.cleanShuffled(target)
				if self._isPdfWindow(src) or devanagariRepair.isBroken(target) or self._isBrokenDoc():
					cleaned = devanagariRepair.repair(cleaned, broken=True)
				if cleaned and cleaned != raw:
					_ownCopy(textInfos.convertToCrlf(cleaned), notify=True)
					return
			if not new or new == raw:
				c = conf()
				ctxEnc = self._inContext()
				defaultEnc = ctxEnc or c["encoding"]
				if c["mode"] != "off" and not self._docState().isUnicodeDocument:
					isPdf = self._isPdfWindow(src)
					conv = detector.convertMixed(raw, lambda t: legacyFonts.convert(t, defaultEnc) or t, encoding=defaultEnc, context=bool(ctxEnc or isPdf))
					if conv and conv != raw:
						new = conv
				if c["repairUnicode"] and new and devanagariRepair.hasDevanagari(new):
					new = devanagariRepair.repair(new, broken=True if (self._isPdfWindow(src) or self._isBrokenDoc()) else None)
			if new and new != raw:
				_ownCopy(textInfos.convertToCrlf(new), notify=True)
				return
		gesture.send()
		if focus is not None:
			wx.CallLater(300, self._fixClipboard, focus)

	def _fixClipboard(self, focus):
		"""After the application copied a selection of Preeti / damaged text, put the real text on
		the clipboard instead."""
		try:
			if not isOn():
				return
			if focus is None:
				focus = api.getFocusObject()
			src = focus
			ti = getattr(focus, "treeInterceptor", None)
			if ti is not None and not getattr(ti, "passThrough", True):
				src = ti  # browse mode: the selection is in the virtual document
			clip = api.getClipData() or ""
			if not clip:
				return
			if devanagariRepair.hasDevanagari(clip):
				cleaned = devanagariRepair.cleanShuffled(clip)
				if self._isPdfWindow(src) or devanagariRepair.isBroken(clip) or self._isBrokenDoc():
					cleaned = devanagariRepair.repair(cleaned, broken=True)
				if cleaned and cleaned != clip:
					_ownCopy(textInfos.convertToCrlf(cleaned))
					return
			# what another program copied is changed only in a Preeti document or a PDF (never a
			# password, a code or an English text that merely looks like keys)
			ctxEnc = self._inContext()
			if conf()["mode"] != "off" and (ctxEnc or self._isPdfWindow(src)) and detector.looksLegacy(clip, ctxEnc or "preeti", context=True):
				enc = ctxEnc or conf()["encoding"]
				conv = detector.convertMixed(clip, lambda t: legacyFonts.convert(t, enc) or t, encoding=enc, context=True)
				if conv and conv != clip:
					_ownCopy(textInfos.convertToCrlf(conv))
		except Exception:
			log.debugWarning("Nepali Reader: could not fix the copied text", exc_info=True)

	@script(
		# Translators: input help for a command
		description=_("Cycles legacy Nepali/Hindi font reading between automatic, always convert and off"),
		category=CATEGORY,
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
		_ownCopy(result)
		ui.message(result)

	@script(
		# Translators: input help for a command
		description=_("Opens Nepali Reader settings dialog"),
		category=CATEGORY,
		gesture="kb:NVDA+control+l",
	)
	def script_openSettings(self, gesture):
		import gui
		wx.CallAfter(gui.mainFrame.popupSettingsDialog, NVDASettingsDialog, NepaliReaderSettingsPanel)




class NepaliReaderSettingsPanel(SettingsPanel):
	# Translators: title of the settings panel
	title = _("Nepali Reader")

	def makeSettings(self, settingsSizer):
		c = conf()
		helper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		# Translators: settings label
		self.enabledCheck = helper.addItem(wx.CheckBox(self, label=_("Nepali mode (NVDA+Ctrl+Shift+Space)")))
		self.enabledCheck.SetValue(isOn())
		# Translators: guidance note in settings dialog
		helper.addItem(wx.StaticText(self, label=_(
			"Recommendation: Keep Nepali mode disabled (NVDA+Ctrl+Shift+Space) when working in English documents, "
			"programming, or navigating system menus. Enable it when reading Nepali text or PDFs."
		)))
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
		self.updateCheck = helper.addItem(wx.CheckBox(self, label=_("Automatically check for updates from GitHub")))
		self.updateCheck.SetValue(c.get("autoCheckUpdate", True))

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
		c["autoCheckUpdate"] = self.updateCheck.GetValue()
		_menuSync[0]()
