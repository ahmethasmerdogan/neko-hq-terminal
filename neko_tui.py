#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEKO HQ (terminal) — Claude CLI kedi kafesi, dogrudan terminalde calisir.

Warp'ta bir panede `python3 neko_tui.py`, baska panede `claude`.
Her oturum bir kedi olur; calisinca yazar, sessizlikte uyur.
Isim/renk degisikligi ARAYUZDEN: 1-8 ile kedi sec, [n] isim, [c] renk, [q] cik.

Yalnizca Python standart kutuphanesi (macOS/Linux/Warp). Cikis: q veya Ctrl+C.
"""
import os, sys, json, time, re, select, argparse, shutil, shlex
try:
    import termios, tty
    HAVE_TTY = True
except Exception:
    HAVE_TTY = False

W, H = 112, 72
HOME = os.path.expanduser("~")
APP_DIR = os.path.join(HOME, ".neko-hq")
LOG = os.path.join(APP_DIR, "activity.log")
OVR_FILE = os.path.join(APP_DIR, "cats.json")
SETTINGS = os.path.join(HOME, ".claude", "settings.json")
SELF = os.path.abspath(__file__)
PY = sys.executable or "python3"
MARK = "# neko-hq"

NAMES = ["Pamuk", "Zeytin", "Boncuk", "Sansli", "Mirnav", "Duman", "Tarcin", "Karamel"]
PAL_HEX = [
    {"F":"#f0a64b","d":"#cf7f2c","l":"#ffc878","B":"#fce3c2","I":"#f3a9bb","N":"#e07a92","iris":"#7fb24a","s":"#cf7f2c"},
    {"F":"#9aa3b2","d":"#79839a","l":"#c2cad6","B":"#e6ebf2","I":"#f3a9bb","N":"#d97f96","iris":"#6fae9a","s":"#79839a"},
    {"F":"#3a3e48","d":"#24262e","l":"#565b6b","B":"#f1f2f4","I":"#e79aa8","N":"#d97f96","iris":"#8fd06a","s":None},
    {"F":"#efe6d3","d":"#cfc3a8","l":"#fffaf0","B":"#fffaf0","I":"#f3a9bb","N":"#e07a92","iris":"#caa24a","s":None},
    {"F":"#e7c27a","d":"#b98e44","l":"#f7df9f","B":"#fff7ea","I":"#f3a9bb","N":"#e07a92","iris":"#7faf6a","s":"#9a6b3a"},
    {"F":"#b9897a","d":"#956a5e","l":"#d8b0a3","B":"#f4e7df","I":"#f3a9bb","N":"#d97f96","iris":"#6fae9a","s":"#7a5446"},
]
TOOL_TASKS = {
    "Bash":"terminalde komut","Read":"dosya okuyor","Edit":"kod yaziyor","Write":"kod yaziyor",
    "MultiEdit":"kod duzenliyor","Grep":"kodda ariyor","Glob":"dosya tariyor",
    "WebSearch":"web'de ariyor","WebFetch":"sayfa getiriyor","Task":"alt-ajan acti","TodoWrite":"liste yaziyor",
}

def hx(s):
    s = s.lstrip("#")
    return (int(s[0:2],16), int(s[2:4],16), int(s[4:6],16))

PAL = []
for p in PAL_HEX:
    q = {}
    for k,v in p.items():
        q[k] = hx(v) if v else None
    PAL.append(q)

OUT = (34,26,18)
WALL = [(244,230,205),(236,221,196),(224,206,178)]
WAIN = (190,170,128); WAINT=(140,114,80); BASE=(110,74,40)
FLOOR = [(178,124,80),(156,107,62),(138,93,52)]
SKY=[(143,199,239),(166,210,242),(190,221,245)]; SUN=(255,209,74); SUNG=(255,231,154); CLOUD=(255,255,255)
FRAME=(110,74,40); SILL=(138,94,54)
RUG=(124,74,143); RUG2=(106,61,124); RUGL=(154,99,173)
POT=(194,98,47); POTD=(151,67,33); LEAF=(74,165,82); LEAFD=(47,122,52); LEAFL=(98,193,104)
SIGN=(94,58,30); SIGNL=(122,74,38); SIGNT=(243,220,174)
DESK=(138,86,48); DESKD=(94,58,30); DESKL=(160,106,60); LEG=(70,41,15)
LAPC=(52,57,74); LAPK=(207,210,216); SCR=(16,35,27); CODE=(123,224,143)
MUG=(217,83,79); MUGD=(178,62,58); STEAM=(238,246,255)
PLAQ=(202,164,106); PLAQD=(154,122,72); PLAQL=(230,207,154)
BADGE=(40,30,22); BADGET=(247,236,206)

DIGITS = {
 "1":["010","110","010","010","111"],
 "2":["111","001","111","100","111"],
 "3":["111","001","111","001","111"],
 "4":["101","101","111","001","001"],
 "5":["111","100","111","001","111"],
 "6":["111","100","111","101","111"],
 "7":["111","001","010","010","010"],
 "8":["111","101","111","101","111"],
}

class Buf:
    def __init__(self, w, h):
        self.w=w; self.h=h
        self.d=[[(0,0,0) for _ in range(w)] for _ in range(h)]
    def fill_band(self, y0, y1, rgb):
        for y in range(max(0,y0),min(self.h,y1)):
            row=self.d[y]
            for x in range(self.w): row[x]=rgb
    def px(self, x, y, w, h, rgb):
        if rgb is None: return
        x0=int(x); y0=int(y); x1=int(x+w); y1=int(y+h)
        if x0<0:x0=0
        if y0<0:y0=0
        if x1>self.w:x1=self.w
        if y1>self.h:y1=self.h
        for yy in range(y0,y1):
            row=self.d[yy]
            for xx in range(x0,x1): row[xx]=rgb

def digit(b,x,y,ch,col):
    g=DIGITS.get(ch); 
    if not g: return
    for r in range(5):
        for c in range(3):
            if g[r][c]=="1": b.px(x+c,y+r,1,1,col)

def rrect(b,x,y,w,h,fill,out):
    for j in range(h):
        ins = 2 if (j==0 or j==h-1) else (1 if (j==1 or j==h-2) else 0)
        b.px(x+ins,y+j,w-2*ins,1,out)
    for j in range(1,h-1):
        ins = 2 if (j==1 or j==h-2) else (1 if (j==2 or j==h-3) else 0)
        b.px(x+1+ins,y+j,w-2-2*ins,1,fill)

def cat(b, ox, oy, P, pose, t):
    F,d,l,B,I,N,iris,s = P["F"],P["d"],P["l"],P["B"],P["I"],P["N"],P["iris"],P["s"]
    blink = (t//9)%13==0
    # ground shadow
    b.px(ox+3, oy+22, 16, 1, (60,42,24))
    # tail (curl right) with stripe
    b.px(ox+17,oy+15,3,4,OUT); b.px(ox+17,oy+16,2,3,F)
    b.px(ox+18,oy+11,3,5,OUT); b.px(ox+18,oy+12,2,4,F)
    b.px(ox+16,oy+9,3,4,OUT);  b.px(ox+16,oy+10,2,3,F)
    if s: b.px(ox+18,oy+12,2,1,s); b.px(ox+17,oy+16,1,1,s)
    # ears
    b.px(ox+3,oy,3,1,OUT); b.px(ox+2,oy+1,5,1,OUT); b.px(ox+2,oy+2,6,1,OUT)
    b.px(ox+3,oy+1,3,1,F); b.px(ox+3,oy+2,4,1,F); b.px(ox+4,oy+3,3,2,F)
    b.px(ox+4,oy+2,2,2,I)
    b.px(ox+16,oy,3,1,OUT); b.px(ox+15,oy+1,5,1,OUT); b.px(ox+14,oy+1,6,1,OUT)
    b.px(ox+16,oy+1,3,1,F); b.px(ox+15,oy+2,4,1,F); b.px(ox+15,oy+3,3,2,F)
    b.px(ox+16,oy+2,2,2,I)
    # head (rounded)
    rrect(b, ox+3, oy+3, 16, 11, F, OUT)
    b.px(ox+5,oy+4,12,1,l)
    b.px(ox+5,oy+12,12,1,d)
    if s:
        b.px(ox+10,oy+4,2,3,s); b.px(ox+7,oy+5,1,2,s); b.px(ox+14,oy+5,1,2,s)
    # muzzle
    b.px(ox+6,oy+9,10,4,B)
    # cheek blush
    b.px(ox+5,oy+10,2,1,(244,176,188)); b.px(ox+15,oy+10,2,1,(244,176,188))
    # eyes (big & cute)
    ey=oy+6; exL=ox+5; exR=ox+12
    if pose=="sleep" or blink:
        b.px(exL,ey+2,4,1,OUT); b.px(exR,ey+2,4,1,OUT)
        b.px(exL,ey+1,1,1,OUT); b.px(exR+3,ey+1,1,1,OUT)
    else:
        dd = 1 if pose=="read" else 0
        b.px(exL,ey,4,5,(255,255,255)); b.px(exR,ey,4,5,(255,255,255))
        b.px(exL,ey,4,1,OUT); b.px(exR,ey,4,1,OUT)
        b.px(exL,ey+1,4,3,iris); b.px(exR,ey+1,4,3,iris)
        b.px(exL+1,ey+1+dd,2,3,(14,17,24)); b.px(exR+1,ey+1+dd,2,3,(14,17,24))
        b.px(exL+1,ey+1,1,1,(255,255,255)); b.px(exR+1,ey+1,1,1,(255,255,255))
    # nose + little smile
    b.px(ox+10,oy+10,2,1,N); b.px(ox+11,oy+11,1,1,N)
    b.px(ox+8,oy+12,2,1,d); b.px(ox+12,oy+12,2,1,d); b.px(ox+10,oy+13,2,1,d)
    # whiskers (short)
    b.px(ox+2,oy+10,3,1,(252,252,252)); b.px(ox+1,oy+12,3,1,(252,252,252))
    b.px(ox+16,oy+10,3,1,(252,252,252)); b.px(ox+17,oy+12,3,1,(252,252,252))
    # body (rounded)
    rrect(b, ox+4, oy+13, 14, 9, F, OUT)
    b.px(ox+8,oy+15,6,6,B)
    if s: b.px(ox+5,oy+16,1,4,s); b.px(ox+16,oy+16,1,4,s)
    # paws
    py=oy+20
    if pose=="walk":
        k=(t//2)%2
        b.px(ox+6,py,3,2,F); b.px(ox+12,py,3,2,F)
        if k==0: b.px(ox+5,py+1,2,1,F)
        else: b.px(ox+14,py+1,2,1,F)
    elif pose=="read":
        b.px(ox+5,oy+17,12,5,(233,231,223)); b.px(ox+10,oy+17,1,5,(196,193,184))
        b.px(ox+6,py,3,2,F); b.px(ox+13,py,3,2,F)
    else:
        k=(t//3)%2
        b.px(ox+6,py-(1 if (pose=="type" and k==0) else 0),3,2,F)
        b.px(ox+13,py-(1 if (pose=="type" and k==1) else 0),3,2,F)
        b.px(ox+7,py+1,1,1,d); b.px(ox+14,py+1,1,1,d)
    # zzz / typing bubble
    if pose=="sleep" and (t//12)%2==0:
        b.px(ox+19,oy+1,1,1,OUT); b.px(ox+21,oy-1,1,1,OUT)
    if pose=="type" and (t//10)%3==0:
        b.px(ox+7,oy-3,9,3,(255,255,255)); b.px(ox+8,oy-2,1,1,OUT); b.px(ox+11,oy-2,1,1,OUT); b.px(ox+14,oy-2,1,1,OUT)

def window(b,X,Y,w,h):
    b.px(X-2,Y-2,w+4,h+4,FRAME)
    bh=h//3
    for i in range(3): b.px(X,Y+i*bh,w,(h-2*bh if i==2 else bh),SKY[i])
    b.px(X+w-10,Y+3,7,7,SUNG); b.px(X+w-9,Y+4,5,5,SUN)
    b.px(X+4,Y+7,8,2,CLOUD); b.px(X+7,Y+5,7,2,CLOUD)
    b.px(X+w//2-1,Y,1,h,FRAME); b.px(X,Y+h//2,w,1,FRAME)
    b.px(X-3,Y+h+1,w+6,2,SILL)

def plant(b,X,Y):
    b.px(X+1,Y+5,7,7,POT); b.px(X+1,Y+5,7,1,(216,114,66)); b.px(X+1,Y+11,7,1,POTD)
    b.px(X,Y+1,9,4,LEAFD); b.px(X+2,Y-1,5,3,LEAF); b.px(X+3,Y-3,3,2,LEAFL)

def banner(b):
    X=42; b.px(X,2,28,9,SIGN); b.px(X,2,28,1,SIGNL); b.px(X,10,28,1,(62,38,15))
    # paw + heart
    b.px(X+9,6,3,2,SIGNT); b.px(X+8,4,1,1,SIGNT); b.px(X+10,3,1,1,SIGNT); b.px(X+12,3,1,1,SIGNT); b.px(X+14,4,1,1,SIGNT)
    b.px(X+18,4,2,2,(239,138,160)); b.px(X+21,4,2,2,(239,138,160)); b.px(X+18,6,5,1,(239,138,160)); b.px(X+19,7,3,1,(239,138,160)); b.px(X+20,8,1,1,(239,138,160))

def laptop(b,lx,ly,tool):
    sc=SCR; cc=CODE
    if tool=="Bash": sc=(12,18,14)
    elif tool in ("WebSearch","WebFetch"): sc=(14,27,40); cc=(111,182,239)
    b.px(lx,ly-6,12,7,LAPC); b.px(lx+1,ly-5,10,5,sc)
    for q in range(2):
        ax=lx+2+((b_step+q*3)%8); b.px(ax,ly-4+q*2,3,1,cc)
    b.px(lx-1,ly+1,14,2,LAPK)

b_step=0  # current animation step (set each frame)

def workstation(b, cx, dy, P, busy, tool, idx):
    pose = "sleep"
    if busy>0:
        pose = "read" if tool in ("Read","WebSearch") else "type"
    cat(b, cx-11, dy-22, P, pose, b_step)
    # number badge above head
    bx=cx-2; by=dy-29
    b.px(bx-1,by-1,5,7,BADGE)
    digit(b,bx,by,str(idx+1),BADGET)
    # desk
    b.px(cx-22,dy,44,3,DESK); b.px(cx-22,dy,44,1,DESKL)
    b.px(cx-22,dy+3,44,7,(94,58,30))
    b.px(cx-20,dy+10,3,7,LEG); b.px(cx+17,dy+10,3,7,LEG)
    if pose!="read":
        laptop(b,cx-6,dy-1,tool)
        Fp=P["F"]; b.px(cx-5,dy-1,2,1,Fp); b.px(cx+3,dy-1,2,1,Fp)
    b.px(cx+12,dy-3,3,3,MUG)
    if busy>0 and (b_step//6)%2==0: b.px(cx+13,dy-5,1,1,STEAM)
    # plaque
    b.px(cx-11,dy+4,22,5,PLAQ); b.px(cx-11,dy+4,22,1,PLAQL); b.px(cx-11,dy+8,22,1,PLAQD)

def layout(n):
    pos=[]
    if n<=0: return pos
    rows = 1 if n<=4 else 2
    per = (n + rows - 1)//rows
    xs, xe = 18, 94
    for r in range(rows):
        cnt = per if r<rows-1 else n-per*r
        if cnt<=0: continue
        topY = 50 if r==0 else 38
        off = 12 if (rows>1 and r==1) else 0
        for c in range(cnt):
            fx = (xs+xe)//2 if cnt==1 else xs + (xe-xs)*c//(cnt-1)
            fx += off
            if fx>xe: fx=xe
            pos.append((int(fx), topY))
    return pos

def draw_office(b, agents):
    b.fill_band(0,28,WALL[0]); b.fill_band(28,40,WALL[1]); b.fill_band(40,46,WALL[2])
    b.px(0,44,W,2,WAIN); b.px(0,44,W,1,WAINT); b.px(0,46,W,2,BASE)
    b.fill_band(48,58,FLOOR[2]); b.fill_band(58,66,FLOOR[1]); b.fill_band(66,72,FLOOR[0])
    for fy in range(52,72,6): b.px(0,fy,W,1,(70,46,24))
    # rug
    b.px(34,58,46,12,RUG); b.px(37,60,40,8,RUGL); b.px(40,62,34,4,RUG)
    banner(b)
    window(b,12,12,26,20); window(b,80,12,22,20)
    plant(b,2,40); plant(b,104,40)
    # agents
    pos=layout(len(agents))
    order=sorted(range(len(pos)), key=lambda i: pos[i][1])
    for i in order:
        cx,dy=pos[i]; a=agents[i]
        workstation(b, cx, dy, a["pal"], a["busy"], a["tool"], a["slot"])

# ----- activity log -> agents (per session) -----
class Store:
    def __init__(self, path):
        self.path=path; self.offset=0; self.buf=b""; self.sessions={}; self.glob=[]; self.counter=0
    def poll(self, now):
        try: st=os.stat(self.path)
        except OSError: return
        if st.st_size < self.offset: self.offset=0; self.buf=b""
        if st.st_size != self.offset:
            try:
                with open(self.path,"rb") as f:
                    f.seek(self.offset); data=f.read(); self.offset=f.tell()
                self.buf+=data; parts=self.buf.split(b"\n"); self.buf=parts.pop()
                for ln in parts: self._p(ln, now)
            except OSError: pass
    def _p(self, ln, now):
        if not ln.strip(): return
        s=ln.decode("utf-8","ignore"); ts=now; rest=s; sp=s.find(" ")
        if sp>0 and s[:sp].isdigit():
            try: ts=int(s[:sp])
            except: ts=now
            rest=s[sp+1:]
        sid=ev=tool=None
        try:
            d=json.loads(rest); sid=d.get("session_id"); ev=d.get("hook_event_name"); tool=d.get("tool_name")
        except Exception:
            m=re.search(r'"session_id"\s*:\s*"([^"]+)"',rest); sid=m.group(1) if m else None
            m=re.search(r'"tool_name"\s*:\s*"([^"]+)"',rest); tool=m.group(1) if m else None
        sid=sid or "default"
        se=self.sessions.get(sid)
        if se is None: se={"first":ts,"slot":self.counter,"events":[]}; self.counter+=1; self.sessions[sid]=se
        se["events"].append((ts,ev or "?",tool)); self.glob.append((ts,ev or "?",tool))
    def prune(self, now):
        for sid in list(self.sessions):
            evs=[e for e in self.sessions[sid]["events"] if e[0]>=now-130]
            if not evs: del self.sessions[sid]
            else: self.sessions[sid]["events"]=evs
        self.glob=[e for e in self.glob if e[0]>=now-60]
    def agents(self, now):
        out=[]
        for sid,se in sorted(self.sessions.items(), key=lambda kv:(kv[1]["first"],kv[0])):
            evs=se["events"]
            if not evs or evs[-1][0]<now-130: continue
            busy=max(0,min(5,sum(1 for e in evs if e[0]>=now-8)))
            tool=None
            for ts,ev,tl in evs:
                if ts>=now-5 and tl: tool=tl
            out.append({"slot":se["slot"],"busy":busy,"tool":tool})
            if len(out)>=8: break
        return out
    def headline(self, now):
        pr=any(ev=="UserPromptSubmit" and ts>=now-4 for ts,ev,_ in self.glob)
        best=None
        for ts,ev,tool in self.glob:
            if ts>=now-5 and (best is None or ts>=best[0]): best=(ts,ev,tool)
        ev,tool=(best[1],best[2]) if best else (None,None)
        if pr: return "yeni gorev geldi!"
        if ev in ("Stop","SubagentStop"): return "is tamamlandi"
        t=TOOL_TASKS.get(tool)
        return t if t else ("kafe sakin - kediler uyukluyor" if not tool else str(tool))

# overrides (names/colors) — edited from UI, saved silently
def load_ovr():
    try:
        with open(OVR_FILE,"r",encoding="utf-8") as f: return json.load(f)
    except Exception: return {}
def save_ovr(o):
    try:
        os.makedirs(APP_DIR,exist_ok=True)
        with open(OVR_FILE,"w",encoding="utf-8") as f: json.dump(o,f,ensure_ascii=False)
    except Exception: pass

def resolve(agents, ovr):
    out=[]
    for a in agents:
        slot=a["slot"]; o=ovr.get(str(slot),{})
        name=o.get("name") or NAMES[slot%len(NAMES)]
        ci=o.get("color"); ci=ci if isinstance(ci,int) else slot%len(PAL)
        a2=dict(a); a2["name"]=name; a2["pal"]=PAL[ci%len(PAL)]; a2["ci"]=ci%len(PAL); out.append(a2)
    return out

# ---------- demo ----------
DSC=[(3,0,0),(2,1,1),(3,3,0),(3,5,0),(3.5,8,0),(3,2,0)]
DTOT=sum(s[0] for s in DSC)
DTOOLS=["Edit","Bash","WebSearch","Read","Write"]
def demo_agents(now):
    a=now%DTOT; acc=0; n=0
    for d,nn,_ in DSC:
        acc+=d
        if a<acc: n=nn; break
    res=[]
    for i in range(n):
        idle=(int(now/1.3+i)%5==0)
        tool=DTOOLS[(i+int(now/1.7))%len(DTOOLS)]
        res.append({"slot":i,"busy":0 if idle else (3+(i%3)),"tool":None if idle else tool})
    return res

# ---------- renderers ----------
def render_terminal(b):
    HALF="\u2580"
    rows=[]
    for ry in range(0,b.h,2):
        top=b.d[ry]; bot=b.d[ry+1] if ry+1<b.h else top
        line=[]; pr=pg=pb=-1; pR=pG=pB=-1
        for x in range(b.w):
            tr,tg,tb=top[x]; br,bg,bb=bot[x]
            line.append("\x1b[38;2;%d;%d;%d;48;2;%d;%d;%dm%s"%(tr,tg,tb,br,bg,bb,HALF))
        rows.append("".join(line)+"\x1b[0m")
    return rows

def render_ascii(b):
    ramp=" .:-=+*#%@"
    rows=[]
    for y in range(b.h):
        line=[]
        for x in range(b.w):
            r,g,bl=b.d[y][x]; lum=(r*299+g*587+bl*114)//1000
            line.append(ramp[min(len(ramp)-1, lum*len(ramp)//256)])
        rows.append("".join(line))
    return rows

def render_png(b, path, scale=7):
    from PIL import Image
    img=Image.new("RGB",(b.w,b.h))
    px=img.load()
    for y in range(b.h):
        for x in range(b.w): px[x,y]=b.d[y][x]
    img=img.resize((b.w*scale,b.h*scale),Image.NEAREST)
    img.save(path)

# ---------- hooks (activity logging only) ----------
HOOK_CMD=('mkdir -p "$HOME/.neko-hq" && '
          '{ printf \'%s \' "$(date +%s)"; cat | tr -d \'\\n\'; printf \'\\n\'; } '
          '>> "$HOME/.neko-hq/activity.log" '+MARK)
HEVENTS=[("UserPromptSubmit",False),("PreToolUse",True),("Stop",False),("SubagentStop",False)]
def _blk(needs):
    return ({"matcher":"","hooks":[{"type":"command","command":HOOK_CMD}]} if needs
            else {"hooks":[{"type":"command","command":HOOK_CMD}]})
def _has(lst):
    return any(MARK in (h.get("command") or "") for x in lst for h in x.get("hooks",[]))
def install_hooks():
    data={}
    if os.path.exists(SETTINGS):
        try:
            with open(SETTINGS,encoding="utf-8") as f: t=f.read().strip(); data=json.loads(t) if t else {}
        except Exception as e: print("ayar okunamadi:",e); return
    hk=data.setdefault("hooks",{}); add=0
    for ev,needs in HEVENTS:
        lst=hk.setdefault(ev,[])
        if not _has(lst): lst.append(_blk(needs)); add+=1
    if add==0: print("• Hook'lar zaten kurulu."); return
    os.makedirs(os.path.dirname(SETTINGS),exist_ok=True)
    if os.path.exists(SETTINGS): shutil.copyfile(SETTINGS,SETTINGS+".bak")
    with open(SETTINGS,"w",encoding="utf-8") as f: json.dump(data,f,indent=2,ensure_ascii=False); f.write("\n")
    print("• Hook'lar kuruldu (%d). Claude Code'u yeniden baslat (veya /hooks)."%add)
def uninstall_hooks():
    if not os.path.exists(SETTINGS): print("ayar yok."); return
    try:
        with open(SETTINGS,encoding="utf-8") as f: data=json.loads(f.read() or "{}")
    except Exception: print("ayar okunamadi."); return
    hk=data.get("hooks",{}); rm=0
    for ev,_ in HEVENTS:
        if ev in hk:
            new=[x for x in hk[ev] if not _has([x])]; rm+=len(hk[ev])-len(new)
            if new: hk[ev]=new
            else: del hk[ev]
    if not hk: data.pop("hooks",None)
    with open(SETTINGS,"w",encoding="utf-8") as f: json.dump(data,f,indent=2,ensure_ascii=False); f.write("\n")
    print("• Hook'lar kaldirildi (%d)."%rm)

# ---------- UI / main loop ----------
def meter(busy):
    return "".join("#" if i<busy else "." for i in range(5))

def build_screen(b, agents, headline, office, sel, mode, namebuf, cols):
    rows=render_terminal(b)
    out=[]
    title="  NEKO HQ   yogunluk %s   |  %s"%(meter(max([a['busy'] for a in agents],default=0)), headline)
    out.append("\x1b[1m"+title[:cols].ljust(min(cols,b.w))+"\x1b[0m")
    out += rows
    # roster
    out.append("")
    if not agents:
        out.append("  (henuz kedi yok — Warp'ta `claude` calistirip soru sor)")
    else:
        for i,a in enumerate(agents):
            mk=">" if i==sel else " "
            st = "uyuyor" if a["busy"]==0 else (TOOL_TASKS.get(a["tool"],"calisiyor"))
            r,g,bl=a["pal"]["F"]
            sw="\x1b[38;2;%d;%d;%dm\u25a0\x1b[0m"%(r,g,bl)
            line="  %s [%d] %s %-9s  %-14s"%(mk,i+1,sw,a["name"][:9],st)
            if i==sel: line="\x1b[7m"+line+"\x1b[0m"
            out.append(line)
    out.append("")
    if mode=="name":
        out.append("  Yeni isim: "+namebuf+"\u2588   (Enter=tamam, Esc=iptal)")
    else:
        out.append("  1-8 sec   [n] isim   [c] renk   [q] cik")
    return "\n".join(out)

def main():
    global b_step
    ap=argparse.ArgumentParser()
    ap.add_argument("--demo",action="store_true")
    ap.add_argument("--png"); ap.add_argument("--scale",type=int,default=7)
    ap.add_argument("--frames",type=int,default=0)
    ap.add_argument("--ascii",action="store_true")
    ap.add_argument("--install-hooks",action="store_true")
    ap.add_argument("--uninstall-hooks",action="store_true")
    ap.add_argument("--no-install",action="store_true")
    a=ap.parse_args()

    if a.install_hooks: install_hooks(); return
    if a.uninstall_hooks: uninstall_hooks(); return

    os.makedirs(APP_DIR,exist_ok=True)
    store=Store(LOG); ovr=load_ovr()

    # one-shot dev renderers
    if a.png or a.ascii or a.frames:
        b_step=18
        ags = demo_agents(time.time()) if (a.demo or True) else []
        ags = resolve(ags, ovr)
        buf=Buf(W,H); draw_office(buf, ags)
        if a.png: render_png(buf,a.png,a.scale); print("png:",a.png); return
        if a.ascii:
            print("\n".join(render_ascii(buf))); return
        for fr in range(a.frames):
            b_step=18+fr
            ags=resolve(demo_agents(time.time()+fr) if a.demo else [], ovr)
            buf=Buf(W,H); draw_office(buf,ags)
            sys.stdout.write("\x1b[H"+build_screen(buf,ags,"demo","NEKO HQ",0,"normal","",W)+"\n")
        return

    if not a.no_install:
        try: install_hooks()
        except Exception: pass
        try: open(LOG,"a").close()
        except Exception: pass

    istty = sys.stdin.isatty() and HAVE_TTY
    fd=None; old=None
    if istty:
        fd=sys.stdin.fileno(); old=termios.tcgetattr(fd); tty.setcbreak(fd)
        sys.stdout.write("\x1b[?1049h\x1b[?25l\x1b[2J")
    sel=0; mode="normal"; namebuf=""
    try:
        while True:
            now=time.time()
            if a.demo: ags_raw=demo_agents(now)
            else:
                store.poll(now); store.prune(now); ags_raw=store.agents(now)
            ags=resolve(ags_raw, ovr)
            head = "demo" if a.demo else store.headline(now)
            if sel>=len(ags): sel=max(0,len(ags)-1)
            # input
            if istty:
                while select.select([sys.stdin],[],[],0)[0]:
                    ch=sys.stdin.read(1)
                    if ch=="": break
                    if mode=="name":
                        if ch in ("\r","\n"):
                            if ags and namebuf.strip():
                                slot=ags[sel]["slot"]; o=ovr.setdefault(str(slot),{}); o["name"]=namebuf.strip()[:9]; save_ovr(ovr)
                            mode="normal"; namebuf=""
                        elif ch=="\x1b": mode="normal"; namebuf=""
                        elif ch in ("\x7f","\b"): namebuf=namebuf[:-1]
                        elif ch.isprintable() and len(namebuf)<9: namebuf+=ch
                    else:
                        if ch in ("q","Q"): raise KeyboardInterrupt
                        elif ch.isdigit() and ch!="0":
                            k=int(ch)-1
                            if k<len(ags): sel=k
                        elif ch in ("n","N"):
                            if ags: mode="name"; namebuf=""
                        elif ch in ("c","C"):
                            if ags:
                                slot=ags[sel]["slot"]; o=ovr.setdefault(str(slot),{})
                                cur=o.get("color"); cur=cur if isinstance(cur,int) else ags[sel]["ci"]
                                o["color"]=(cur+1)%len(PAL); save_ovr(ovr); ovr=ovr
            # draw
            buf=Buf(W,H); draw_office(buf,ags)
            cols=shutil.get_terminal_size((W,40)).columns
            screen=build_screen(buf,ags,head,"NEKO HQ",sel,mode,namebuf,cols)
            if istty: sys.stdout.write("\x1b[H"+screen)
            else: sys.stdout.write(screen+"\n")
            sys.stdout.flush()
            b_step+=1
            if not istty: break
            time.sleep(0.1)
    except KeyboardInterrupt: pass
    finally:
        if istty:
            sys.stdout.write("\x1b[?25h\x1b[?1049l"); sys.stdout.flush()
            try: termios.tcsetattr(fd,termios.TCSADRAIN,old)
            except Exception: pass

if __name__=="__main__":
    main()
