# Builds glyphRefs.dat: for each reference Devanagari font, the text behind every glyph
# (from the font's cmap + GSUB), its advance width and an outline fingerprint.
import sys, os, glob, json, zlib, hashlib
sys.path.insert(0, '/root/work/pkg')
from nr import sfnt, glyphRefs
out = []
seenTables = set()
files = sorted(p for a in sys.argv[2:] for p in glob.glob(a, recursive=True))
for p in files:
    data = open(p, 'rb').read()
    for face in range(sfnt.faceCount(data)):
        try:
            f = sfnt.Font(data, face)
            fam, sub, full, ps = f.names()
            if not any(0x900 <= c <= 0x97f for c in f.cmap()):
                continue
            upm, rows = sfnt.referenceTable(f)
        except Exception as e:
            print('skip', p, e); continue
        key = hashlib.md5((glyphRefs.norm(fam) + json.dumps(rows)).encode()).hexdigest()
        if key in seenTables:
            continue
        seenTables.add(key)
        famN = glyphRefs.norm(ps or fam)
        famF = glyphRefs.norm(fam)
        out.append({'family': famF, 'ps': famN, 'style': glyphRefs.styleOf(sub + ' ' + ps), 'upm': upm,
                    'adv': [r[1] for r in rows], 'str': [r[0] for r in rows], 'hash': [r[2] for r in rows]})
        print(fam, sub, len(rows))
blob = zlib.compress(json.dumps({'fonts': out}, ensure_ascii=False, separators=(',', ':')).encode('utf-8'), 9)
open(sys.argv[1], 'wb').write(blob)
print('fonts', len(out), 'bytes', len(blob))
