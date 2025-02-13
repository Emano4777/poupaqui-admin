from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
import os
from PIL import Image

app = Flask(__name__)
app.secret_key = 'segredo123'  # Chave secreta para gerenciar sessões

UPLOAD_FOLDER = '/tmp/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Criar a pasta "uploads" se não existir (corrige o problema no Vercel)
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    # Garante que a pasta de uploads existe
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    # Lista os banners da pasta uploads
    banners = [
        file for file in os.listdir(UPLOAD_FOLDER) if file.endswith(('.jpg', '.png', '.jpeg'))
    ]

    return render_template('index.html', banners=banners)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        if username == 'admin' and password == 'admin123':  # Usuário e senha fixos
            session['logged_in'] = True
            return redirect(url_for('admin'))
        else:
            return render_template('login.html', error="Credenciais inválidas. Tente novamente.")

    return render_template('login.html')


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('logged_in'):
        return redirect(url_for('login'))  # Redireciona para login se não estiver autenticado

    error = None

    if request.method == 'POST':
        if 'file' not in request.files:
            error = "Nenhum arquivo enviado."
        else:
            file = request.files['file']
            banner_type = request.form.get('banner_type')

            if file and allowed_file(file.filename):
                filename = f"{banner_type}.jpg"  # Nome fixo para substituir os banners
                file_path = os.path.join(UPLOAD_FOLDER, filename)

                try:
                    # Verifica as dimensões da imagem
                    file.seek(0)  # Resetar ponteiro antes de abrir a imagem
                    image = Image.open(file)
                    if image.size != (1312, 302):
                        error = "A imagem deve ter exatamente 1312x302 pixels!"
                    else:
                        file.seek(0)  # Resetar ponteiro antes de salvar
                        file.save(file_path)
                except Exception as e:
                    error = f"Erro ao processar imagem: {str(e)}"

    return render_template('admin.html', error=error)


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))


@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    file_path = os.path.join(UPLOAD_FOLDER, filename)

    # Se o arquivo não existir, retorna erro 404
    if not os.path.exists(file_path):
        return "Arquivo não encontrado", 404

    return send_from_directory(UPLOAD_FOLDER, filename)



if __name__ == '__main__':
    app.run(debug=True)
