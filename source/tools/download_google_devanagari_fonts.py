import subprocess, re, os, json, sys
fams = "amiko amita annapurnasil arya asar baloo2 biryani cambay dekko eczar ekmukta glegoo gotu halant hind inknutantiqua jaldi kadwa kalam karma khand kurale laila martel martelsans modak mukta notosansdevanagari notoserifdevanagari palanquin palanquindark poppins pragatinarrow rajdhani rhodiumlibre rozhaone sahitya sarala sarpanch sumana sura teko tirodevanagarihindi tirodevanagarimarathi tirodevanagarisanskrit vesperlibre yantramanav yatraone".split()
os.makedirs('ttf', exist_ok=True)
got=0
for fam in fams:
    meta=None
    for lic in ('ofl','apache','ufl'):
        r=subprocess.run(['curl','-sS','-m','30','-f','https://raw.githubusercontent.com/google/fonts/main/%s/%s/METADATA.pb'%(lic,fam)],capture_output=True,text=True)
        if r.returncode==0: meta=(lic,r.stdout); break
    if not meta: print('no meta', fam); continue
    lic,txt=meta
    files=re.findall(r'filename: "([^"]+)"', txt)
    for fn in files:
        out='ttf/'+fn
        if os.path.exists(out): continue
        r=subprocess.run(['curl','-sS','-m','90','-f','-o',out,'https://raw.githubusercontent.com/google/fonts/main/%s/%s/%s'%(lic,fam,fn)],capture_output=True)
        if r.returncode==0: got+=1
        else: print('fail',fam,fn)
    print(fam, len(files))
print('downloaded', got)
