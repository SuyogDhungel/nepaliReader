import sys,time; sys.path.insert(0,'addon/globalPlugins/nepaliReader')
from PIL import Image, ImageDraw, ImageFont
import tesseractOcr as T
f=ImageFont.truetype('/root/ref/gf/ofl/mukta/Mukta-Regular.ttf',15, layout_engine=ImageFont.Layout.RAQM)
lines=['नेपाल सरकार, शिक्षा मन्त्रालय','सूचना: विद्यालय भोलि बिदा रहनेछ।','भारत सरकार हिन्दी भाषा का प्रयोग','Notice: Office closed on Friday.']
img=Image.new('RGB',(520,120),'white'); d=ImageDraw.Draw(img)
for i,l in enumerate(lines): d.text((10,8+27*i),l,font=f,fill='black')
img.save('/tmp/ocr_in.png')
scale=3; big=img.resize((img.width*scale,img.height*scale),Image.LANCZOS)  # what NVDA's resize factor does
raw=big.convert('RGBA').tobytes('raw','BGRA')
exe=T.findTesseract(); print('exe',exe)
t=time.perf_counter(); data=T.recognizeBgra(exe,raw,big.width,big.height); print('secs',round(time.perf_counter()-t,2))
for line in data: print(' '.join(w['text'] for w in line), '| first box', line[0]['x'],line[0]['y'])
