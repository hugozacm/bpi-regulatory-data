"""Generate illustrative stakeholder diagrams; optional dependency: Pillow."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "review_images"
OUT.mkdir(exist_ok=True)
NAVY, INK, BG = "#17324d", "#253d50", "#f5f8fb"

def font(size, bold=False):
    candidates = (
        ["C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
        if bold else
        ["C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    )
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise RuntimeError("Install Arial or DejaVu Sans to regenerate the diagrams.")

def box(d, y, title, lines, fill="white"):
    d.rounded_rectangle((80, y, 1520, y+155), 20, fill=fill, outline="#cbd8e3", width=2)
    d.text((800,y+20), title, font=font(31,True), fill=NAVY, anchor="mt")
    for i,line in enumerate(lines):
        d.text((800,y+68+i*35),line,font=font(25),fill=INK,anchor="mt")

im = Image.new("RGB",(1600,1800),BG)
d = ImageDraw.Draw(im)
d.text((800,35),"BPI data workflow",font=font(48,True),fill=NAVY,anchor="mt")
d.text((800,100),"Current draft: 2023–2025 | Every output: REVIEW_REQUIRED",
       font=font(27,True),fill="#9a4e13",anchor="mt")
steps = [
    ("1. Read official sources", ["NIC Y-9C quarterly ZIPs + FDIC financials API",
                                  "NIC dated relationships and transformation records"]),
    ("2. Match banks to holders for each quarter", ["Use same-quarter FDIC identifiers; audit against NIC control chains.",
                                                    "No NIC parent found means candidate standalone, not proven independent."]),
    ("3. Build core financials + separate deposit detail", ["Y-9C consolidated core OR candidate bank core; do not add subsidiaries twice.",
                                                           "Sum matched-bank deposits separately; preserve gaps and perimeter differences."]),
    ("4. Prepare stocks and quarterly flows", ["Stocks: quarter-end. Income: Q1 YTD; later quarters minus adjacent prior YTD.",
                                              "Keep different loan definitions separate; missing values remain missing."]),
    ("5. Review ownership, values and merger events", ["Retain raw banks and exceptions; flag potentially affected merger quarters.",
                                                       "Events do not rewrite historical financial values."]),
    ("6. Export the draft and supporting evidence", ["CSV + Parquet + DuckDB: organisation table, raw banks, checks and provenance.",
                                                     "Validation has unresolved failures; a completed run is not approval."])
]
for i,(title,lines) in enumerate(steps):
    y=170+i*210
    box(d,y,title,lines)
    if i<5:
        d.line((800,y+155,800,y+192),fill="#55748d",width=5)
        d.polygon([(800,y+205),(789,y+188),(811,y+188)],fill="#55748d")
box(d,1450,"PLANNED — not implemented",[
    "Complete population / bank-only groups, agreed definitions and earlier history.",
    "Dated highest-parent grouping; predecessors stay separate before official merger."
], "#fff0db")
d.text((800,1650),"Coverage gap: 40,430 bank-quarter rows with a holder but no selected Y-9C",
       font=font(25,True),fill=INK,anchor="mt")
d.text((800,1695),"are retained in raw data but excluded from the main organisation table.",
       font=font(25),fill=INK,anchor="mt")
im.save(OUT/"workflow.png")

im = Image.new("RGB",(1900,1510),BG)
d = ImageDraw.Draw(im)
d.text((65,35),"Output structure — current draft",font=font(46,True),fill=NAVY)
d.text((65,100),"ILLUSTRATIVE figures, not real records. USD millions here; production uses USD thousands.",
       font=font(25,True),fill="#9a4e13")

def table(y,title,headers,rows,widths,note):
    d.text((65,y),title,font=font(30,True),fill=NAVY)
    top=y+50
    for i,row in enumerate([headers]+rows):
        x=65
        for value,w in zip(row,widths):
            yy=top+i*61
            d.rectangle((x,yy,x+w,yy+61),fill=NAVY if i==0 else ("white" if i%2 else "#eaf0f5"),
                        outline="#d8e2ea")
            d.text((x+12,yy+19),str(value),font=font(22,i==0),fill="white" if i==0 else INK)
            x+=w
    d.text((65,top+(len(rows)+1)*61+15),note,font=font(23),fill=INK)

table(170,"1. organisation_financials — one row per organisation and quarter",[
    "Org","Quarter","Level","Assets","BHC loans","Bank net loans","Equity","Quarter income"],[
    ["A","2023 Q1","Holder","1,000","600","—","100","10"],
    ["B","2023 Q1","Bank candidate","200","—","120","20","2"],
    ["A","2023 Q2","Holder","1,250","750","—","125","13"]
], [100,150,260,190,210,270,170,420],
"BHC loans are net of unearned income; bank net loans are net of allowances. They are not equivalent.")

table(550,"2. Deposit detail — separately labelled FDIC bank-perimeter sums",[
    "Org","Quarter","Core deposits","Bank total","Domestic","Foreign","Domestic int.","Domestic nonint."],[
    ["A","2023 Q1","650","675","650","25","450","200"],
    ["B","2023 Q1","130","130","130","missing","90","40"]
], [100,150,260,200,200,180,290,390],
"Bank sums are not added to core deposits. Missing detail stays missing; candidate banks use their own values.")

table(865,"3. Supporting evidence — separate linked tables",[
    "Table","Contents","Why retain it"],[
    ["bank_raw / coverage","All downloaded banks, including excluded groups","Coverage transparency"],
    ["ownership / audit","FDIC links and dated NIC control-chain checks","Explain inclusion decisions"],
    ["validation / exceptions","Check results, missing measures, negative stocks","Review unresolved issues"],
    ["merger_events / quarter review","Source events and potentially affected quarters","Not an adjusted history"],
    ["provenance","Source URLs, hashes, parameters, processing time","Trace the source snapshot"]
], [400,850,520],
"Every financial export is REVIEW_REQUIRED. These examples do not demonstrate financial certification.")
d.rounded_rectangle((65,1360,1835,1475),18,fill="#fff0db",outline="#d8c29a")
d.text((90,1380),"NEW TARGET: one dataset with ownership valid at each reporting date.",
       font=font(27,True),fill=NAVY)
d.text((90,1425),"No retroactive merger combination. Highest-parent grouping and expanded financial schedules still need work.",
       font=font(24),fill=INK)
im.save(OUT/"output_tables_example.png")
print(OUT)
