# -*- coding: utf-8 -*-
# Nepali Reader GitHub Auto-Updater
# Checks GitHub releases and allows users to update directly without the NVDA Add-on Store.

import json
import os
import re
import socket
import tempfile
import threading
import time
import urllib.request

try:
	import addonHandler
	addonHandler.initTranslation()
except ImportError:
	addonHandler = None
	def _(s): return s

try:
	import gui
	import wx
except ImportError:
	gui = None
	wx = None

try:
	from logHandler import log
except ImportError:
	import logging
	log = logging.getLogger("updater")

try:
	import ui
except ImportError:
	ui = None

GITHUB_REPO = "SuyogDhungel/nepaliReader"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
CHECK_INTERVAL_SECONDS = 86400  # Check once per 24 hours automatically


def parseVersion(verStr):
	"""Converts version strings like 'v2.1.0', '2.0.9' into a tuple of ints (2, 1, 0)."""
	if not verStr:
		return (0, 0, 0)
	cleaned = verStr.lstrip("vV").strip()
	parts = re.split(r'[-+.]', cleaned)
	nums = []
	for p in parts:
		digits = re.match(r'^\d+', p)
		if digits:
			nums.append(int(digits.group(0)))
		else:
			break
	while len(nums) < 3:
		nums.append(0)
	return tuple(nums[:3])


def stripMarkdown(text):
	"""Converts GitHub Markdown release notes into clean plain text for screen readers."""
	if not text:
		return ""
	# 1. Normalize line breaks
	s = text.replace("\r\n", "\n").replace("\r", "\n")
	# 2. Remove fenced code blocks
	s = re.sub(r'```[a-zA-Z0-9_-]*\n(.*?)```', r'\1', s, flags=re.DOTALL)
	# 3. Remove inline code backticks: `code` -> code
	s = re.sub(r'`([^`]+)`', r'\1', s)
	# 4. Remove HTML tags: <br>, <b>, etc.
	s = re.sub(r'<[^>]+>', '', s)
	# 5. Remove markdown images and links: ![alt](url) -> alt, [text](url) -> text
	s = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', s)
	s = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', s)
	# 6. Remove bold/italics markers: **text**, __text__, *text*, _text_
	s = re.sub(r'\*\*([^*]+)\*\*', r'\1', s)
	s = re.sub(r'__([^_]+)__', r'\1', s)
	s = re.sub(r'\*([^*]+)\*', r'\1', s)
	s = re.sub(r'(?<!\w)_([^_]+)_(?!\w)', r'\1', s)
	# 7. Process lines: strip header hashes (### Header -> Header), standardize bullets, remove blockquotes/rules
	lines = []
	for line in s.split("\n"):
		# Skip horizontal rules
		if re.match(r'^\s*[-*_]{3,}\s*$', line):
			continue
		# Strip blockquote '>'
		line = re.sub(r'^\s*>\s*', '', line)
		# Strip leading header hashes
		line = re.sub(r'^\s*#{1,6}\s*', '', line)
		# Convert markdown bullets (- , * , + ) to a clean bullet character
		line = re.sub(r'^\s*[-*+]\s+', '• ', line)
		lines.append(line.rstrip())
	# 8. Collapse 3+ consecutive newlines to 2
	result = "\n".join(lines)
	result = re.sub(r'\n{3,}', '\n\n', result).strip()
	return result


def getCurrentVersion():
	"""Reads current installed version from addon manifest."""
	try:
		if addonHandler and hasattr(addonHandler, "getAvailableAddons"):
			for addon in addonHandler.getAvailableAddons():
				if addon.name == "nepaliReader":
					return parseVersion(addon.version)
	except Exception:
		pass
	# Fallback: read manifest.ini directly from addon directory
	try:
		manifestPath = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "manifest.ini")
		if os.path.isfile(manifestPath):
			with open(manifestPath, "r", encoding="utf-8") as f:
				for line in f:
					if line.strip().startswith("version"):
						_, val = line.split("=", 1)
						return parseVersion(val.strip())
	except Exception:
		pass
	return (2, 1, 0)


def launchInstaller(destPath):
	"""Hands off the downloaded .nvda-addon package to NVDA's installation dialog."""
	if ui:
		try:
			ui.message(_("Download complete. Opening add-on installation dialog..."))
		except Exception:
			pass

	launched = False

	# 1. Modern NVDA: gui.addonGui.installAddon(parentWindow, addonPath)
	try:
		import gui.addonGui
		if hasattr(gui.addonGui, "installAddon"):
			try:
				parent = getattr(gui, "mainFrame", None)
				gui.addonGui.installAddon(parent, destPath)
				launched = True
			except TypeError:
				# Older NVDA: installAddon(bundle)
				if addonHandler and hasattr(addonHandler, "AddonBundle"):
					bundle = addonHandler.AddonBundle(destPath)
					gui.addonGui.installAddon(bundle)
					launched = True
	except Exception:
		log.debugWarning("Nepali Reader: gui.addonGui.installAddon failed", exc_info=True)
		launched = False

	# 2. Try addonHandler.installAddonBundle
	if not launched and addonHandler:
		try:
			if hasattr(addonHandler, "installAddonBundle") and hasattr(addonHandler, "AddonBundle"):
				bundle = addonHandler.AddonBundle(destPath)
				addonHandler.installAddonBundle(bundle)
				launched = True
				if ui:
					ui.message(_("Nepali Reader updated successfully. Please restart NVDA."))
		except Exception:
			log.debugWarning("Nepali Reader: addonHandler.installAddonBundle failed", exc_info=True)
			launched = False

	# 3. Universal Windows file handler (triggers NVDA's native install dialog)
	if not launched:
		try:
			os.startfile(destPath)
			launched = True
		except Exception:
			try:
				import subprocess
				subprocess.Popen(["cmd", "/c", "start", "", destPath], shell=True)
				launched = True
			except Exception:
				pass

	# 4. Message box fallback
	if not launched and gui and wx:
		gui.messageBox(
			_("Update package downloaded to:\n{path}\n\nPlease open this file to install.").format(path=destPath),
			_("Nepali Reader Update"),
			wx.OK | wx.ICON_INFORMATION
		)


class DownloadTask:
	"""Handles downloading the update package with throttled progress updates to prevent NVDA freezes."""

	def __init__(self, url, newVerStr):
		self.url = url
		self.newVerStr = newVerStr
		self.cancelFlag = threading.Event()
		self.progressDialog = None
		self.destPath = os.path.join(tempfile.gettempdir(), f"nepaliReader-{newVerStr}.nvda-addon")
		self._lastGuiTime = 0.0
		self._lastPct = -1

	def start(self):
		"""Creates progress dialog on the main thread and launches download worker."""
		if gui and hasattr(gui, "mainFrame") and gui.mainFrame:
			try:
				gui.mainFrame.prePopup()
			except Exception:
				pass

		if wx:
			try:
				self.progressDialog = wx.ProgressDialog(
					_("Nepali Reader Update"),
					_("Connecting to server, please wait..."),
					maximum=100,
					parent=gui.mainFrame if (gui and hasattr(gui, "mainFrame")) else None,
					style=wx.PD_CAN_ABORT | wx.PD_AUTO_HIDE | wx.PD_SMOOTH
				)
				self.progressDialog.CentreOnScreen()
				self.progressDialog.Raise()
			except Exception as dlgErr:
				log.debugWarning("Nepali Reader: failed to create wx.ProgressDialog: %s" % dlgErr)
				self.progressDialog = None

		threading.Thread(
			target=self._runDownload,
			name="NR_Downloader",
			daemon=True
		).start()

	def _closeDialog(self):
		"""Closes and cleans up progress dialog safely on the main thread."""
		if self.progressDialog:
			try:
				self.progressDialog.Hide()
			except Exception:
				pass
			try:
				self.progressDialog.Destroy()
			except Exception:
				pass
			self.progressDialog = None
		if gui and hasattr(gui, "mainFrame") and gui.mainFrame and wx:
			try:
				wx.CallLater(50, gui.mainFrame.postPopup)
			except Exception:
				pass

	def _updateProgress(self, pct, text):
		"""Main thread callback for determinate progress updates."""
		if self.cancelFlag.is_set() or not self.progressDialog:
			return
		try:
			res = self.progressDialog.Update(pct, text)
			cancelled = False
			if hasattr(self.progressDialog, "WasCancelled") and self.progressDialog.WasCancelled():
				cancelled = True
			elif isinstance(res, tuple) and not res[0]:
				cancelled = True
			elif res is False:
				cancelled = True
			if cancelled:
				self.cancelFlag.set()
		except Exception:
			pass

	def _updatePulse(self, text):
		"""Main thread callback for indeterminate pulse updates."""
		if self.cancelFlag.is_set() or not self.progressDialog:
			return
		try:
			res = self.progressDialog.Pulse(text)
			cancelled = False
			if hasattr(self.progressDialog, "WasCancelled") and self.progressDialog.WasCancelled():
				cancelled = True
			elif isinstance(res, tuple) and not res[0]:
				cancelled = True
			elif res is False:
				cancelled = True
			if cancelled:
				self.cancelFlag.set()
		except Exception:
			pass

	def _runDownload(self):
		"""Background worker thread downloading the update package."""
		# Prefer IPv4 over IPv6 to avoid connection drops with ISPs in Nepal
		orig_getaddrinfo = socket.getaddrinfo

		def ipv4_first_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
			try:
				res = orig_getaddrinfo(host, port, family, type, proto, flags)
				return sorted(res, key=lambda x: 0 if x[0] == socket.AF_INET else 1)
			except Exception:
				return orig_getaddrinfo(host, port, family, type, proto, flags)

		try:
			socket.getaddrinfo = ipv4_first_getaddrinfo
			req = urllib.request.Request(self.url, headers={"User-Agent": "NepaliReader-NVDA-Addon"})
			with urllib.request.urlopen(req, timeout=30) as resp:
				try:
					totalSize = int(resp.headers.get("Content-Length", 0) or 0)
				except Exception:
					totalSize = 0

				downloaded = 0
				chunkSize = 65536  # 64 KB chunks
				lastSpokenPct = 0

				with open(self.destPath, "wb") as f:
					while True:
						if self.cancelFlag.is_set():
							break
						chunk = resp.read(chunkSize)
						if not chunk:
							break
						f.write(chunk)
						downloaded += len(chunk)

						now = time.monotonic()
						if totalSize > 0:
							pct = int((downloaded / totalSize) * 100)
							pct = min(max(pct, 0), 99)
							# Throttle GUI calls to at most 10/sec (100ms) to prevent wx event loop starvation
							if pct != self._lastPct and (now - self._lastGuiTime >= 0.1):
								self._lastPct = pct
								self._lastGuiTime = now
								msg = _("Downloading update, please wait... {pct}%").format(pct=pct)
								if wx:
									wx.CallAfter(self._updateProgress, pct, msg)

							# Announce progress milestones (25%, 50%, 75%) to screen reader users
							if pct >= lastSpokenPct + 25:
								lastSpokenPct = (pct // 25) * 25
								if ui:
									try:
										ui.message(f"{lastSpokenPct}%")
									except Exception:
										pass
						else:
							if now - self._lastGuiTime >= 0.2:
								self._lastGuiTime = now
								mb = downloaded / (1024 * 1024)
								msg = _("Downloading update, please wait... {mb:.1f} MB").format(mb=mb)
								if wx:
									wx.CallAfter(self._updatePulse, msg)

						# Yield CPU slightly to ensure speech synthesizer and NVDA review stay responsive
						time.sleep(0.005)

			if self.cancelFlag.is_set():
				try:
					if os.path.exists(self.destPath):
						os.remove(self.destPath)
				except Exception:
					pass

				def handleCancel():
					self._closeDialog()
					if ui:
						try:
							ui.message(_("Update download cancelled."))
						except Exception:
							pass

				if wx:
					wx.CallAfter(handleCancel)
				else:
					handleCancel()
				return

			# Download completed successfully!
			if not self.cancelFlag.is_set():
				if ui:
					try:
						ui.message("100%")
					except Exception:
						pass

			def finish():
				self._closeDialog()
				if wx:
					wx.CallLater(100, launchInstaller, self.destPath)
				else:
					launchInstaller(self.destPath)

			if wx:
				wx.CallAfter(finish)
			else:
				finish()

		except Exception as e:
			log.error("Nepali Reader: update download failed", exc_info=True)
			try:
				if os.path.exists(self.destPath):
					os.remove(self.destPath)
			except Exception:
				pass

			def notifyFail(errMsg):
				self._closeDialog()
				if not self.cancelFlag.is_set() and gui and wx:
					gui.messageBox(
						_("Failed to download update: {err}\nPlease check your internet connection.").format(err=errMsg),
						_("Nepali Reader Update"),
						wx.OK | wx.ICON_ERROR
					)

			if wx:
				wx.CallAfter(notifyFail, str(e))
			else:
				notifyFail(str(e))
		finally:
			socket.getaddrinfo = orig_getaddrinfo


def checkUpdate(manual=False, configRef=None):
	"""Checks GitHub API for new releases in a background worker thread."""
	def worker():
		try:
			req = urllib.request.Request(
				API_URL,
				headers={
					"User-Agent": "NepaliReader-NVDA-Addon",
					"Accept": "application/vnd.github.v3+json"
				}
			)
			with urllib.request.urlopen(req, timeout=10) as resp:
				data = json.loads(resp.read().decode("utf-8"))

			if configRef is not None:
				configRef["lastUpdateCheck"] = time.time()

			tag = data.get("tag_name", "")
			body = (data.get("body", "") or "").strip()
			remoteVer = parseVersion(tag)
			currentVer = getCurrentVersion()

			addonUrl = None
			for asset in data.get("assets", []):
				name = asset.get("name", "")
				if name.endswith(".nvda-addon"):
					addonUrl = asset.get("browser_download_url")
					break

			if remoteVer > currentVer and addonUrl:
				def promptUser():
					plainNotes = stripMarkdown(body).strip()
					notes = plainNotes[:800] + ("..." if len(plainNotes) > 800 else "")
					msg = _(
						"An update for Nepali Reader is available!\n\n"
						"Installed Version: {cur}\n"
						"Latest Version: {new}\n\n"
						"Release Notes:\n{notes}\n\n"
						"Do you want to download and install this update now?"
					).format(
						cur=".".join(map(str, currentVer)),
						new=tag,
						notes=notes if notes else _("Bug fixes and improvements")
					)
					if gui and wx:
						res = gui.messageBox(
							msg,
							_("Nepali Reader Update"),
							wx.YES_NO | wx.ICON_QUESTION
						)
						if res == wx.YES:
							task = DownloadTask(addonUrl, tag)
							task.start()
					elif ui:
						ui.message(_("An update for Nepali Reader is available: {new}").format(new=tag))

				if wx:
					wx.CallAfter(promptUser)
				else:
					promptUser()
			elif manual:
				def informCurrent():
					if gui and wx:
						gui.messageBox(
							_("Nepali Reader is up to date (version {ver}).").format(ver=".".join(map(str, currentVer))),
							_("Nepali Reader Update"),
							wx.OK | wx.ICON_INFORMATION
						)
					elif ui:
						ui.message(_("Nepali Reader is up to date (version {ver}).").format(ver=".".join(map(str, currentVer))))

				if wx:
					wx.CallAfter(informCurrent)
				else:
					informCurrent()

		except Exception as e:
			log.debugWarning("Nepali Reader: update check error: %s" % e)
			if manual:
				def informError():
					if gui and wx:
						gui.messageBox(
							_("Could not check for updates. Please check your internet connection."),
							_("Nepali Reader Update"),
							wx.OK | wx.ICON_WARNING
						)
					elif ui:
						ui.message(_("Could not check for updates. Please check your internet connection."))

				if wx:
					wx.CallAfter(informError)
				else:
					informError()

	threading.Thread(target=worker, name="NR_UpdateCheck", daemon=True).start()


def startAutoUpdateCheck(configRef):
	"""Runs a fast, non-blocking background check on every startup and restart."""
	def delayedCheck():
		# 5-second delay so NVDA finishes loading audio and GUI smoothly
		time.sleep(5)
		try:
			now = time.time()
			last = configRef.get("lastUpdateCheck", 0.0) if configRef else 0.0
			if now - last >= CHECK_INTERVAL_SECONDS:
				checkUpdate(manual=False, configRef=configRef)
		except Exception:
			pass

	threading.Thread(target=delayedCheck, name="NR_AutoUpdate", daemon=True).start()
