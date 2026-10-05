# -*- coding: utf-8 -*-
# Nepali Reader for NVDA - offline OCR with Tesseract (Nepali, Hindi, English).
# The engine-level helpers here have no NVDA dependencies; the NVDA recognizer
# class is created lazily by makeRecognizerClass() so this file can be tested alone.

import os
import struct
import subprocess
import tempfile
import threading
import unicodedata

ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
TESSDATA_DIR = os.path.join(ADDON_DIR, "tessdata")

_CANDIDATES = [
	os.path.join(ADDON_DIR, "tesseract", "tesseract.exe"),
	r"C:\Program Files\Tesseract-OCR\tesseract.exe",
	r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
	os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
	os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe"),
]


def findTesseract(customPath=""):
	paths = ([customPath] if customPath else []) + _CANDIDATES
	for p in paths:
		if p and os.path.isfile(p):
			return p
	for d in os.environ.get("PATH", "").split(os.pathsep):
		for name in ("tesseract.exe", "tesseract"):
			p = os.path.join(d, name)
			if os.path.isfile(p):
				return p
	return None


def bgraToBmp(raw, width, height):
	"""Encode top-down BGRA pixels as a 24-bit bottom-up BMP (the most widely supported form)."""
	raw = bytes(raw)
	srcRow = width * 4
	dstRow = (width * 3 + 3) & ~3
	pad = b"\x00" * (dstRow - width * 3)
	rows = []
	for y in range(height - 1, -1, -1):
		row = raw[y * srcRow:(y + 1) * srcRow]
		# drop every 4th byte (alpha): keep B, G, R
		bgr = bytearray(width * 3)
		bgr[0::3] = row[0::4]
		bgr[1::3] = row[1::4]
		bgr[2::3] = row[2::4]
		rows.append(bytes(bgr) + pad)
	imageSize = dstRow * height
	header = struct.pack("<2sIHHI", b"BM", 54 + imageSize, 0, 0, 54)
	info = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 24, 0, imageSize, 2835, 2835, 0, 0)
	return header + info + b"".join(rows)


def parseTsv(tsv, scale=1.0):
	"""Turn Tesseract TSV output into NVDA's lines/words structure."""
	lines = {}
	order = []
	for row in tsv.splitlines()[1:]:
		cols = row.split("\t")
		if len(cols) < 12 or cols[0] != "5":
			continue
		text = cols[11].strip()
		if not text:
			continue
		key = (int(cols[2]), int(cols[3]), int(cols[4]))  # block, paragraph, line
		if key not in lines:
			lines[key] = []
			order.append(key)
		lines[key].append({
			"x": int(int(cols[6]) / scale), "y": int(int(cols[7]) / scale),
			"width": max(1, int(int(cols[8]) / scale)), "height": max(1, int(int(cols[9]) / scale)),
			"text": unicodedata.normalize("NFC", text),
		})
	result = []
	for key in order:
		words = lines[key]
		# LinesWordsResult joins words with spaces itself; add line breaks between lines
		result.append(words)
	return result


def runTesseract(exe, imagePath, languages="nep+hin+eng", psm=3, timeout=120):
	args = [exe, imagePath, "stdout", "-l", languages, "--psm", str(psm), "-c", "tessedit_create_tsv=1"]
	if os.path.isdir(TESSDATA_DIR):
		args[1:1] = ["--tessdata-dir", TESSDATA_DIR]
	startupinfo = None
	creationflags = 0
	if os.name == "nt":
		startupinfo = subprocess.STARTUPINFO()
		startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
		creationflags = 0x08000000  # CREATE_NO_WINDOW
	proc = subprocess.run(
		args, capture_output=True, timeout=timeout,
		startupinfo=startupinfo, creationflags=creationflags,
	)
	if proc.returncode != 0:
		raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip() or "Tesseract failed")
	return proc.stdout.decode("utf-8", "replace")


def recognizeBgra(exe, raw, width, height, languages="nep+hin+eng"):
	fd, path = tempfile.mkstemp(suffix=".bmp", prefix="nvdaNepaliOcr_")
	try:
		with os.fdopen(fd, "wb") as f:
			f.write(bgraToBmp(raw, width, height))
		return parseTsv(runTesseract(exe, path, languages))
	finally:
		try:
			os.remove(path)
		except OSError:
			pass


def makeRecognizerClass():
	"""Build the NVDA ContentRecognizer subclass (imports NVDA modules)."""
	import ctypes
	from contentRecog import ContentRecognizer, LinesWordsResult
	from logHandler import log

	class TesseractRecognizer(ContentRecognizer):
		allowAutoRefresh = False

		def __init__(self, exe, languages):
			super().__init__()
			self.exe = exe
			self.languages = languages
			self._cancelled = False

		def getResizeFactor(self, width, height):
			# tested: 1x and 2x give the same accuracy on 13-20px screen text; enlarge only small objects
			return 2 if (width < 600 or height < 200) else 1

		def recognize(self, pixels, imageInfo, onResult):
			self._cancelled = False
			w, h = imageInfo.recogWidth, imageInfo.recogHeight
			raw = ctypes.string_at(ctypes.addressof(pixels), w * h * 4)

			def work():
				try:
					data = recognizeBgra(self.exe, raw, w, h, self.languages)
					if self._cancelled:
						return
					if not data:
						onResult(RuntimeError("No text found"))
						return
					onResult(LinesWordsResult(data, imageInfo))
				except Exception as e:  # noqa: BLE001
					log.error("Nepali Reader OCR failed", exc_info=True)
					if not self._cancelled:
						onResult(e)

			threading.Thread(target=work, name="NepaliReaderOCR", daemon=True).start()

		def cancel(self):
			self._cancelled = True

	return TesseractRecognizer
