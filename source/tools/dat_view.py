# Turns the add-on's .dat files into files you can open in Notepad.
# The .dat files are plain text or JSON, compressed with zlib (so the add-on stays small and loads
# them fast). Word lists become .txt (one word per line); nepaliWords.dat and glyphRefs.dat
# become .json.
#
#   python dat_view.py                 (every .dat file of the add-on, into a "dat_readable" folder)
#   python dat_view.py file.dat [...]  (only these)
import json
import os
import sys
import zlib

here = os.path.dirname(os.path.abspath(__file__))
addon = os.path.join(here, "..", "addon", "globalPlugins", "nepaliReader")
files = sys.argv[1:] or sorted(os.path.join(addon, n) for n in os.listdir(addon) if n.endswith(".dat"))
out = os.path.join(os.getcwd(), "dat_readable")
os.makedirs(out, exist_ok=True)
for path in files:
	text = zlib.decompress(open(path, "rb").read()).decode("utf-8")
	name = os.path.splitext(os.path.basename(path))[0]
	if text.lstrip().startswith("{"):
		target = os.path.join(out, name + ".json")
		with open(target, "w", encoding="utf-8") as f:
			json.dump(json.loads(text), f, ensure_ascii=False, indent=1)
	else:
		target = os.path.join(out, name + ".txt")
		with open(target, "w", encoding="utf-8") as f:
			f.write(text)
	print("%s -> %s" % (os.path.basename(path), target))
