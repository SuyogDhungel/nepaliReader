import sys; sys.path.insert(0,'addon/globalPlugins/nepaliReader')
from legacyFonts import preetiFamilyToUnicode as P, krutiDevToUnicode as K
preeti = {'g]kfn':'नेपाल','sf7df8f}+':'काठमाडौं','/fli6«o':'राष्ट्रिय','lzIff':'शिक्षा','dGqfno':'मन्त्रालय',';/sf/':'सरकार','k|wfgdGqL':'प्रधानमन्त्री',"cg'/f]w":'अनुरोध','ljBfno':'विद्यालय','dxfgu/kflnsf':'महानगरपालिका',';"rgf':'सूचना','/fd|f]':'राम्रो','xf]':'हो','5':'छ','s[lif':'कृषि','wd{':'धर्म','sfo{qmd':'कार्यक्रम','sfo{s|d':'कार्यक्रम','cfof]u':'आयोग','pkTosf':'उपत्यका','k"/f':'पूरा','Ps':'एक','P]g':'ऐन','O{Zj/':'ईश्वर','cf}iflw':'औषधि','xfdL':'हामी','tkfO{+':'तपाईं','dlxnf':'महिला','cWoIf':'अध्यक्ष','ljZjljBfno':'विश्वविद्यालय','ljZjljb\\ofno':'विश्वविद्यालय','k|lt':'प्रति','ef/t':'भारत','lxGbL':'हिन्दी','xfd|f] b]z':'हाम्रो देश','jflif{s':'वार्षिक','km\'n':'फुल','e\'mn':'झुल','pm':'ऊ','cf]v/L':'ओखरी','l:ylt':'स्थिति','k|of]u':'प्रयोग','@)*!':'२०८१','dlGqkl/ifb\\':'मन्त्रिपरिषद्','cfGtl/s':'आन्तरिक',';+ljwfg':'संविधान','lgjf{rg':'निर्वाचन','k|ltlglw':'प्रतिनिधि','ug{\'kg]{':'गर्नुपर्ने',';Dk"0f{':'सम्पूर्ण','cIf/':'अक्षर','w]/}':'धेरै','ldlt':'मिति','b]lv':'देखि'}
bad=0
for k,v in preeti.items():
    r=P(k)
    if r!=v: bad+=1; print('PREETI FAIL',repr(k),r,'expected',v)
kruti={'esjk uke usgy gSA eS ,d Nk= gw¡A':'मेरा नाम नेहल है। मै एक छात्र हूँ।','fgUnh':'हिन्दी','Hkkjr':'भारत','ljdkj':'सरकार','Hkk"kk':'भाषा','jkT;':'राज्य','dk;ZØe':'कार्यक्रम','fo|ky;':'विद्यालय','eSa':'मैं','gS':'है','vkSj':'और','esa':'में','ugha':'नहीं','Hkh':'भी','dh':'की','iz/kkuea=h':'प्रधानमंत्री','f\'k{kk':'शिक्षा','/keZ':'धर्म','jk"Vªh;':'राष्ट्रीय','fLFkfr':'स्थिति','vkidk':'आपका','iqLrd':'पुस्तक','fodkl':'विकास','Ldwy':'स्कूल','dEI;wVj':'कम्प्यूटर','izns\'k':'प्रदेश','ifj;kstuk':'परियोजना','loZ':'सर्व','fLkagk':'सिंहा','vfHkus=h':'अभिनेत्री'}
for k,v in kruti.items():
    r=K(k)
    if r!=v: bad+=1; print('KRUTI FAIL',repr(k),r,'expected',v)
print('failures',bad,'of',len(preeti)+len(kruti))
