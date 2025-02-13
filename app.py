from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import cloudinary
import cloudinary.uploader
import cloudinary.api
import json
import os
from PIL import Image

# Configurar a API do Cloudinary
cloudinary.config(
    cloud_name="dizfq460q",
    api_key="218941668123635",
    api_secret="bADJ8clAnP8Ghptg93-I5ZCAVd4"
)

app = Flask(__name__)
app.secret_key = 'segredo123'  # Chave secreta para gerenciar sessões

# Arquivo JSON para armazenar os banners e a logo
DATA_FILE = "/tmp/images.json"

def load_images():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"banners": [], "logo": None, "banner_top": None}  # Estrutura padrão

# Salvar imagens no JSON
def save_images(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    data = load_images()  # Carregar as imagens salvas
    banners = data.get("banners", [])
    logo = data.get("logo", None)
    banner_top = data.get("banner_top", None) 
    return render_template('index.html', banners=banners, logo=logo,banner_top=banner_top)

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
        if 'file' not in request.files or 'image_type' not in request.form:
            error = "Nenhum arquivo enviado ou tipo de imagem inválido."
        else:
            file = request.files['file']
            image_type = request.form['image_type']  # Define se é 'banner', 'banner_top' ou 'logo'

            if file and allowed_file(file.filename):
                try:
                    # Criar uma cópia temporária da imagem para evitar problemas com stream
                    file_path = f"/tmp/{file.filename}"
                    file.save(file_path)

                    # Verifica dimensões da imagem antes do upload
                    image = Image.open(file_path)

                    if image_type == "banner" and image.size != (1312, 302):
                        error = "O banner deve ter exatamente 1312x302 pixels!"
                    elif image_type == "banner_top" and image.size != (1310, 110):
                        error = "O banner principal deve ter 1310x110 pixels!"
                    elif image_type == "logo" and image.size != (2000, 2000):
                        error = "A logo deve ter exatamente 2000x2000 pixels!"
                    else:
                        # Envia a imagem para o Cloudinary
                        upload_result = cloudinary.uploader.upload(file_path)

                        # Pega a URL gerada automaticamente pelo Cloudinary
                        image_url = upload_result['secure_url']

                        # Atualiza as imagens salvas
                        data = load_images()
                        if image_type == "banner":
                            data["banners"].append(image_url)
                        elif image_type == "banner_top":
                            data["banner_top"] = image_url  # Atualiza o banner principal corretamente
                        elif image_type == "logo":
                            data["logo"] = image_url  # Substitui a logo existente

                        save_images(data)  # Atualiza o JSON

                        print(f"Imagem enviada com sucesso: {image_url}")

                except Exception as e:
                    error = f"Erro ao enviar imagem: {str(e)}"

    data = load_images()
    return render_template('admin.html', error=error, banners=data["banners"], banner_top=data.get("banner_top"), logo=data["logo"])

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
