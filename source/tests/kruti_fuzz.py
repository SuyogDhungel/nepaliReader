import sys, json, random, subprocess, unicodedata
sys.path.insert(0,'addon/globalPlugins/nepaliReader')
from legacyFonts import krutiDevToUnicode as K
random.seed(7)
cons=['d','[k','x','?k','p','N','t','>','V','B','M','<','.k','r','Fk','n','/k','u','i','Q','c','Hk','e',';','j','y','o',"'k",'"k','l','g','{k','=','K','J','Ø','ç','|',')']
half=['D','[','X','?','P','T','R','F','/','U','I','C','H','E','L','Y','O',"'",'"']
mat=['','','k','h','q','w','s','S','ks','kS','a','¡','`','ka','ksa']
words=[]
for _ in range(4000):
    w=''
    for _ in range(random.randint(1,4)):
        syl=''
        if random.random()<.2: syl+=random.choice(half)
        c=random.choice(cons); m=random.choice(mat)
        if random.random()<.15: syl='f'+syl+c+m
        else: syl+=c+m
        if random.random()<.08: syl+='Z'
        w+=syl
    words.append(w)
js=subprocess.run(['node','-e','const k=require("/root/ref/package");const a=JSON.parse(require("fs").readFileSync(0));console.log(JSON.stringify(a.map(k)))'],input=json.dumps(words),capture_output=True,text=True)
ref=json.loads(js.stdout)
N=lambda s:unicodedata.normalize('NFC',s)
diff=[(w,N(K(w)),N(r)) for w,r in zip(words,ref) if N(K(w))!=N(r)]
print('total',len(words),'diff',len(diff))
for d in diff[:25]: print(d)
