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

GITHUB_REPO = "SuyogDhungel/nepaliReader"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
CHECK_INTERVAL_SECONDS = 86400  # Check once per 24 hours automatically


def parseVersion(verStr):
	"""Converts version strings like 'v1.1.6', '1.1.7-beta' into a tuple of ints (1, 1, 6)."""
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
		for addon in addonHandler.getAvailableAddons():
			if addon.name == "nepaliReader":
				return parseVersion(addon.version)
	except Exception:
		pass
	return (1, 1, 7)


def launchInstaller(destPath):
	"""Hands off the downloaded .nvda-addon package to NVDA's installation dialog."""
	try:
		import ui
		ui.message(_("Download complete. Opening add-on installation dialog..."))
	except Exception:
		pass

	launched = False
	# 1. Try NVDA's internal gui.addonGui on main thread
	try:
		import gui.addonGui
		if hasattr(gui.addonGui, "installAddon") and hasattr(addonHandler, "AddonBundle"):
			bundle = addonHandler.AddonBundle(destPath)
			gui.addonGui.installAddon(bundle)
			launched = True
	except Exception:
		launched = False

	# 2. Universal Windows file handler (triggers NVDA's native install dialog)
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

	if not launched:
		gui.messageBox(
			_("Update package downloaded to:\n{path}\n\nPlease open this file to install.").format(path=destPath),
			_("Nepali Reader Update"),
			wx.OK | wx.ICON_INFORMATION
		)


def _downloadAndInstall(url, newVerStr, progressDialog, cancelFlag):
	"""Downloads the .nvda-addon package in the background while updating the progress dialog."""
	tempDir = tempfile.gettempdir()
	destPath = os.path.join(tempDir, f"nepaliReader-{newVerStr}.nvda-addon")

	def updateDialog(pct, text):
		if cancelFlag.is_set() or not progressDialog:
			return
		try:
			res = progressDialog.Update(pct, text)
			userCancelled = False
			if hasattr(progressDialog, "WasCancelled") and progressDialog.WasCancelled():
				userCancelled = True
			elif isinstance(res, tuple) and not res[0]:
				userCancelled = True
			elif res is False:
				userCancelled = True
			if userCancelled:
				cancelFlag.set()
		except Exception:
			pass

	def updatePulse(text):
		if cancelFlag.is_set() or not progressDialog:
			return
		try:
			res = progressDialog.Pulse(text)
			userCancelled = False
			if hasattr(progressDialog, "WasCancelled") and progressDialog.WasCancelled():
				userCancelled = True
			elif isinstance(res, tuple) and not res[0]:
				userCancelled = True
			elif res is False:
				userCancelled = True
			if userCancelled:
				cancelFlag.set()
		except Exception:
			pass

	# Prefer IPv4 over IPv6 to avoid the common 21-second TCP connect timeout
	# on Windows with certain ISPs in Nepal where IPv6 routes to GitHub/AWS are dropped.
	orig_getaddrinfo = socket.getaddrinfo

	def ipv4_first_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
		try:
			res = orig_getaddrinfo(host, port, family, type, proto, flags)
			# Put AF_INET (IPv4) ahead of AF_INET6
			return sorted(res, key=lambda x: 0 if x[0] == socket.AF_INET else 1)
		except Exception:
			return orig_getaddrinfo(host, port, family, type, proto, flags)

	try:
		socket.getaddrinfo = ipv4_first_getaddrinfo
		req = urllib.request.Request(url, headers={"User-Agent": "NepaliReader-NVDA-Addon"})
		with urllib.request.urlopen(req, timeout=45) as resp:
			try:
				totalSize = int(resp.headers.get("Content-Length", 0) or 0)
			except Exception:
				totalSize = 0

			downloaded = 0
			lastPct = -1
			chunkSize = 32768  # 32 KB chunks

			with open(destPath, "wb") as f:
				while True:
					if cancelFlag.is_set():
						break
					chunk = resp.read(chunkSize)
					if not chunk:
						break
					if cancelFlag.is_set():
						break
					f.write(chunk)
					downloaded += len(chunk)

					if totalSize > 0:
						pct = int((downloaded / totalSize) * 100)
						pct = min(max(pct, 0), 99)
						if pct != lastPct:
							lastPct = pct
							msg = _("Downloading update, please wait... {pct}%").format(pct=pct)
							wx.CallAfter(updateDialog, pct, msg)
					else:
						mb = downloaded / (1024 * 1024)
						msg = _("Downloading update, please wait... {mb:.1f} MB").format(mb=mb)
						wx.CallAfter(updatePulse, msg)

					# Micro-pace streaming slightly (10ms) so NVDA can cleanly announce/beep
					# progress bar changes instead of flashing from 0% to 100% in an instant.
					time.sleep(0.01)

		if cancelFlag.is_set():
			try:
				if os.path.exists(destPath):
					os.remove(destPath)
			except Exception:
				pass

			def handleCancel():
				if progressDialog:
					try:
						progressDialog.Hide()
					except Exception:
						pass
					try:
						progressDialog.Close()
					except Exception:
						pass
					try:
						progressDialog.Destroy()
					except Exception:
						pass
				try:
					import ui
					ui.message(_("Update download cancelled."))
				except Exception:
					pass

			wx.CallAfter(handleCancel)
			return

		# Download completed successfully!
		def finish():
			if progressDialog:
				try:
					progressDialog.Hide()
				except Exception:
					pass
				try:
					progressDialog.Close()
				except Exception:
					pass
				try:
					progressDialog.Destroy()
				except Exception:
					pass

			wx.CallLater(100, launchInstaller, destPath)

		wx.CallAfter(finish)

	except Exception as e:
		log.error("Nepali Reader: update download failed", exc_info=True)
		try:
			if os.path.exists(destPath):
				os.remove(destPath)
		except Exception:
			pass

		def notifyFail(errMsg):
			if progressDialog:
				try:
					progressDialog.Hide()
				except Exception:
					pass
				try:
					progressDialog.Close()
				except Exception:
					pass
				try:
					progressDialog.Destroy()
				except Exception:
					pass
			if not cancelFlag.is_set():
				gui.messageBox(
					_("Failed to download update: {err}\nPlease check your internet connection.").format(err=errMsg),
					_("Nepali Reader Update"),
					wx.OK | wx.ICON_ERROR
				)

		wx.CallAfter(notifyFail, str(e))
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
					plainNotes = stripMarkdown(body)
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
					res = gui.messageBox(
						msg,
						_("Nepali Reader Update"),
						wx.YES_NO | wx.ICON_QUESTION
					)
					if res == wx.YES:
						progressDialog = None
						try:
							progressDialog = wx.ProgressDialog(
								_("Nepali Reader Update"),
								_("Connecting to server, please wait..."),
								maximum=100,
								parent=gui.mainFrame if (gui and hasattr(gui, "mainFrame")) else None,
								style=wx.PD_CAN_ABORT | wx.PD_AUTO_HIDE | wx.PD_SMOOTH
							)
							progressDialog.CentreOnScreen()
						except Exception as dlgErr:
							log.debugWarning("Failed to create wx.ProgressDialog: %s" % dlgErr)
							progressDialog = None

						cancelFlag = threading.Event()
						threading.Thread(
							target=_downloadAndInstall,
							args=(addonUrl, tag, progressDialog, cancelFlag),
							name="NepaliReaderDownloader",
							daemon=True
						).start()

				wx.CallAfter(promptUser)
			elif manual:
				def informCurrent():
					gui.messageBox(
						_("Nepali Reader is up to date (version {ver}).").format(ver=".".join(map(str, currentVer))),
						_("Nepali Reader Update"),
						wx.OK | wx.ICON_INFORMATION
					)
				wx.CallAfter(informCurrent)

		except Exception as e:
			log.debugWarning("Nepali Reader: update check error: %s" % e)
			if manual:
				def informError():
					gui.messageBox(
						_("Could not check for updates. Please check your internet connection."),
						_("Nepali Reader Update"),
						wx.OK | wx.ICON_WARNING
					)
				wx.CallAfter(informError)

	threading.Thread(target=worker, name="NepaliReaderUpdateCheck", daemon=True).start()


def startAutoUpdateCheck(configRef):
	"""Runs a fast, non-blocking background check on every startup and restart."""
	def delayedCheck():
		# 4-second delay so NVDA finishes loading audio and GUI smoothly
		time.sleep(4)
		try:
			checkUpdate(manual=False, configRef=configRef)
		except Exception:
			pass

	threading.Thread(target=delayedCheck, name="NepaliReaderAutoUpdate", daemon=True).start()
