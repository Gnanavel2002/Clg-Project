import sqlite3, random, time, uuid, json
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

BASE=Path(__file__).parent; DB=BASE/'smritiner.db'
app=FastAPI(title='SmritiNER SIH26003')
app.add_middleware(SessionMiddleware,secret_key='change-this-secret')
templates=Jinja2Templates(directory=str(BASE/'templates'))
app.mount('/static', StaticFiles(directory=str(BASE/'static')), name='static')
OBJECTS=[('Apple','🍎'),('Banana','🍌'),('Orange','🍊'),('Grapes','🍇'),('Dog','🐶'),('Cat','🐱'),('Elephant','🐘'),('Fish','🐟'),('Car','🚗'),('Bicycle','🚲'),('House','🏠'),('Tree','🌳'),('Flower','🌸'),('Star','⭐'),('Sun','☀️'),('Music','🎵')]
COLORS=['RED','BLUE','GREEN','YELLOW','PURPLE','ORANGE']

def conn():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init():
 c=conn(); c.executescript('''
 CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE,password TEXT,name TEXT,role TEXT,language TEXT DEFAULT 'English');
 CREATE TABLE IF NOT EXISTS game_sessions(id TEXT PRIMARY KEY,user_id INTEGER,game TEXT,level INTEGER,challenge TEXT,started REAL,answered INTEGER DEFAULT 0);
 CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,game TEXT,level INTEGER,correct INTEGER,response_time REAL,score INTEGER,created TEXT);
 CREATE TABLE IF NOT EXISTS reminders(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,title TEXT,time TEXT,kind TEXT,active INTEGER DEFAULT 1);
 ''')
 c.execute("INSERT OR IGNORE INTO users VALUES(1,'patient','1234','Demo Patient','patient','English')")
 c.execute("INSERT OR IGNORE INTO users VALUES(2,'caregiver','1234','Demo Caregiver','caregiver','English')")
 if c.execute("SELECT COUNT(*) FROM reminders WHERE user_id=1").fetchone()[0]==0:
  c.executemany('INSERT INTO reminders(user_id,title,time,kind) VALUES(?,?,?,?)',[(1,'Morning medicine','08:00','Medicine'),(1,'Drink water','10:30','Hydration'),(1,'Evening walk','17:30','Activity')])
 c.commit(); c.close()
init()

def user(request):
 uid=request.session.get('uid')
 if not uid:return None
 c=conn(); u=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone();c.close();return u

def level_for(uid,game):
 c=conn(); rows=c.execute('SELECT correct,response_time,level FROM attempts WHERE user_id=? AND game=? ORDER BY id DESC LIMIT 10',(uid,game)).fetchall();c.close()
 if not rows:return 1
 acc=sum(r['correct'] for r in rows)/len(rows); rt=sum(r['response_time'] for r in rows)/len(rows); lv=rows[0]['level']
 if acc>=.85 and rt<=6:lv+=1
 elif acc<.5 or rt>12:lv-=1
 return max(1,min(10,lv))

def challenge(game,lv):
 n=min(3+lv,10)
 if game in ('memory','sequence'):
  items=random.sample(OBJECTS,n);return {'items':[{'name':a,'emoji':b} for a,b in items],'answer':[a for a,b in items],'display':max(2.5,7-lv*.35)}
 if game=='pattern':
  seq=[random.choice(COLORS) for _ in range(min(5+lv,10))];i=random.randrange(1,len(seq));ans=seq[i];opts=list(dict.fromkeys([ans]+random.sample([x for x in COLORS if x!=ans],3)));return {'pattern':seq,'missing':i,'answer':ans,'options':opts}
 routines=[['Wake up','Brush teeth','Breakfast','Take medicine','Morning walk'],['Wake up','Wash face','Breakfast','Read newspaper','Drink water'],['Get ready','Breakfast','Take medicine','Talk to family','Rest']]
 a=random.choice(routines)[:min(5,max(4,lv+3))];return {'items':a,'answer':a}

@app.get('/',response_class=HTMLResponse)
def root(request:Request):
 u=user(request);return RedirectResponse('/login' if not u else ('/caregiver' if u['role']=='caregiver' else '/dashboard'))
@app.get('/login',response_class=HTMLResponse)
def login_page(request:Request):return templates.TemplateResponse(request=request,name='login.html',context={'request':request})
@app.post('/login')
def login(request:Request,username:str=Form(...),password:str=Form(...)):
 c=conn();u=c.execute('SELECT * FROM users WHERE username=? AND password=?',(username,password)).fetchone();c.close()
 if not u:return templates.TemplateResponse(request=request,name='login.html',context={'request':request,'error':'Invalid login'})
 request.session['uid']=u['id'];return RedirectResponse('/caregiver' if u['role']=='caregiver' else '/dashboard',303)
@app.get('/logout')
def logout(request:Request):request.session.clear();return RedirectResponse('/login',303)
@app.get('/dashboard',response_class=HTMLResponse)
def dashboard(request:Request):
 u=user(request)
 if not u:return RedirectResponse('/login')
 c=conn();s=c.execute('SELECT COUNT(*) games,COALESCE(AVG(correct)*100,0) acc,COALESCE(AVG(response_time),0) rt,COALESCE(SUM(score),0) score FROM attempts WHERE user_id=?',(u['id'],)).fetchone();r=c.execute('SELECT * FROM reminders WHERE user_id=? AND active=1 ORDER BY time',(u['id'],)).fetchall();c.close()
 return templates.TemplateResponse(request=request,name='dashboard.html',context={'request':request,'user':u,'stats':s,'reminders':r})
@app.get('/game/{game}',response_class=HTMLResponse)
def game_page(request:Request,game:str):
 u=user(request)
 if not u:return RedirectResponse('/login')
 if game not in ('memory','sequence','pattern','routine'):return RedirectResponse('/dashboard')
 return templates.TemplateResponse(request=request,name='game.html',context={'request':request,'game':game})
@app.get('/api/start')
def start(request:Request,game:str):
 u=user(request)
 if not u:return JSONResponse({'error':'login'},401)
 lv=level_for(u['id'],game);ch=challenge(game,lv);sid=str(uuid.uuid4());c=conn();c.execute('INSERT INTO game_sessions VALUES(?,?,?,?,?,?,0)',(sid,u['id'],game,lv,json.dumps(ch,ensure_ascii=False),time.time()));c.commit();c.close();pub=dict(ch);pub.pop('answer');return {'session_id':sid,'level':lv,'challenge':pub}
@app.post('/api/answer')
def answer(request:Request,payload:dict):
 u=user(request)
 if not u:return JSONResponse({'error':'login'},401)
 c=conn();s=c.execute('SELECT * FROM game_sessions WHERE id=? AND user_id=? AND answered=0',(payload.get('session_id'),u['id'])).fetchone()
 if not s:c.close();return JSONResponse({'error':'invalid session'},400)
 ch=json.loads(s['challenge']);expected=ch['answer'];got=payload.get('answer');
 if isinstance(got,str):got=[x.strip() for x in got.split(',') if x.strip()]
 correct=got==expected;rt=max(.1,float(payload.get('response_time',1)));score=max(0,(1000*s['level'] if correct else 0)+max(0,200-int(rt*10)))
 c.execute('UPDATE game_sessions SET answered=1 WHERE id=?',(s['id'],));c.execute('INSERT INTO attempts(user_id,game,level,correct,response_time,score,created) VALUES(?,?,?,?,?,?,?)',(u['id'],s['game'],s['level'],int(correct),rt,score,datetime.now().isoformat(timespec='seconds')));c.commit();c.close()
 c=conn()
 recent=c.execute('SELECT correct FROM attempts WHERE user_id=? AND game=? ORDER BY id DESC LIMIT 10',(u['id'],s['game'])).fetchall()
 c.close()
 accuracy=round(100*sum(x['correct'] for x in recent)/len(recent),1) if recent else 0.0
 lv=level_for(u['id'],s['game'])
 return {'correct':correct,'score':score,'accuracy':accuracy,'response_time':round(rt,2),'next_level':lv,'message':'Excellent! Next challenge can be harder.' if correct else 'Good try. Let us try again.'}
@app.get('/caregiver',response_class=HTMLResponse)
def caregiver(request:Request):
 u=user(request)
 if not u:return RedirectResponse('/login')
 c=conn();p=c.execute("SELECT * FROM users WHERE role='patient' LIMIT 1").fetchone();a=c.execute('SELECT game,COUNT(*) n,AVG(correct)*100 acc,AVG(response_time) rt,SUM(score) score FROM attempts WHERE user_id=? GROUP BY game',(p['id'],)).fetchall();recent=c.execute('SELECT game,level,correct,response_time,score,created FROM attempts WHERE user_id=? ORDER BY id DESC LIMIT 15',(p['id'],)).fetchall();c.close();return templates.TemplateResponse(request=request,name='caregiver.html',context={'request':request,'patient':p,'attempts':a,'recent':recent})
