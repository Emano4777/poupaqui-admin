from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import cloudinary
import cloudinary.uploader
import cloudinary.api
import json
import os
import io
from PIL import Image
import time


# Configurar a API do Cloudinary
cloudinary.config(
    cloud_name="dizfq460q",
    api_key="218941668123635",
    api_secret="bADJ8clAnP8Ghptg93-I5ZCAVd4"
)

app = Flask(__name__)
app.secret_key = 'segredo123'  # Chave secreta para gerenciar sessões


def load_images():
    """ Busca imagens no Cloudinary e mantém a estrutura correta. """
    try:
        timestamp = int(time.time())  # Evita cache

        # 🔹 Inicializando as variáveis corretamente
        banner_top = None
        logo = None
        banners = []

        # 🔹 Buscar apenas o banner_top
        result_top = cloudinary.api.resources_by_tag("banner_top", max_results=1)
        if result_top["resources"]:
            banner_top = f"{result_top['resources'][0]['secure_url']}?t={timestamp}"  # Adiciona timestamp

        # 🔹 Buscar apenas a logo
        result_logo = cloudinary.api.resources_by_tag("logo", max_results=1)
        if result_logo["resources"]:
            logo = f"{result_logo['resources'][0]['secure_url']}?t={timestamp}"  # Adiciona timestamp

        # 🔹 Buscar todos os banners normais
        result_banners = cloudinary.api.resources_by_tag("poupAqui", max_results=10)
        for img in result_banners["resources"]:
            tags = img.get("tags", [])

            # 🔹 Adiciona ao carrossel **somente se NÃO for banner_top nem logo**
            if "banner_top" not in tags and "logo" not in tags:
                banners.append(f"{img['secure_url']}?t={timestamp}")

        print(f"✅ Imagens carregadas corretamente: banner_top={banner_top}, logo={logo}, banners={len(banners)}")

        return {
            "banners": banners,  
            "banner_top": banner_top,  
            "logo": logo  
        }
    except Exception as e:
        print(f"❌ Erro ao carregar imagens: {str(e)}")
        return {"banners": [], "banner_top": None, "logo": None}




def delete_old_image(tag):
    """ Deleta todas as imagens antigas associadas a uma tag específica (banner_top ou logo). """
    try:
        result = cloudinary.api.resources_by_tag(tag, max_results=50)
        for img in result["resources"]:
            cloudinary.uploader.destroy(img["public_id"])
            print(f"Imagem antiga removida: {img['public_id']}")
    except Exception as e:
        print(f"Erro ao excluir imagem ({tag}): {e}")

    

def save_images(data):
    os.environ["BANNERS"] = json.dumps(data["banners"])  # Garante que seja uma string JSON válida
    os.environ["LOGO"] = data["logo"] or ""  # Se for None, salva como string vazia
    os.environ["BANNER_TOP"] = data["banner_top"] or ""  # Se for None, salva como string vazia

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    data = load_images()
    
    print(f"🔹 Exibindo index.html: banner_top={data['banner_top']}, logo={data['logo']}, banners={len(data['banners'])}")
    
    return render_template('index.html', 
                           banners=data["banners"], 
                           logo=data["logo"], 
                           banner_top=data["banner_top"], 
                           timestamp=int(time.time()))

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

    if request.method == 'POST':
        if 'file' not in request.files or 'image_type' not in request.form:
            error = "Nenhum arquivo enviado ou tipo de imagem inválido."
        else:
            file = request.files['file']
            image_type = request.form['image_type']

            if file and allowed_file(file.filename):
                try:
                    # Verificar dimensões da imagem
                    image = Image.open(io.BytesIO(file.read()))
                    file.seek(0)  # Resetar o ponteiro do arquivo

                    if image_type == "banner" and image.size != (1312, 302):
                        error = "O banner deve ter exatamente 1312x302 pixels!"
                    elif image_type == "banner_top" and image.size != (1310, 110):
                        error = "O banner principal deve ter 1310x110 pixels!"
                    elif image_type == "logo" and image.size != (2000, 2000):
                        error = "A logo deve ter exatamente 2000x2000 pixels!"
                    else:
                        # Se for banner_top ou logo, excluir o antigo antes de salvar o novo
                        if image_type == "banner_top":
                            delete_old_image("banner_top")
                            upload_result = cloudinary.uploader.upload(file.stream, tags=["banner_top"])
                            print(f"✅ Nova imagem de banner_top enviada: {upload_result['secure_url']}")

                        elif image_type == "logo":
                            delete_old_image("logo")
                            upload_result = cloudinary.uploader.upload(file.stream, tags=["logo"])
                            print(f"✅ Nova logo enviada: {upload_result['secure_url']}")

                        else:  # Banner normal (não precisa excluir)
                            upload_result = cloudinary.uploader.upload(file.stream, tags=["poupAqui"])
                            print(f"✅ Novo banner enviado para carrossel: {upload_result['secure_url']}")

                except Exception as e:
                    error = f"Erro ao enviar imagem: {str(e)}"

    data = load_images()
    return render_template('admin.html', error=error, banners=data["banners"], 
                           banner_top=data["banner_top"], logo=data["logo"])


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
