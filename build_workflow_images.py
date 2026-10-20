from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / 'review_images'
OUT.mkdir(exist_ok=True)
FONT = 'C:/Windows/Fonts/arial.ttf'
BOLD = 'C:/Windows/Fonts/arialbd.ttf'
NAVY = '#17324d'
INK = '#253d50'
BG = '#f5f8fb'

def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)

def centred(draw, text, y, size=28, bold=False, colour=INK, width=1600):
    draw.text((width/2,y),text,font=font(size,bold),fill=colour,anchor='mt')

im = Image.new('RGB',(1600,1730),BG)
d = ImageDraw.Draw(im)
centred(d,'BPI regulatory data workflow',45,48,True)
centred(d,'Proposed full workflow · includes work beyond the current MVP',110,26)

def box(x,y,w,h,title,lines,fill='#ffffff'):
    d.rounded_rectangle((x,y,x+w,y+h),radius=22,fill=fill,outline='#cbd8e3',width=2)
    d.text((x+w/2,y+20),title,font=font(29,True),fill=NAVY,anchor='mt')
    for n,line in enumerate(lines):
        d.text((x+w/2,y+64+n*35),line,font=font(25),fill=INK,anchor='mt')

def arrow(x,y1,y2):
    d.line((x,y1,x,y2-12),fill='#55748d',width=5)
    d.polygon([(x,y2),(x-10,y2-16),(x+10,y2-16)],fill='#55748d')

box(80,175,690,160,'1. Holding-company filings',['All Y-9C filers · FFIEC/NIC','Quarterly financials + RSSD identifiers'])
box(830,175,690,160,'1. Bank and savings-institution filings',['All relevant Call Reports · FFIEC/FDIC','Financials + detailed deposit categories'])
d.line((425,335,425,363,1175,363,1175,335),fill='#55748d',width=4)
arrow(800,363,400)
box(180,400,1240,145,'2. Match ownership for each quarter',['Link banks to their regulatory holding company using dated identifiers.','Retain standalone banks; flag missing or ambiguous ownership.'])
arrow(800,545,585)
box(80,585,690,180,'3. Build the core financial dataset',['Use consolidated Y-9C for holding companies.','Use Call Reports for standalone banks.','Exclude subsidiaries as separate rows.'])
box(830,585,690,180,'3. Add detailed deposits',['Sum each deposit category across','the holding company’s bank subsidiaries.','Keep standalone-bank deposit detail.'])
d.line((800,565,425,565,425,585),fill='#55748d',width=4)
d.line((800,565,1175,565,1175,585),fill='#55748d',width=4)
d.line((425,765,425,790,1175,790,1175,765),fill='#55748d',width=4)
arrow(800,790,825)
box(180,825,1240,145,'4. Standardise stocks and flows',['Stocks: use quarter-end balances. Flows: convert YTD amounts to quarterly amounts.','Check definitions, reporting coverage and changes across time.'])
arrow(800,970,1010)
box(180,1010,1240,180,'5. Create merger-adjusted history',['Keep the original as-reported dataset.','Use verified predecessor/successor history to combine earlier organisations.','Choose a fixed reference date; document partial deals and accounting limits.'], '#eaf2fb')
arrow(800,1190,1230)
box(180,1230,1240,145,'6. Validate and review',['Check identifiers, ownership, duplicates, totals, deposit coverage and income.','Reconcile sample values to official filings and review merger adjustments.'])
arrow(800,1375,1415)
box(180,1415,1240,145,'7. Export the research tables',['One row per organisation and quarter in each financial dataset.','CSV + Parquet + DuckDB, with ownership, merger and source evidence.'], '#e6f4ee')
centred(d,'Historical coverage: extend as far back as verified data and mappings support.',1610,25)
centred(d,'Decisions to confirm: deposit categories · entity coverage · merger reference date',1655,24,True)
im.save(OUT/'workflow.png')

im = Image.new('RGB',(1900,1500),BG)
d = ImageDraw.Draw(im)
d.text((65,40),'Example output tables',font=font(46,True),fill=NAVY)
d.text((65,103),'ILLUSTRATIVE ONLY — invented organisation names and figures; amounts in USD millions.',font=font(25,True),fill='#9a4e13')

def table(y,title,headers,rows,widths,note):
    d.text((65,y),title,font=font(30,True),fill=NAVY)
    top=y+48
    x=65
    for h,w in zip(headers,widths):
        d.rectangle((x,top,x+w,top+55),fill=NAVY)
        d.text((x+13,top+17),h,font=font(21,True),fill='white')
        x+=w
    for i,row in enumerate(rows):
        x=65; yy=top+55+i*57
        for value,w in zip(row,widths):
            d.rectangle((x,yy,x+w,yy+57),fill='white' if i%2==0 else '#eaf0f5',outline='#d8e2ea')
            d.text((x+13,yy+18),str(value),font=font(21),fill=INK)
            x+=w
    d.text((65,top+55+len(rows)*57+15),note,font=font(22),fill=INK)

table(165,'1. As-reported financials — one row per organisation and quarter',
      ['Org. ID','Quarter','Level','Assets','Loans','Equity','Quarter income','Demand dep.','Savings dep.'],
      [['A','2023 Q1','Holding co.','1,000','600','100','10','200','450'],
       ['B','2023 Q1','Standalone','200','120','20','2','40','90'],
       ['A','2023 Q2','Holding co.','1,250','750','125','13','250','560']],
      [125,145,200,150,150,150,210,220,220],
      'Holding-company core figures come from Y-9C; its deposit categories come from aggregated Call Reports.')
table(515,'2. Merger-adjusted financials — same measures, grouped to the chosen reference date',
      ['Adjusted org.','Quarter','Included predecessors','Assets','Loans','Equity','Quarter income'],
      [['A','2023 Q1','A + B','1,200','720','120','12'],
       ['A','2023 Q2','A, including acquired B','1,250','750','125','13']],
      [200,180,550,180,180,180,210],
      'Example: A acquires B on 1 April 2023. Earlier A and B values are combined; B is not added again after acquisition.')
table(805,'3. Supporting evidence — separate linked tables',
      ['Table','Example fields','Purpose'],
      [['Institutions','Organisation ID, name, RSSD, FDIC certificate','Identify each entity'],
       ['Ownership','Bank ID, holder ID, valid dates, source','Explain grouping and exclusions'],
       ['Merger links','Predecessor, successor, effective date, evidence','Explain historical adjustments'],
       ['Validation','Check, quarter, entity, result, explanation','Show data-quality issues'],
       ['Provenance','Source URL, source field, file hash, download time','Trace values to source files']],
      [260,880,590],
      'Use stable organisation IDs to join the financial tables to their evidence.')
d.text((65,1285),'Review notes',font=font(27,True),fill=NAVY)
for i,line in enumerate([
    '• Deposit categories shown here are examples; the owner must approve the exact definitions.',
    '• Merger-adjusted figures need verified deal scope and accounting rules; simple addition is illustrative.',
    '• Production units can remain USD thousands. This example uses USD millions for readability.',
    '• The full historical and merger-adjusted outputs shown here are proposed, not yet implemented.'
]):
    d.text((65,1330+i*34),line,font=font(23),fill=INK)
im.save(OUT/'output_tables_example.png')
print(OUT)
