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
CHANGELOG_URL = "https://raw.githubusercontent.com/" + GITHUB_REPO + "/{tag}/CHANGELOG.md"
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
		# Tables: the |---| row goes, a row's cells are read one after the other
		if re.match(r'^\s*\|?[\s:|-]+\|[\s:|-]*$', line) and '-' in line:
			continue
		if line.strip().startswith('|'):
			cells = [c.strip() for c in line.strip().strip('|').split('|')]
			line = ', '.join(c for c in cells if c)
		lines.append(line.rstrip())
	# 8. Collapse 3+ consecutive newlines to 2
	result = "\n".join(lines)
	result = re.sub(r'\n{3,}', '\n\n', result).strip()
	return result


def changelogSince(text, currentVer, newVer):
	"""The sections of CHANGELOG.md for the versions after the installed one, up to the new one
	(what changes for this user), newest first as the file has them."""
	if not text:
		return ""
	out = []
	keep = False
	for line in text.replace("\r\n", "\n").split("\n"):
		m = re.match(r'^##\s+\[?v?(\d+(?:\.\d+)*)', line)
		if m:
			v = parseVersion(m.group(1))
			keep = currentVer < v <= newVer
		elif re.match(r'^#\s', line):
			keep = False
		if keep:
			out.append(line)
	return "\n".join(out).strip()


def fetchChangelog(tag, currentVer, newVer):
	"""What changed since the installed version, from the CHANGELOG.md of the new release ("" when
	it cannot be had)."""
	try:
		req = urllib.request.Request(CHANGELOG_URL.format(tag=tag), headers={"User-Agent": "NepaliReader-NVDA-Addon"})
		with urllib.request.urlopen(req, timeout=10) as resp:
			text = resp.read().decode("utf-8", "replace")
		return changelogSince(text, currentVer, newVer)
	except Exception as e:
		log.debugWarning("Nepali Reader: could not read the changelog: %s" % e)
		return ""


def releaseNotes(body, changelog):
	"""The text shown before updating: the changes since the installed version (CHANGELOG.md),
	or the release notes when the changelog cannot be had."""
	notes = stripMarkdown(changelog).strip() if changelog else ""
	if notes:
		# "## [2.2.0] - 2026-11-25" reads "Version 2.2.0 - 2026-11-25"
		notes = re.sub(r'^\[(\d+(?:\.\d+)*)\]', lambda m: _("Version {v}").format(v=m.group(1)), notes, flags=re.M)
	else:
		notes = stripMarkdown(body).strip()
	return notes


def checkPackage(path, expectedSize=0):
	"""None if the downloaded file is a whole Nepali Reader add-on package, else what is wrong."""
	import zipfile
	try:
		size = os.path.getsize(path)
	except OSError:
		return _("the downloaded file is missing")
	if size == 0:
		return _("the download is empty")
	if expectedSize and size != expectedSize:
		return _("the download is incomplete ({got} of {want} bytes)").format(got=size, want=expectedSize)
	try:
		with zipfile.ZipFile(path) as z:
			manifest = z.read("manifest.ini").decode("utf-8", "replace")
	except Exception:
		return _("the downloaded file is not an NVDA add-on package")
	if not re.search(r'^\s*name\s*=\s*"?nepaliReader"?\s*$', manifest, re.M):
		return _("the downloaded package is not Nepali Reader")
	return None


if wx is not None:
	class UpdateDialog(wx.Dialog):
		"""Asks before updating, with everything that changed in a text box that can be read line by
		line with the arrow keys (a message box reads it all at once, cut short)."""

		def __init__(self, parent, curStr, newStr, notes):
			super().__init__(parent, title=_("Nepali Reader Update"))
			sizer = wx.BoxSizer(wx.VERTICAL)
			intro = wx.StaticText(self, label=_("Nepali Reader {new} is available. You have version {cur}.").format(new=newStr, cur=curStr))
			sizer.Add(intro, 0, wx.ALL, 10)
			sizer.Add(wx.StaticText(self, label=_("&What's new:")), 0, wx.LEFT | wx.RIGHT, 10)
			self.notes = wx.TextCtrl(self, value=notes, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(600, 340))
			sizer.Add(self.notes, 1, wx.EXPAND | wx.ALL, 10)
			buttons = wx.BoxSizer(wx.HORIZONTAL)
			self.updateButton = wx.Button(self, wx.ID_OK, _("&Update now"))
			buttons.Add(self.updateButton, 0, wx.ALL, 5)
			buttons.Add(wx.Button(self, wx.ID_CANCEL, _("&Later")), 0, wx.ALL, 5)
			sizer.Add(buttons, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
			self.SetSizerAndFit(sizer)
			self.updateButton.SetDefault()
			self.notes.SetInsertionPoint(0)
			self.notes.SetFocus()
			self.CentreOnScreen()


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

	# 1. NVDA's own way of installing an add-on file: asks to install (or update), installs, then
	# offers the restart the new version needs
	try:
		import gui.addonGui
		if hasattr(gui.addonGui, "handleRemoteAddonInstall"):
			gui.addonGui.handleRemoteAddonInstall(destPath)
			launched = True
	except Exception:
		log.debugWarning("Nepali Reader: gui.addonGui.handleRemoteAddonInstall failed", exc_info=True)
		launched = False

	# 2. Older NVDA: gui.addonGui.installAddon(parentWindow, addonPath), then the restart prompt
	try:
		import gui.addonGui
		if not launched and hasattr(gui.addonGui, "installAddon"):
			try:
				parent = getattr(gui, "mainFrame", None)
				if gui.addonGui.installAddon(parent, destPath):
					if hasattr(gui.addonGui, "promptUserForRestart") and wx:
						wx.CallAfter(gui.addonGui.promptUserForRestart)
				launched = True
			except TypeError:
				# Older NVDA: installAddon(bundle)
				if addonHandler and hasattr(addonHandler, "AddonBundle"):
					bundle = addonHandler.AddonBundle(destPath)
					gui.addonGui.installAddon(bundle)
					launched = True
	except Exception:
		log.debugWarning("Nepali Reader: gui.addonGui.installAddon failed", exc_info=True)

	# 3. Try addonHandler.installAddonBundle
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

	# 4. Universal Windows file handler (triggers NVDA's native install dialog)
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

	# 5. Message box fallback
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
		self.expectedSize = 0

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
				self.expectedSize = totalSize

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

			# a connection that drops can end the download early without an error: only a whole
			# add-on package is installed
			problem = checkPackage(self.destPath, self.expectedSize)
			if problem:
				raise IOError(problem)

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
				def noteChecked(when=time.time()):
					try:
						configRef["lastUpdateCheck"] = when
					except Exception:
						pass
				# (NVDA's configuration is changed on its main thread only)
				if wx:
					wx.CallAfter(noteChecked)
				else:
					noteChecked()

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
				# everything that changed since the installed version (CHANGELOG.md of the new release),
				# read here in the background thread
				notes = releaseNotes(body, fetchChangelog(tag, currentVer, remoteVer)) or _("Bug fixes and improvements")

				def promptUser():
					curStr = ".".join(map(str, currentVer))
					if gui and wx:
						res = None
						try:
							gui.mainFrame.prePopup()
							try:
								dlg = UpdateDialog(gui.mainFrame, curStr, tag, notes)
								res = dlg.ShowModal()
								dlg.Destroy()
							finally:
								gui.mainFrame.postPopup()
							update = res == wx.ID_OK
						except Exception:
							log.debugWarning("Nepali Reader: update dialog failed", exc_info=True)
							short = notes[:800] + ("..." if len(notes) > 800 else "")
							update = gui.messageBox(
								_(
									"An update for Nepali Reader is available!\n\n"
									"Installed Version: {cur}\n"
									"Latest Version: {new}\n\n"
									"Release Notes:\n{notes}\n\n"
									"Do you want to download and install this update now?"
								).format(cur=curStr, new=tag, notes=short),
								_("Nepali Reader Update"),
								wx.YES_NO | wx.ICON_QUESTION
							) == wx.YES
						if update:
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
