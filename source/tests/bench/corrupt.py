# Damages correct Unicode Nepali the way the reported PDF did: signs over/under a letter and the
# reph come out one glyph to the right, a space before a sign that follows a moved sign, lost
# spaces between words, and a letter drawn twice.
import random, re, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'addon', 'globalPlugins', 'nepaliReader'))
import glyphOrder as G

def damageWord(w, rnd, p=0.9):
    ats = [list(a) for a in G.atoms(w)]
    # reph: र् + C -> C + र्
    i = 0
    while i < len(ats) - 1:
        if ats[i][0] == 'H' and ats[i][1].startswith(G.REPH) and ats[i + 1][0] == 'C' and rnd.random() < p:
            ats[i], ats[i + 1] = ats[i + 1], ats[i]
            i += 2
            continue
        i += 1
    out = []
    i = 0
    moved = set()
    while i < len(ats):
        k, t = ats[i]
        # a run of marks: push past the next spacing glyph (if any, inside the word)
        if k == 'M':
            j = i
            while j < len(ats) and ats[j][0] == 'M':
                j += 1
            run = ats[i:j]
            if j < len(ats) and ats[j][0] in 'CHV' and rnd.random() < p:
                out.append(ats[j]); out.extend(run); moved.add(len(out) - 1)
                i = j + 1
                continue
            out.extend(run); i = j; continue
        out.append(ats[i]); i += 1
    s = ''
    for idx, (k, t) in enumerate(out):
        s += t
        if idx in moved and idx + 1 < len(out) and out[idx + 1][0] == 'S' and out[idx + 1][1] in 'ाीोौ' and rnd.random() < 0.6:
            s += ' '
    return s

def damageLine(line, rnd):
    words = line.split(' ')
    out = []
    for w in words:
        out.append(damageWord(w, rnd) if re.search('[ऀ-ॿ]', w) else w)
        if out[-1] and re.search('[क-ह]$', out[-1]) and rnd.random() < 0.02:
            out[-1] = out[-1] + ' ' + out[-1][-1]
    s = ''
    for i, w in enumerate(out):
        if i:
            s += '' if (rnd.random() < 0.08 and re.search('[ऀ-ॿ]$', s) and re.match('[ऀ-ॿ]', w)) else ' '
        s += w
    return s

if __name__ == '__main__':
    rnd = random.Random(1)
    for line in open(sys.argv[1], encoding='utf-8'):
        line = line.strip()
        if line:
            print(line + '\t' + damageLine(line, rnd))
