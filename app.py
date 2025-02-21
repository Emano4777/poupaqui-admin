from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import cloudinary
import cloudinary.uploader
import cloudinary.api
import json
import os
import io
from PIL import Image
import time
import re


# Configurar a API do Cloudinary
cloudinary.config(
    cloud_name="dizfq460q",
    api_key="218941668123635",
    api_secret="bADJ8clAnP8Ghptg93-I5ZCAVd4"
)

app = Flask(__name__)
app.secret_key = 'segredo123'  # Chave secreta para gerenciar sessões

def load_store_images():
    """ Busca as imagens das lojas no Cloudinary e garante que os metadados sejam carregados corretamente. """
    try:
        timestamp = int(time.time())
        stores = []
        logo = None

        # 🔹 Buscar imagens com a tag 'lojas_poupAqui', garantindo que os metadados sejam carregados
        result = cloudinary.api.resources_by_tag("lojas_poupAqui", max_results=120, context=True)

        for img in result["resources"]:
            context = img.get("context", {}).get("custom", {})  # Obtém os metadados corretamente
            endereco = context.get("endereco", "Endereço não informado")
            google_maps_url = f"https://www.google.com/maps/search/?api=1&query={endereco.replace(' ', '+')}" if endereco != "Endereço não informado" else "#"
            cep = context.get("cep", "").replace("-", "").strip() 
            store = {
                "url": f"{img['secure_url']}?t={timestamp}",
                "public_id": img["public_id"],
                "cidade": context.get("cidade", "Cidade Teste"),
                "endereco": endereco,
                "telefone": context.get("telefone", "(99) 99999-9999"),
                "whatsapp": context.get("whatsapp", "https://wa.me/5599999999999"),
                "google_maps": google_maps_url,
                "cep": cep
            }
            stores.append(store)

        # 🔹 Ordena as lojas em ordem alfabética pelo nome da cidade
        stores.sort(key=lambda loja: loja["cidade"].lower())

        # 🔹 Buscar a logo apenas uma vez, fora do loop
        result_logo = cloudinary.api.resources_by_tag("logo", max_results=1)
        if result_logo["resources"]:
            logo = f"{result_logo['resources'][0]['secure_url']}?t={timestamp}"  # Adiciona timestamp para evitar cache

        print("📸 Imagens carregadas e ordenadas:", stores)  # 🔹 Debug
        print(f"🎨 Logo carregada: {logo}")
        
        return {"stores": stores, "logo": logo}
    
    except Exception as e:
        print(f"❌ Erro ao carregar imagens das lojas: {e}")
        return {"stores": [], "logo": None}

@app.route('/buscar_loja', methods=['POST'])
def buscar_loja():
    """ Rota para buscar a loja mais próxima pelo CEP informado. """
    cep_digitado = request.json.get("cep", "").replace("-", "").replace(" ", "").strip()

    if not cep_digitado:
        return jsonify({"error": "CEP não informado."}), 400

    lojas = load_store_images().get("stores", [])  # 🔹 Garante que estamos pegando a lista de lojas

    loja_mais_proxima = None

    for loja in lojas:
        endereco_loja = loja.get("endereco", "").strip()

        # 🔹 Usa regex para tentar capturar o CEP no final do endereço
        match = re.search(r"(\d{5}-?\d{3})$", endereco_loja)

        if match:
            cep_loja = match.group(1).replace("-", "").strip()  # 🔹 Remove qualquer hífen

            if cep_loja[:5] == cep_digitado[:5]:  # 🔹 Compara os primeiros 5 dígitos
                loja_mais_proxima = loja
                break  # Para a busca ao encontrar a primeira loja correspondente

    if loja_mais_proxima:
        return jsonify(loja_mais_proxima)
    else:
        return jsonify({"error": "Nenhuma loja encontrada para esse CEP."}), 404

    
@app.route('/lojas')
def lojas():
    data = load_store_images()  # Carrega imagens das lojas + logo
    return render_template('lojas.html', lojas=data["stores"], logo=data["logo"])


@app.route('/admin/lojas', methods=['GET', 'POST'])
def admin_lojas():
    if request.method == 'POST':
        file = request.files.get('file')
        cidade = request.form.get("cidade")
        endereco = request.form.get("endereco")
        telefone = request.form.get("telefone")
        whatsapp = request.form.get("whatsapp")

        if not file or file.filename == '':
            flash('Selecione uma imagem para upload.', 'danger')
            return redirect(request.url)

        try:
            # 🔹 Upload da imagem
            upload_result = cloudinary.uploader.upload(file, tags=["lojas_poupAqui"])

            # 🔹 Define os metadados manualmente após o upload
            cloudinary.api.update(upload_result["public_id"], context={
                "cidade": cidade,
                "endereco": endereco,
                "telefone": telefone,
                "whatsapp": whatsapp
            })

            print("Metadados Atualizados:", cidade, endereco, telefone, whatsapp)  # 🔹 Debug

            flash("Imagem enviada com sucesso!", "success")
        except Exception as e:
            flash(f"Erro ao enviar imagem: {e}", "danger")

    # 🔹 Busca as lojas e já garante que elas estejam ordenadas
    lojas = load_store_images()
    
    return render_template('admin_lojas.html', lojas=lojas["stores"], logo=lojas["logo"])

@app.route('/admin/lojas/delete/<public_id>')
def delete_loja(public_id):
    try:
        cloudinary.uploader.destroy(public_id)
        flash("Imagem removida com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao excluir imagem: {e}", "danger")

    return redirect(url_for('admin_lojas'))


@app.route('/admin/lojas/edit/<public_id>', methods=['GET', 'POST'])
def edit_loja(public_id):
    lojas_data = load_store_images()  # Agora retorna um dicionário {"stores": [...], "logo": "URL"}
    lojas = lojas_data["stores"]  # Acessa apenas a lista de lojas
    
    loja = next((l for l in lojas if l["public_id"] == public_id), None)

    if not loja:
        flash("Loja não encontrada!", "danger")
        return redirect(url_for('admin_lojas'))

    if request.method == 'POST':
        cidade = request.form.get("cidade")
        endereco = request.form.get("endereco")
        telefone = request.form.get("telefone")
        whatsapp = request.form.get("whatsapp")
        file = request.files.get('file')  # Novo upload de imagem

        try:
            # Se uma nova imagem foi enviada, faz upload e deleta a antiga
            if file and file.filename != '':
                new_upload = cloudinary.uploader.upload(file, tags=["lojas_poupAqui"])

                # Deletar a imagem antiga do Cloudinary
                cloudinary.uploader.destroy(public_id)

                # Atualizar o ID da imagem para o novo
                public_id = new_upload["public_id"]

                # Atualizar metadados da nova imagem
                cloudinary.api.update(public_id, context={
                    "cidade": cidade,
                    "endereco": endereco,
                    "telefone": telefone,
                    "whatsapp": whatsapp
                })

                loja["url"] = new_upload["secure_url"]  # Atualiza a URL para exibição imediata
            else:
                # Apenas atualiza os metadados da imagem existente
                cloudinary.api.update(public_id, context={
                    "cidade": cidade,
                    "endereco": endereco,
                    "telefone": telefone,
                    "whatsapp": whatsapp
                })

            flash("Informações da loja atualizadas com sucesso!", "success")
            return redirect(url_for('admin_lojas'))
        except Exception as e:
            flash(f"Erro ao atualizar informações: {e}", "danger")

    return render_template('edit_loja.html', loja=loja)


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
