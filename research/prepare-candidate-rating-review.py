"""Create numbered contact sheets for reviewing public-image scoring eligibility."""
from pathlib import Path
import json
from PIL import Image,ImageOps,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data';out=DATA/'candidate-rating';(out/'review-sheets').mkdir(parents=True,exist_ok=True)
rows=json.loads((DATA/'candidate-collection/candidates.json').read_text());(out/'index.json').write_text(json.dumps(rows,indent=2))
font_path=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
font=ImageFont.truetype(str(font_path),11) if font_path.exists() else ImageFont.load_default()
for batch in range((len(rows)+99)//100):
 subset=rows[batch*100:(batch+1)*100];sheet=Image.new('RGB',(1280,((len(subset)+9)//10)*153),'#eeeeee');draw=ImageDraw.Draw(sheet)
 for j,row in enumerate(subset):
  im=ImageOps.contain(Image.open(DATA/'images'/row['filename']),(124,124));x=j%10*128;y=j//10*153;sheet.paste(im,(x,y));text=str(batch*100+j)+' '+row['title'][:16]
  draw.text((x,y+125),text.encode('ascii','replace').decode(),font=font,fill='black')
 sheet.save(out/'review-sheets'/f'{batch:02d}.jpg',quality=90)
print('Prepared',len(rows),'images in',(len(rows)+99)//100,'numbered contact sheets')
