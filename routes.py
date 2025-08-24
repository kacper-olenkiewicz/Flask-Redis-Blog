from app import app
from flask import render_template , request , session , redirect , url_for
from flask_redis import FlaskRedis
from datetime import datetime
import json
from werkzeug.utils import secure_filename
import os

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.config['REDIS_URL'] = 'redis://redis:6379/0'  
redis_client = FlaskRedis(app)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/zaloguj', methods=['GET','POST'])
def logowanie():
    error = None
    if request.method == 'POST':
        username = request.form['user']
        password = request.form['password']
        haslo = redis_client.hgetall(f"user:{username}")
        if not haslo:
            error="Nie ma takiego uzytkownika"
        else:
            haslo = {k.decode('utf-8'):v.decode('utf-8') for k,v in haslo.items()}
            if password == haslo.get('password'):
                role = haslo.get('role', 'user')
                if role == 'user':
                    session['username']=username
                    session['role'] = role
                    return redirect(url_for('stro'))
                elif role == 'admin':
                    session['username']=username
                    session['role'] = role
                    return redirect(url_for('admin_panel'))
            else:
                error = "Zle haslo"
    return render_template('header/zaloguj.html',error=error)

@app.route('/rejestracja', methods=['GET','POST'])
def reje():
    error = None
    if request.method == 'POST':
        username = request.form['user']
        password = request.form['password']
        email = request.form['email']
        if redis_client.get(f"user:{username}"):
            error = "Uzytkownik juz istnieje"
        else:
            redis_client.hset(f"user:{username}",mapping={
                "password": password,
                "email": email,
                "role": "user"
            })
            return redirect(url_for('logowanie'))
    return render_template('header/rejestracja.html', error=error)

@app.route('/StronaU')
def stro():
    if 'username' not in session:
        return redirect(url_for('logowanie'))
    naz = session.get('username')
    id = redis_client.lrange("posts", 0, -1)
    id = [pid.decode('utf-8') for pid in id]
    posty = []
    for a in id:
        p = redis_client.hgetall(f"post:{a}")
        if not p:
            continue  
        dek_decoded = {k.decode('utf-8'): v.decode('utf-8') for k, v in p.items()}
        dek_decoded['id']=a
        posty.append(dek_decoded)
    return render_template('uzyt/glowna.html', naz=naz,posty=posty)

@app.route('/wyloguj')
def wyloguj():
    session.clear()
    return redirect(url_for('home'))

@app.route('/znajomi')
def znajomi():
    if 'username' not in session:
        return redirect(url_for('logowanie'))
    naz = session.get('username')
    znajomi = redis_client.smembers(f"friends:{naz}")
    znajomi = [f.decode('utf-8') for f in znajomi]
    return render_template('znaj/lista.html', znajomi=znajomi)

@app.route('/usun_znajomego/<znaj>')
def usun_znaj(znaj):
    if 'username' not in session:
        return redirect(url_for('logowanie'))
    naz = session['username']
    redis_client.srem(f"friends:{naz}", znaj)
    redis_client.srem(f"friends:{znaj}", naz)
    return redirect(url_for('znajomi'))

@app.route('/dodajZnaj', methods=['GET','POST'])
def dodajZnaj():
    error = None
    dodano = None
    if 'username' not in session:
        return redirect(url_for('logowanie'))
    if request.method == 'POST':
        naz = session.get('username')
        znajomi = redis_client.smembers(f"friends:{naz}")
        znajomi = [f.decode('utf-8') for f in znajomi]
        dodaj = request.form['user']
        if dodaj == naz:
            error = "Nie mozesz dodac samego siebie!"
            return render_template('znaj/dodawanie.html',error=error)
        if redis_client.exists(f"user:{dodaj}"):
            if dodaj in znajomi:
                error = "Juz jestescie znajomymi."
            else:
                redis_client.sadd(f"friends:{naz}",dodaj)
                redis_client.sadd(f"friends:{dodaj}",naz)
                dodano = "Dodano Znajomego!"
        else:
            error = "Nie ma takiego uzytkownika!"
    return render_template('znaj/dodawanie.html',error=error,dodano=dodano)

@app.route('/nowyPost', methods=['POST','GET'])
def post():
    if 'username' not in session:
        return redirect(url_for('logowanie'))
    if request.method == 'POST':
        naz = session.get('username')
        tytul = request.form['tytul']
        tresc = request.form['tresc']
        data =  datetime.now().strftime('%Y-%m-%d %H:%M')
        f = request.files.get('img')
        if f and f.filename:
            filename= datetime.now().strftime("%Y%m%d%H%M%S_")+secure_filename(f.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            f.save(filepath)
        else:
            filename = None
        post_id = redis_client.incr('next_post_id')
        redis_client.hset(f"post:{post_id}",mapping={
            "Autor": naz,
            "Tytul": tytul,
            "Tresc": tresc,
            "Data": data,
            "img": filename if filename else ""
        })
        redis_client.lpush("posts",post_id)
        redis_client.lpush(f"posts:{naz}",post_id)
        return redirect(url_for('poka'))
    return render_template('posty/nowyP.html')
@app.route('/mojePosty')
def poka():
    if 'username' not in session:
        return redirect(url_for('logowanie'))
    naz = session['username']
    ind = redis_client.lrange(f"posts:{naz}", 0, -1)
    ind = [pid.decode('utf-8') for pid in ind]
    p = []
    for a in ind:
        dek = redis_client.hgetall(f"post:{a}")
        if not dek:
            continue  
        dek_decoded = {k.decode('utf-8'): v.decode('utf-8') for k, v in dek.items()}
        dek_decoded['id']=a
        p.append(dek_decoded)
    return render_template('posty/wyswietlP.html', post=p)
@app.route('/admin')
def admin_panel():
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('logowanie',error = "Nie jestes adminem"))
    post_id = redis_client.lrange("posts",0,-1)
    post_id = [pid.decode('utf-8') for pid in post_id]

    posty = []
    for a in post_id:
        p = redis_client.hgetall(f"post:{a}")
        if not p:
            continue
        p = {k.decode('utf-8'): v.decode('utf-8') for k,v in p.items()}
        p['id']=a
        posty.append(p)
    return render_template('admin/admin_panel.html',posty=posty)
@app.route('/usun_Post/<post_id>/<naz>')
def usun_post(post_id, naz):
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('logowanie', error="Nie jestes adminem"))
    post = redis_client.hgetall(f"post:{post_id}")
    post = {k.decode('utf-8'): v.decode('utf-8') for k, v in post.items()}
    img_filename = post.get("img", "")
    if img_filename:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], img_filename)
        if os.path.exists(filepath):
            os.remove(filepath)
    redis_client.delete(f"post:{post_id}")
    redis_client.lrem("posts", 0, post_id)
    redis_client.lrem(f"posts:{naz}", 0, post_id)
    return redirect(url_for('admin_panel'))
@app.route('/wiadomosci/<znaj>', methods= ['GET','POST'])
def wiadomosc(znaj):
    if 'username' not in session:
        return redirect(url_for('logowanie'))
    naz = session['username']
    error = None
    wys , dos = sorted([naz,znaj])
    klucz = f"chat:{wys}:{dos}"
    if request.method == 'POST':
        wiad = request.form['wiad']
        if not wiad or wiad.strip() == '':
            error = "Wiadomosc nie moze byc pusta"
        else:
            wiadomosc = {
                "od": naz,
                "do": znaj,
                "text": wiad,
                "czas": datetime.now().strftime('%Y-%m-%d %H:%M')
            }
            redis_client.rpush(klucz,json.dumps(wiadomosc))
            if naz != znaj:
                redis_client.sadd(f"powiadomienia:{znaj}", f"Nowa wiadomość od {naz}")
    chat = redis_client.lrange(klucz,-30,-1)
    chat = [json.loads(m.decode('utf-8')) for m in chat]
    return render_template('chat/chat.html', wiadomosci=chat,error=error,odbiorca=znaj)
@app.route('/edytujPost/<id>', methods=['GET','POST'])
def edytujPost(id):
    if 'username' not in session:
        return redirect(url_for('logowanie'))
    post = redis_client.hgetall(f"post:{id}")
    post = {k.decode('utf-8'): v.decode('utf-8') for k, v in post.items()}
    if request.method == 'POST':
        aut = session['username']
        Tresc = request.form['tresc']
        Tytul = request.form['tytul']
        Data = datetime.now().strftime('%Y-%m-%d %H:%M')
        f = request.files.get('img')  
        if f and f.filename:
            old_img = post.get("img", "")
            if old_img:
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], old_img)
                if os.path.exists(old_path):
                    os.remove(old_path)
            filename = datetime.now().strftime("%Y%m%d%H%M%S_") + secure_filename(f.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            f.save(filepath)
        else:
            filename = None

        if not Tresc:
            Tresc = post['Tresc']
        if not Tytul:
            Tytul = post['Tytul']
        redis_client.hset(f"post:{id}", mapping={
            "Autor": aut,
            "Tytul": Tytul,
            "Tresc": Tresc,
            "Data": Data,
            "img": filename if filename else post.get("img", "")
        })
        return redirect(url_for('poka'))
    return render_template('posty/edytujP.html', post=post)
@app.route('/uPost/<id>')
def uPost(id):
    if 'username' not in session:
        return redirect(url_for('logowanie'))
    naz = session['username']
    post = redis_client.hgetall(f"post:{id}")
    post = {k.decode('utf-8'): v.decode('utf-8') for k, v in post.items()}
    img_filename = post.get("img", "")
    if img_filename:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], img_filename)
        if os.path.exists(filepath):
            os.remove(filepath)
    redis_client.delete(f"post:{id}")
    redis_client.lrem("posts", 0, id)
    redis_client.lrem(f"posts:{naz}", 0, id)
    return redirect(url_for('poka'))
@app.route('/komentarz/<id>', methods=['GET','POST'])
def kom(id):
    if 'username' not in session:
        return redirect(url_for('logowanie'))
    naz = session['username']
    post =  redis_client.hgetall(f"post:{id}")
    post = {k.decode('utf-8'):v.decode('utf-8') for k,v in post.items()}
    tyt = redis_client.hget(f"post:{id}", "Tytul").decode('utf-8')
    post_author = redis_client.hget(f"post:{id}", "Autor").decode('utf-8')
    if request.method == 'POST':
        kom = request.form['kom']
        data = datetime.now().strftime('%Y-%m-%d %H:%M')
        comment_id = redis_client.incr("next_comment_id")
        redis_client.hset(f"comment:{comment_id}", mapping={
            "author": naz,
            "text": kom,
            "data": data
        })
        redis_client.rpush(f"comments:{id}", comment_id)
        return redirect(url_for('stro'))
    com = redis_client.lrange(f"comments:{id}",0,-1)
    com = [a.decode('utf-8') for a in com]
    comment = []
    for c in com:
        temp = redis_client.hgetall(f"comment:{c}")
        temp = {k.decode('utf-8'):v.decode('utf-8') for k,v in temp.items()}
        comment.append(temp)
    if post_author != naz:
        redis_client.sadd(f"powiadomienia:{post_author}", f"Dodano komentarz do postu pod tytulem:{tyt}")
    return render_template('posty/dodajKom.html',comments=comment,post=post)
@app.route('/zobKom/<id>')
def zobKom(id):
    if 'username' not in session:
        return redirect(url_for('logowanie'))
    post =  redis_client.hgetall(f"post:{id}")
    post = {k.decode('utf-8'):v.decode('utf-8') for k,v in post.items()}
    com = redis_client.lrange(f"comments:{id}",0,-1)
    com = [a.decode('utf-8') for a in com]
    comment = []
    for c in com:
        temp = redis_client.hgetall(f"comment:{c}")
        temp = {k.decode('utf-8'):v.decode('utf-8') for k,v in temp.items()}
        comment.append(temp)
    return render_template('posty/mojeKom.html',comments=comment,post=post)
@app.route('/Powiadomienia')
def Powiadomienia():
    if 'username' not in session:
        return redirect(url_for('logowanie'))
    naz = session['username']
    pow = redis_client.smembers(f"powiadomienia:{naz}")
    p = [a.decode('utf-8') for a in pow]
    redis_client.delete(f"powiadomienia:{naz}")
    return render_template('uzyt/pow.html', pow=p)
