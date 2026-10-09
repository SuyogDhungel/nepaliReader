# -*- coding: utf-8 -*-
# Nepali Reader for NVDA - MultiLang Add-on Integration
# Ensures MultiLang (and any supporting NVDA TTS engine like Hear2ReadNG, eSpeak NG, SAPI5, OneCore)
# seamlessly detects and speaks Nepali across PDFs, Word documents, web pages, and edit controls.

import os
import re
import sys
import unicodedata
from io import StringIO
from collections import OrderedDict

try:
	from logHandler import log
except ImportError:
	import logging
	log = logging.getLogger(__name__)

try:
	from speech.commands import LangChangeCommand
except ImportError:
	class LangChangeCommand:
		def __init__(self, lang):
			self.lang = lang
		def __repr__(self):
			return f"LangChangeCommand({self.lang!r})"
try:
	from . import devanagariRepair, neLexicon
except (ImportError, ValueError):
	import devanagariRepair, neLexicon

# Signature Nepali markers that distinguish Nepali from Hindi
_NEPALI_SPECIFIC_WORDS = frozenset({
	"र", "पनि", "छ", "छन्", "छैन", "छैनन्", "थियो", "थिए", "भएको", "भएका", "भएकी",
	"गरेको", "गरेका", "गर्न", "गरी", "गर्छ", "गर्छन्", "गर्दछ", "गर्दछन्", "भने",
	"हुने", "रहेको", "रहेका", "रहेकी", "लागि", "भन्नाले", "बमोजिम", "तथा", "यस",
	"यसको", "यसका", "यसले", "उनको", "उनले", "हाम्रो", "हाम्रा", "हामी", "तपाईं",
	"हुन्", "हुन्छ", "हुँदैन", "भयो", "गयो", "किनभने", "त्यस", "त्यसको", "त्यसैले",
	"कुनै", "पुरै", "पहिलो", "दोस्रो", "तेस्रो", "नेपाल", "सरकार", "केन्द्र",
	"पाठ्यक्रम", "विकास", "सानोठिमी", "भक्तपुर", "शिक्षा", "विज्ञान", "प्रविधि",
	"मन्त्रालय", "कक्षा", "अध्ययन", "जीवनोपयोगी", "ऐन", "नियम", "दफा", "उपधारा",
})

_HINDI_SPECIFIC_WORDS = frozenset({
	"है", "हैं", "था", "थी", "थे", "थीं", "और", "भी", "से", "में", "पर", "लिए", "किया", "होगा", "होगी",
	"करना", "रहा", "रही", "रहे", "बहुत", "भारत", "यह", "वह", "इस", "उस", "का", "के", "की",
	"उसने", "इसने", "उन्होंने", "इन्होंने", "मैंने", "तुमने", "आपका", "आपके", "आपकी", "लिया", "दिया",
	"गया", "गई", "गए", "जाता", "जाती", "जाते", "नहीं", "वाले", "वाली", "वाला", "किसी", "कुछ",
	"कैसे", "ऐसे", "जैसे", "वैसे", "बातें", "होगी", "होंगे",
})


def isNepaliDevanagari(text):
	"""Returns True if the Devanagari text is Nepali rather than Hindi."""
	if not text or not devanagariRepair.hasDevanagari(text):
		return False
	# Strip punctuation including Devanagari danda / purna viram
	raw_words = text.split()
	words = [re.sub(r'^[^\u0900-\u097f]+|[^\u0900-\u097f]+$', '', w).strip('।,;:!?()[]{}"\'“”‘’•–—…') for w in raw_words]
	words = [w for w in words if w]
	if not words:
		return False
	ne_hits = 0
	hi_hits = 0
	extra_hindi = getattr(neLexicon, "_EXTRA", frozenset())
	stems_nepali = getattr(neLexicon, "_STEMS", {})
	for w in words:
		if w in _NEPALI_SPECIFIC_WORDS:
			ne_hits += 3
		elif w.endswith(("हरूको", "हरूमा", "हरूले", "हरू", "हरु", "बाट", "देखि", "सम्म", "लाई", "मै", "कै")):
			ne_hits += 2
		elif w.endswith("ले") and len(w) >= 3 and w not in ("पहले", "अकेले", "भले", "गले", "वाले", "निचले"):
			ne_hits += 2
		elif w in stems_nepali or w in getattr(neLexicon, "_COMMON_NEPALI", ()) or w in getattr(neLexicon, "_NAMES", ()):
			ne_hits += 1

		if w in _HINDI_SPECIFIC_WORDS:
			hi_hits += 3
		elif w in extra_hindi and w not in stems_nepali:
			hi_hits += 2

	if ne_hits > hi_hits:
		return True
	if hi_hits > ne_hits:
		return False
	# Default within Nepali Reader: Devanagari text is treated as Nepali unless predominantly Hindi
	return True


def findNepaliVoice(synth):
	"""Locates a Nepali voice ID on the given synthesizer driver if supported."""
	if not synth or not synth.isSupported("voice"):
		return None
	voices = getattr(synth, "availableVoices", None)
	if not voices:
		return None
	# 1. Direct language code match (ne, ne-NP, ne_NP)
	for vid, v in voices.items():
		vlang = (getattr(v, "language", "") or "").lower().replace("_", "-")
		if vlang.startswith("ne"):
			return vid
	# 2. Check voice ID or display name
	for vid, v in voices.items():
		vname = (getattr(v, "name", "") or getattr(v, "displayName", "") or "").lower()
		vid_str = str(vid).lower()
		if "nepali" in vname or vid_str.startswith("ne-") or vid_str == "ne" or "ne_np" in vid_str:
			return vid
	return None


def findBestNepaliSynth():
	"""Returns the best available synthesizer driver name with Nepali voice support in NVDA."""
	try:
		import synthDriverHandler
		synth_list = [sid for sid, _ in synthDriverHandler.getSynthList()]
		# Prefer Hear2ReadNG if installed (high quality Indic neural voice)
		if "Hear2ReadNG" in synth_list:
			return "Hear2ReadNG"
		# Fall back to eSpeak NG (standard across all NVDA installations)
		if "espeak" in synth_list:
			return "espeak"
	except Exception:
		pass
	return "espeak"


_orig_addDetectedLanguageCommands = None
_orig_getSynth = None
_installed = False


def _active():
	"""False while Nepali mode is switched off: the hooks below then do exactly what MultiLang does without us."""
	try:
		from . import isOn
		return bool(isOn())
	except Exception:
		return True


def install():
	"""Hooks MultiLang if installed or active so Nepali language and TTS voices are properly handled."""
	global _installed, _orig_addDetectedLanguageCommands, _orig_getSynth
	if _installed:
		return True

	try:
		# Check if MultiLang synthesizer driver module exists in NVDA
		import synthDrivers
		ml_mod = None
		try:
			import synthDrivers.MultiLang as ml_mod
		except ImportError:
			pass

		if ml_mod is None:
			return False

		ld = getattr(ml_mod, "languageDetection", None)
		if ld is not None and hasattr(ld, "addDetectedLanguageCommands"):
			if _orig_addDetectedLanguageCommands is None:
				_orig_addDetectedLanguageCommands = ld.addDetectedLanguageCommands

				def nepali_addDetectedLanguageCommands(speechSequence, defaultLang, scriptSettings, ignoreNumbersInLanguageDetection):
					"""Drop-in patch for MultiLang's script detection:
					1. Preserves explicit 'ne' language tags without clobbering to 'hi'.
					2. Detects Devanagari text as Nepali whenever it contains Nepali vocabulary.
					3. Prevents Devanagari numbers from being forced to English.
					"""
					if not _active():
						yield from _orig_addDetectedLanguageCommands(speechSequence, defaultLang, scriptSettings, ignoreNumbersInLanguageDetection)
						return
					curScript = None
					curLang = defaultLang
					scripts_dict = getattr(ld, "SCRIPTS", {})
					devanagari_langs = getattr(ld, "DEVANAGARI", ("hi", "sa", "mr", "ne"))

					for command in speechSequence:
						if isinstance(command, LangChangeCommand):
							if command.lang is None:
								curLang = defaultLang
							elif command.lang.startswith("ne"):
								curLang = "ne"
							else:
								curLang = command.lang
							curScript = None
						elif isinstance(command, str):
							sb = StringIO()
							is_ne = isNepaliDevanagari(command)
							for c in command:
								newScript = scripts_dict.get(ord(c))
								newLang = curLang
								if newScript == "Common":
									cat = unicodedata.category(c)
									if cat.startswith("N"):
										# Keep numbers attached to Nepali text in Nepali!
										if 0x0966 <= ord(c) <= 0x096F or curLang == "ne":
											newLang = curLang
										elif not ignoreNumbersInLanguageDetection:
											newLang = defaultLang
									else:
										newScript = None
								elif newScript is not None and newScript != curScript:
									if newScript == "Devanagari":
										if curLang in ("ne", "hi", "mr", "sa"):
											newLang = curLang
										elif is_ne or getattr(scriptSettings, "Devanagari", "") == "ne":
											newLang = "ne"
										else:
											newLang = getattr(scriptSettings, newScript, curLang)
									else:
										newLang = getattr(scriptSettings, newScript, curLang)

								if curLang != newLang:
									if curScript is not None and sb.tell() > 0:
										yield LangChangeCommand(curLang)
										yield sb.getvalue()
										sb = StringIO()
									curLang = newLang
								if newScript is not None:
									curScript = newScript
								sb.write(c)

							if sb.tell() > 0:
								yield LangChangeCommand(curLang)
								yield sb.getvalue()
						else:
							yield command

				ld.addDetectedLanguageCommands = nepali_addDetectedLanguageCommands
				log.info("Nepali Reader: Successfully hooked MultiLang languageDetection for Nepali support")

		# Patch MultiLang SynthDriver._getSynth
		driver_cls = getattr(ml_mod, "SynthDriver", None)
		if driver_cls is not None and hasattr(driver_cls, "_getSynth"):
			if _orig_getSynth is None:
				_orig_getSynth = driver_cls._getSynth

				def nepali_getSynth(self, lang):
					"""Ensures that when MultiLang switches to Nepali ('ne'),
					the selected synthesizer is set to its Nepali voice rather than defaulting to English."""
					if not _active():
						return _orig_getSynth(self, lang)
					if lang and lang.startswith("ne"):
						settings = getattr(self, "_settings", {}).get(lang)
						synth = None
						if settings is not None:
							try:
								synth = _orig_getSynth(self, lang)
							except Exception:
								synth = None

						# If synth has no Nepali capability (e.g. default Eloquence or SAPI5):
						cur_has_ne = False
						if synth is not None and synth.isSupported("voice"):
							cur_voice = getattr(synth, "voice", "")
							vlang = ""
							if cur_voice and getattr(synth, "availableVoices", None) and cur_voice in synth.availableVoices:
								vlang = (getattr(synth.availableVoices[cur_voice], "language", "") or "").lower()
							if vlang.startswith("ne") or findNepaliVoice(synth):
								cur_has_ne = True

						if not cur_has_ne:
							# Look for a synthesizer in MultiLang or NVDA that actually supports Nepali
							best_driver_name = findBestNepaliSynth()
							alt_synth = None
							synths_dict = getattr(self, "_synths", None)
							if synths_dict is not None:
								if best_driver_name in synths_dict:
									alt_synth = synths_dict[best_driver_name]
								elif "espeak" in synths_dict:
									alt_synth = synths_dict["espeak"]
								elif "Hear2ReadNG" in synths_dict:
									alt_synth = synths_dict["Hear2ReadNG"]

								if alt_synth is None:
									# Dynamically initialize eSpeak / Hear2Read into MultiLang's synths pool
									try:
										import synthDriverHandler
										for s_name in (best_driver_name, "Hear2ReadNG", "espeak"):
											try:
												drv = synthDriverHandler.getSynthDriver(s_name)
												if drv:
													synths_dict[s_name] = drv
													alt_synth = drv
													log.info("Nepali Reader: Initialized %s into MultiLang synth pool" % s_name)
													break
											except Exception:
												continue
									except Exception:
										pass
							if alt_synth is not None:
								synth = alt_synth

						if synth is None:
							try:
								synth = _orig_getSynth(self, lang)
							except Exception:
								synth = getattr(self, "_defaultSynth", None)

						if synth is not None and (settings is None or getattr(settings, "profile", None) is None) and synth.isSupported("voice"):
							cur_voice = getattr(synth, "voice", "")
							vlang = ""
							if cur_voice and getattr(synth, "availableVoices", None) and cur_voice in synth.availableVoices:
								vlang = (getattr(synth.availableVoices[cur_voice], "language", "") or "").lower()
							if not vlang.startswith("ne"):
								ne_voice = findNepaliVoice(synth)
								if ne_voice:
									try:
										synth.voice = ne_voice
										log.debug("Nepali Reader: Set MultiLang synth %s voice to Nepali: %s" % (synth.name, ne_voice))
									except Exception:
										pass
						return synth
					return _orig_getSynth(self, lang)

				driver_cls._getSynth = nepali_getSynth
				log.info("Nepali Reader: Successfully hooked MultiLang SynthDriver._getSynth for Nepali voice routing")

		# Auto-configure MultiLang settings if present in NVDA configuration
		try:
			import config
			if "speech" in config.conf and "MultiLang" in config.conf["speech"]:
				ml_conf = config.conf["speech"]["MultiLang"]
				changed = False
				if ml_conf.get("devanagariVoice") != "ne":
					ml_conf["devanagariVoice"] = "ne"
					changed = True
				# Check language settings
				if "languages" in ml_conf:
					langs = ml_conf["languages"]
					if "ne" not in langs or not (isinstance(langs.get("ne"), dict) and langs["ne"].get("synth")):
						best_synth = findBestNepaliSynth()
						langs["ne"] = {"synth": best_synth, "profile": None, "sendLang": True}
						changed = True
				if changed:
					try:
						config.conf.save()
					except Exception:
						pass
					log.info("Nepali Reader: Auto-configured MultiLang speech settings for Nepali and saved config")
		except Exception:
			pass

		_installed = True
		return True
	except Exception:
		log.debugWarning("Nepali Reader: Could not install MultiLang integration", exc_info=True)
		return False
