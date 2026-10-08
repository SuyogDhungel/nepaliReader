# -*- coding: utf-8 -*-
# Nepali Reader GitHub Auto-Updater
# Checks GitHub releases and allows users to update directly without the NVDA Add-on Store.

import json
import os
import re
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


def getCurrentVersion():
	"""Reads current installed version from addon manifest."""
	try:
		for addon in addonHandler.getAvailableAddons():
			if addon.name == "nepaliReader":
				return parseVersion(addon.version)
	except Exception:
		pass
	return (1, 1, 7)


def _downloadAndInstall(url, newVerStr):
	"""Downloads the .nvda-addon package and triggers NVDA's installer."""
	try:
		progressDialog = wx.ProgressDialog(
			_("Updating Nepali Reader"),
			_("Downloading Nepali Reader {version}...").format(version=newVerStr),
			maximum=100,
			parent=gui.mainFrame,
			style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
		)
	except Exception:
		progressDialog = None

	try:
		req = urllib.request.Request(url, headers={"User-Agent": "NepaliReader-NVDA-Addon"})
		with urllib.request.urlopen(req, timeout=30) as resp:
			totalSize = int(resp.headers.get("Content-Length", 0))
			downloaded = 0
			tempFile = tempfile.NamedTemporaryFile(suffix=".nvda-addon", delete=False)
			try:
				blockSize = 8192
				while True:
					chunk = resp.read(blockSize)
					if not chunk:
						break
					tempFile.write(chunk)
					downloaded += len(chunk)
					if progressDialog and totalSize > 0:
						pct = min(99, int((downloaded / totalSize) * 100))
						wx.CallAfter(progressDialog.Update, pct)
				tempFile.flush()
				tempFile.close()
			finally:
				if progressDialog:
					wx.CallAfter(progressDialog.Destroy)

			def installOnMainThread():
				try:
					if hasattr(addonHandler, "installAddonPackage"):
						addonHandler.installAddonPackage(tempFile.name)
					elif hasattr(addonHandler, "installAddon"):
						addonHandler.installAddon(tempFile.name)
				except Exception:
					log.error("Nepali Reader: installation failed", exc_info=True)
					gui.messageBox(
						_("Could not install update package. Please try downloading manually from GitHub."),
						_("Nepali Reader Update"),
						wx.OK | wx.ICON_ERROR
					)
				finally:
					try:
						os.remove(tempFile.name)
					except Exception:
						pass

			wx.CallAfter(installOnMainThread)
	except Exception as e:
		if progressDialog:
			try:
				wx.CallAfter(progressDialog.Destroy)
			except Exception:
				pass
		log.error("Nepali Reader: update download failed", exc_info=True)
		def notifyFail():
			gui.messageBox(
				_("Failed to download update: {err}").format(err=str(e)),
				_("Nepali Reader Update"),
				wx.OK | wx.ICON_ERROR
			)
		wx.CallAfter(notifyFail)


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
			with urllib.request.urlopen(req, timeout=12) as resp:
				data = json.loads(resp.read().decode("utf-8"))

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
					notes = body[:600] + ("..." if len(body) > 600 else "")
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
						threading.Thread(
							target=_downloadAndInstall,
							args=(addonUrl, tag),
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
	"""Runs a delayed background check on startup once per day."""
	def delayedCheck():
		time.sleep(12)  # Delay so NVDA finishes loading without any interruption
		try:
			now = time.time()
			last = configRef.get("lastUpdateCheck", 0.0)
			if now - last >= CHECK_INTERVAL_SECONDS:
				configRef["lastUpdateCheck"] = now
				checkUpdate(manual=False, configRef=configRef)
		except Exception:
			pass

	threading.Thread(target=delayedCheck, name="NepaliReaderAutoUpdate", daemon=True).start()
