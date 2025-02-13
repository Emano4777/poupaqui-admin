from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import cloudinary
import cloudinary.uploader
import cloudinary.api
import json
import os

# Configurar a API do Cloudinary
cloudinary.config(
    cloud_name="dizfq460q",
    api_key="218941668123635",
    api_secret="bADJ8clAnP8Ghptg93-I5ZCAVd4"
)

app = Flask(__name__)
app.secret_key = 'segredo123'  # Chave secreta para gerenciar sessões

# Arquivo JSON para armazenar os banners enviados
BANNERS_FILE = "banners.json"

# Carregar os banners salvos no JSON (corrigido para evitar erros em arquivos vazios)
def load_banners():
    if os.path.exists(BANNERS_FILE):
        try:
            with open(BANNERS_FILE, "r") as f:
                banners = json.load(f)
                return banners if isinstance(banners, list) else []  # Garante que seja uma lista
        except json.JSONDecodeError:
            return []  # Se o arquivo estiver corrompido, retorna lista vazia
    return []

# Salvar os banners no JSON
def save_banners(banners):
    with open(BANNERS_FILE, "w") as f:
        json.dump(banners, f, indent=4)  # Indentado para melhor legibilidade

@app.route('/')
def index():
    banners = load_banners()  # Carregar os banners do JSON
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
        return redirect(url_for('login'))

    error = None
    image_url = None

    if request.method == 'POST':
        if 'file' not in request.files:
            error = "Nenhum arquivo enviado."
        else:
            file = request.files['file']

            if file:
                try:
                    # Envia a imagem para o Cloudinary
                    upload_result = cloudinary.uploader.upload(file)

                    # Pega a URL gerada automaticamente pelo Cloudinary
                    image_url = upload_result.get('secure_url')

                    if image_url:  # Se a URL for válida, salva no JSON
                        banners = load_banners()
                        banners.append(image_url)
                        save_banners(banners)  # Atualiza o JSON

                        print(f"Imagem enviada com sucesso: {image_url}")
                    else:
                        error = "Erro ao obter URL da imagem."

                except Exception as e:
                    error = f"Erro ao enviar imagem: {str(e)}"

    banners = load_banners()
    return render_template('admin.html', error=error, image_url=image_url, banners=banners)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)