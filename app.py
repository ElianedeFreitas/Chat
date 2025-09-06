from flask import Flask, request, redirect, session, jsonify, render_template_string, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

app = Flask(__name__)
app.secret_key = "segredo_super_secreto"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

socketio = SocketIO(app, manage_session=False)

DB_NAME = "chat.db"
online_users = set()

# ----------------- ESTILO BASE -----------------
BASE_STYLE = '''
<style>
    body {
        background: #d3d3d3;
        font-family: 'Segoe UI', sans-serif;
        margin: 0; padding: 0;
        font-size: 15px;
    }
    .centered-box {
        background: white;
        max-width: 400px;
        margin: 100px auto;
        padding: 20px;
        border-radius: 6px;
        box-shadow: 0 0 10px rgba(0,0,0,0.2);
        text-align: center;
    }
    input[type=text], input[type=password] {
        width: 90%;
        height: 42px;
        padding: 10px;
        margin: 10px 0;
        border-radius: 4px;
        border: 1px solid #ccc;
        font-size: 15px;
    }
    button {
        background-color: #000;
        color: white;
        border: none;
        padding: 10px 20px;
        margin-top: 10px;
        font-size: 15px;
        border-radius: 4px;
        cursor: pointer;
        transition: background-color 0.3s;
        height: 42px;
    }
    button:hover {
        background-color: #444;
    }
    a {
        color: #000;
        text-decoration: none;
    }
    a:hover {
        text-decoration: underline;
    }
</style>
'''

# ----------------- TELAS -----------------
TEMPLATE_LOGIN = BASE_STYLE + '''
<div class="centered-box">
    <h2>Login</h2>
    <form method="POST">
        Nome:<br>
        <input name="nome" required><br>
        Senha:<br>
        <input type="password" name="senha" required><br>
        <button type="submit">Entrar</button>
    </form>
    <p>Não tem conta? <a href="/cadastro">Cadastre-se</a></p>
</div>
'''

TEMPLATE_CADASTRO = BASE_STYLE + '''
<div class="centered-box">
    <h2>Cadastro</h2>
    <form method="POST">
        Nome:<br>
        <input name="nome" required><br>
        Senha:<br>
        <input type="password" name="senha" required><br>
        <button type="submit">Cadastrar</button>
    </form>
    <p>Já tem conta? <a href="/login">Login</a></p>
</div>
'''

TEMPLATE_HOME = BASE_STYLE + '''
<div style="max-width: 600px; margin: 50px auto; background: white; padding: 20px; border-radius:6px; box-shadow: 0 0 8px rgba(0,0,0,0.1);">
    <h2>Bem-vindo, {{ nome }}!</h2>
    <p><a href="/logout">Sair</a></p>
    <h3>Salas disponíveis:</h3>
    <ul>
        {% for sala in salas %}
            <li><a href="{{ url_for('sala', sala_id=sala[0]) }}">{{ sala[1] }}</a></li>
        {% endfor %}
    </ul>
    <h3>Criar nova sala:</h3>
    <form method="POST" action="/criar_sala">
        <input name="nome_sala" placeholder="Nome da sala" required>
        <button type="submit">Criar</button>
    </form>
</div>
'''

# ----------------- SALA DE CHAT -----------------
TEMPLATE_SALA = BASE_STYLE + '''
<style>
  #container {
    display: flex;
    max-width: 900px;
    margin: 30px auto;
    background: white;
    border-radius: 6px;
    box-shadow: 0 0 10px rgba(0,0,0,0.1);
    height: 520px;
  }
  #chat {
    flex-grow: 1;
    display: flex;
    flex-direction: column;
    padding: 20px;
  }
  #mensagens {
    border: 1px solid #ccc;
    flex-grow: 1;
    overflow-y: auto;
    padding: 10px;
    margin-bottom: 12px;
    font-size: 15px;
    line-height: 1.4em;
  }
  #mensagens p { margin: 4px 0; }
  #mensagens span.time {
    color: #888;
    font-size: 12px;
    margin-left: 5px;
  }
  #input-area {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  #msg, #emoji-picker, #imgUpload, button {
    height: 42px;
    border-radius: 4px;
    border: 1px solid #ccc;
    font-size: 15px;
    padding: 0 10px;
  }
  #msg { flex-grow: 1; }
  button {
    background-color: #000;
    color: white;
    cursor: pointer;
    transition: background-color 0.3s;
    min-width: 80px;
  }
  button:hover { background-color: #444; }
  #online-users {
    width: 220px;
    border-left: 1px solid #ccc;
    padding: 20px;
    overflow-y: auto;
  }
  #online-users h4 { margin-top: 0; }
  #online-users ul { list-style: none; padding-left: 0; }
  #online-users li {
    padding: 5px 0;
    border-bottom: 1px solid #eee;
  }
</style>

<div id="container">
  <div id="chat">
    <h2>Sala: {{ sala_nome }}</h2>
    <p><a href="/">Voltar</a></p>
    <div id="mensagens"></div>
    <div id="input-area">
      <select id="emoji-picker" title="Escolha um emoji">
        <option value="">😊 Emojis</option>
        <option value="😀">😀</option>
        <option value="😂">😂</option>
        <option value="😍">😍</option>
        <option value="😎">😎</option>
        <option value="👍">👍</option>
        <option value="🎉">🎉</option>
        <option value="😢">😢</option>
        <option value="😡">😡</option>
        <option value="🙏">🙏</option>
        <option value="💡">💡</option>
      </select>
      <input type="file" id="imgUpload" accept="image/*">
      <input id="msg" placeholder="Mensagem" autocomplete="off" autofocus>
      <button onclick="enviar()">Enviar</button>
    </div>
  </div>
  <div id="online-users">
    <h4>Usuários Online</h4>
    <ul id="usuarios-online-list"></ul>
  </div>
</div>

<script src="https://cdn.socket.io/4.6.1/socket.io.min.js"></script>
<script>
  const socket = io();

  function addMensagem(msg) {
    const div = document.getElementById('mensagens');
    const p = document.createElement('p');
    if (msg.conteudo.startsWith("data:image")) {
      p.innerHTML = `<b>${msg.usuario}</b> <span class="time">[${msg.tempo}]</span><br>
                     <img src="${msg.conteudo}" style="max-width:200px; border-radius:6px; margin-top:5px;">`;
    } else {
      p.innerHTML = `<b>${msg.usuario}</b> <span class="time">[${msg.tempo}]</span>: ${msg.conteudo}`;
    }
    div.appendChild(p);
    div.scrollTop = div.scrollHeight;
  }

  socket.on('online_users', function(users){
    const list = document.getElementById('usuarios-online-list');
    list.innerHTML = '';
    users.forEach(function(user){
      const li = document.createElement('li');
      li.textContent = user;
      list.appendChild(li);
    });
  });

  socket.on('new_message', function(msg){
    if(msg.sala_id != {{ sala_id }}) return;
    addMensagem(msg);
  });

  function enviar(){
    const input = document.getElementById('msg');
    const conteudo = input.value.trim();
    if(!conteudo) return;
    socket.emit('send_message', {
      usuario: "{{ session['usuario_nome'] }}",
      sala_id: {{ sala_id }},
      conteudo: conteudo
    });
    input.value = '';
  }

  document.getElementById('msg').addEventListener('keydown', function(e){
    if(e.key === 'Enter'){
      e.preventDefault();
      enviar();
    }
  });

  document.getElementById('imgUpload').addEventListener('change', function(){
    const file = this.files[0];
    if(!file) return;
    const reader = new FileReader();
    reader.onload = function(e){
      socket.emit('send_message', {
        usuario: "{{ session['usuario_nome'] }}",
        sala_id: {{ sala_id }},
        conteudo: e.target.result
      });
    }
    reader.readAsDataURL(file);
    this.value = "";
  });

  document.getElementById('emoji-picker').addEventListener('change', function(){
    const input = document.getElementById('msg');
    if(this.value) {
      input.value += this.value;
      this.value = '';
      input.focus();
    }
  });

  socket.emit('join', {usuario: "{{ session['usuario_nome'] }}", sala_id: {{ sala_id }}});

  async function carregarMensagens(){
    const res = await fetch("/api/mensagens/{{ sala_id }}");
    const msgs = await res.json();
    const div = document.getElementById('mensagens');
    div.innerHTML = '';
    msgs.forEach(m => {
      addMensagem({usuario: m.usuario, conteudo: m.mensagem, tempo: m.tempo});
    });
  }
  carregarMensagens();
</script>
'''

# ----------------- BANCO -----------------
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS usuario (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE NOT NULL,
                senha TEXT NOT NULL
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS sala (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE NOT NULL
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS mensagem (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER,
                sala_id INTEGER,
                conteudo TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(usuario_id) REFERENCES usuario(id),
                FOREIGN KEY(sala_id) REFERENCES sala(id)
            )
        ''')

# ----------------- ROTAS -----------------
@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        nome = request.form["nome"].strip()
        senha = request.form["senha"].strip()
        if not nome or not senha:
            return "Preencha todos os campos.<br><a href='/cadastro'>Voltar</a>"

        senha_hash = generate_password_hash(senha)
        try:
            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("INSERT INTO usuario (nome, senha) VALUES (?, ?)", (nome, senha_hash))
                conn.commit()
            return redirect("/login")
        except sqlite3.IntegrityError:
            return "Usuário já existe.<br><a href='/cadastro'>Tente novamente</a>"

    return render_template_string(TEMPLATE_CADASTRO)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        nome = request.form["nome"].strip()
        senha = request.form["senha"].strip()
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT id, senha FROM usuario WHERE nome = ?", (nome,))
            user = c.fetchone()
            if user and check_password_hash(user[1], senha):
                session["usuario_id"] = user[0]
                session["usuario_nome"] = nome
                return redirect("/")
            else:
                return "Usuário ou senha incorretos.<br><a href='/login'>Tente novamente</a>"
    return render_template_string(TEMPLATE_LOGIN)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/", methods=["GET"])
def home():
    if "usuario_id" not in session:
        return redirect("/login")
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT id, nome FROM sala")
        salas = c.fetchall()
    return render_template_string(TEMPLATE_HOME, nome=session["usuario_nome"], salas=salas)

@app.route("/criar_sala", methods=["POST"])
def criar_sala():
    if "usuario_id" not in session:
        return redirect("/login")
    nome_sala = request.form["nome_sala"].strip()
    if not nome_sala:
        return redirect("/")
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        try:
            c.execute("INSERT INTO sala (nome) VALUES (?)", (nome_sala,))
            conn.commit()
        except sqlite3.IntegrityError:
            pass
    return redirect("/")

@app.route("/sala/<int:sala_id>")
def sala(sala_id):
    if "usuario_id" not in session:
        return redirect("/login")
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT nome FROM sala WHERE id = ?", (sala_id,))
        sala_nome = c.fetchone()
        if not sala_nome:
            return "Sala não encontrada"
    return render_template_string(
        TEMPLATE_SALA,
        sala_id=sala_id,
        sala_nome=sala_nome[0]
    )

@app.route("/api/mensagens/<int:sala_id>")
def obter_mensagens(sala_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT mensagem.conteudo, mensagem.timestamp, usuario.nome
            FROM mensagem
            JOIN usuario ON mensagem.usuario_id = usuario.id
            WHERE sala_id = ?
            ORDER BY mensagem.timestamp ASC
        """, (sala_id,))
        mensagens = [{"usuario": row[2], "mensagem": row[0], "tempo": row[1]} for row in c.fetchall()]
        return jsonify(mensagens)

# ----------------- SOCKET.IO -----------------
@socketio.on('join')
def on_join(data):
    usuario = data.get('usuario')
    sala_id = data.get('sala_id')
    if usuario and sala_id:
        join_room(str(sala_id))
        online_users.add(usuario)
        emit('online_users', list(online_users), broadcast=True)

@socketio.on('send_message')
def handle_message(data):
    usuario = data.get('usuario')
    sala_id = data.get('sala_id')
    conteudo = data.get('conteudo')

    if not usuario or not sala_id or not conteudo:
        return

    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM usuario WHERE nome = ?", (usuario,))
        user = c.fetchone()
        if not user:
            return
        user_id = user[0]
        c.execute("""
            INSERT INTO mensagem (usuario_id, sala_id, conteudo) VALUES (?, ?, ?)
        """, (user_id, sala_id, conteudo))
        conn.commit()
        c.execute("SELECT timestamp FROM mensagem WHERE id = last_insert_rowid()")
        timestamp = c.fetchone()[0]

    msg = {"usuario": usuario, "sala_id": sala_id, "conteudo": conteudo, "tempo": timestamp}
    emit('new_message', msg, room=str(sala_id))

@socketio.on('disconnect')
def on_disconnect():
    usuario = session.get('usuario_nome')
    if usuario and usuario in online_users:
        online_users.remove(usuario)
        emit('online_users', list(online_users), broadcast=True)

# ----------------- MAIN -----------------
if __name__ == "__main__":
    init_db()
    socketio.run(app, debug=True)
