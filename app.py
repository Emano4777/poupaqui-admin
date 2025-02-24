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
from math import radians, sin, cos, sqrt, atan2
import requests

CACHE_FILE = "cep_coordinates_cache.json"



# Configurar a API do Cloudinary
cloudinary.config(
    cloud_name="dizfq460q",
    api_key="218941668123635",
    api_secret="bADJ8clAnP8Ghptg93-I5ZCAVd4"
)

app = Flask(__name__)
app.secret_key = 'segredo123'  # Chave secreta para gerenciar sessões

CACHE_FILE = "cep_coordinates_cache.json"
STORES_FILE = "stores_data.json"  # Novo arquivo para guardar as lojas carregadas

# 🔹 Carregar cache de coordenadas do CEP se existir
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r") as f:
        cep_cache = json.load(f)
else:
    cep_cache = {}

def save_cache():
    """ Salva o cache de coordenadas no arquivo JSON """
    with open(CACHE_FILE, "w") as f:
        json.dump(cep_cache, f, indent=4)

        

def get_coordinates_from_cep(cep):
    """ Obtém latitude e longitude a partir de um CEP, utilizando cache e fallback. """
    cep = cep.replace("-", "").strip()

    # 🔹 Verifica se já está no cache
    if cep in cep_cache:
        print(f"✅ [CACHE] Coordenadas do CEP {cep}: {cep_cache[cep]}")
        return cep_cache[cep]["lat"], cep_cache[cep]["lon"]

    # 🔹 Primeira tentativa com OpenStreetMap (Nominatim)
    url_osm = f"https://nominatim.openstreetmap.org/search?q={cep}&countrycodes=BR&format=json"
    headers = {"User-Agent": "PoupAquiBot/1.0 (contato@poupAqui.com)"}

    try:
        response = requests.get(url_osm, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, list) and len(data) > 0:
            latitude = float(data[0]["lat"])
            longitude = float(data[0]["lon"])
            print(f"✅ Coordenadas do CEP {cep}: ({latitude}, {longitude})")

            # 🔹 Adicionamos ao cache e salvamos
            cep_cache[cep] = {"lat": latitude, "lon": longitude}
            save_cache()
            return latitude, longitude
        else:
            print(f"⚠️ Primeira tentativa falhou para {cep}, tentando fallback...")
            return get_coordinates_from_brasilapi(cep)

    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao buscar coordenadas: {e}")
        return None, None
    
def get_city_from_cep(cep):
    """ Obtém a cidade a partir do CEP usando a BrasilAPI ou OpenStreetMap como fallback. """
    url_brasilapi = f"https://brasilapi.com.br/api/cep/v1/{cep}"

    try:
        response = requests.get(url_brasilapi, timeout=5)
        response.raise_for_status()
        data = response.json()

        if "city" in data:
            print(f"✅ Cidade encontrada via BrasilAPI: {data['city']}")
            return data["city"]

    except requests.exceptions.RequestException:
        print(f"⚠️ BrasilAPI falhou, tentando OpenStreetMap...")

    # 🔹 Se BrasilAPI falhar, tenta via OpenStreetMap
    url_osm = f"https://nominatim.openstreetmap.org/search?q={cep}&countrycodes=BR&format=json"
    
    try:
        response = requests.get(url_osm, timeout=5)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, list) and len(data) > 0:
            cidade = data[0]["display_name"].split(",")[1].strip()
            print(f"✅ Cidade encontrada via OpenStreetMap: {cidade}")
            return cidade

    except requests.exceptions.RequestException:
        print(f"❌ Falha ao obter cidade para o CEP {cep}")

    return None


def get_coordinates_from_brasilapi(cep):
    """ Obtém informações do CEP via BrasilAPI e tenta converter para coordenadas. """
    url_brasilapi = f"https://brasilapi.com.br/api/cep/v1/{cep}"

    try:
        response = requests.get(url_brasilapi, timeout=10)  # ⏳ Aumentamos o timeout
        response.raise_for_status()
        data = response.json()

        if "state" in data and "city" in data:
            cidade = data["city"]
            estado = data["state"]
            print(f"🔍 Buscando coordenadas da cidade: {cidade}, {estado}...")

            # 🔹 Busca coordenadas da cidade como fallback
            url_osm = f"https://nominatim.openstreetmap.org/search?q={cidade},+{estado},+Brasil&format=json"
            response = requests.get(url_osm, timeout=5)
            data_osm = response.json()

            if isinstance(data_osm, list) and len(data_osm) > 0:
                latitude = float(data_osm[0]["lat"])
                longitude = float(data_osm[0]["lon"])
                print(f"✅ Coordenadas da cidade {cidade}: ({latitude}, {longitude})")

                # 🔹 Adicionamos ao cache
                cep_cache[cep] = {"lat": latitude, "lon": longitude}
                save_cache()
                return latitude, longitude

    except requests.exceptions.Timeout:
        print(f"⚠️ Timeout na BrasilAPI para {cep}. Usando fallback de cidade cadastrada...")

    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao buscar BrasilAPI: {e}")

    return None, None

def extract_cep(endereco):
    """ Extrai o CEP do endereço se ele estiver presente. """
    match = re.search(r"(\d{5}-?\d{3})", endereco)
    if match:
        return match.group(1).replace("-", "").strip()
    return None


def extract_city(endereco):
    """ Extrai a cidade do endereço no formato correto. """
    padrao = r",\s*([^,]+)\s*-\s*[A-Z]{2}"  # Captura a cidade antes do estado (ex: Adamantina - SP)
    match = re.search(padrao, endereco)
    return match.group(1).strip().lower() if match else "desconhecido"


def load_store_images():
    """ Busca imagens das lojas no Cloudinary e garante que os metadados sejam carregados corretamente. """
    try:
        timestamp = int(time.time())
        stores = []
        logo = None

        # 🔹 Buscar imagens com a tag 'lojas_poupAqui', garantindo que os metadados sejam carregados
        result = cloudinary.api.resources_by_tag("lojas_poupAqui", max_results=120, context=True)

        for img in result["resources"]:
            context = img.get("context", {}).get("custom", {})
            endereco = context.get("endereco", "Endereço não informado")
            google_maps_url = f"https://www.google.com/maps/search/?api=1&query={endereco.replace(' ', '+')}" if endereco != "Endereço não informado" else "#"
            cep = context.get("cep", "").replace("-", "").strip()
            cidade = context.get("cidade", "").strip()

            if not cidade:
                cidade = extract_city(endereco)  # 🔹 Se a cidade não estiver nos metadados, extrai do endereço
            
            store = {
                "url": f"{img['secure_url']}?t={timestamp}",
                "public_id": img["public_id"],
                "cidade": cidade,
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
            logo = f"{result_logo['resources'][0]['secure_url']}?t={timestamp}"

        print("📸 Imagens carregadas e ordenadas:", stores)
        print(f"🎨 Logo carregada: {logo}")
        
        return {"stores": stores, "logo": logo}
    
    except Exception as e:
        print(f"❌ Erro ao carregar imagens das lojas: {e}")
        return {"stores": [], "logo": None}


def haversine(lat1, lon1, lat2, lon2):
    """ Calcula a distância entre dois pontos geográficos usando a Fórmula de Haversine """
    R = 6371  # Raio da Terra em KM
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    return R * c  # Retorna a distância em KM

@app.route('/buscar_loja', methods=['POST'])
def buscar_loja():
    """ Rota para buscar a loja mais próxima pelo CEP informado, priorizando busca por cidade. """
    cep_digitado = request.json.get("cep", "").replace("-", "").replace(" ", "").strip()

    if not cep_digitado:
        return jsonify({"error": "CEP não informado."}), 400

    data = load_store_images()
    lojas = data.get("stores", [])

    if not lojas:
        return jsonify({"error": "Nenhuma loja cadastrada."}), 404

    # 🔹 Obtém a cidade pelo CEP
    cidade_usuario = get_city_from_cep(cep_digitado)

    if not cidade_usuario:
        return jsonify({"error": "Cidade não encontrada para o CEP informado."}), 404
    
    cidade_usuario = cidade_usuario.lower().strip()

    # 🔍 Debug: Exibir todas as cidades encontradas nas lojas
    cidades_lojas = set(loja["cidade"].lower().strip() for loja in lojas)
    print(f"🔍 Buscando lojas na cidade: {cidade_usuario}")
    print(f"🏢 Cidades encontradas nas lojas: {cidades_lojas}")

    # 🔹 Filtra as lojas que pertencem à cidade
    lojas_cidade = [loja for loja in lojas if cidade_usuario in loja["cidade"].lower()]

    if not lojas_cidade:
        print(f"❌ Nenhuma loja encontrada na cidade: {cidade_usuario}")
        return jsonify({
        "error": "Nenhuma loja encontrada nesta cidade.",
        "message": f"Nenhuma loja encontrada em {cidade_usuario}. <a href='/lojas'>Clique aqui</a> para conferir todas as nossas lojas."
    }), 404

    print(f"🏪 Total de lojas encontradas em {cidade_usuario}: {len(lojas_cidade)}")

    # 🔹 Retorna apenas a primeira loja (para evitar erro no JS)
    loja_mais_proxima = lojas_cidade[0]

    print(f"📦 Retornando loja: {loja_mais_proxima}")  # Debug

    return jsonify(loja_mais_proxima)



@app.route('/lojas')
def lojas():
    data = load_store_images()  # Carrega imagens das lojas + logo
    return render_template('lojas.html', lojas=data["stores"], logo=data["logo"])



@app.route('/admin/lojas', methods=['GET', 'POST'])
def admin_lojas():
    if request.method == 'POST':
        file = request.files.get('file')
        cidade = request.form.get("cidade").strip()
        endereco = request.form.get("endereco").strip()
        telefone = request.form.get("telefone").strip()
        whatsapp = request.form.get("whatsapp").strip()
        cep = extract_cep(endereco)  # 🔹 Extrai o CEP do endereço automaticamente

        if not file or file.filename == '':
            flash('Selecione uma imagem para upload.', 'danger')
            return redirect(request.url)

        try:
            # 🔹 Upload da imagem
            upload_result = cloudinary.uploader.upload(file, tags=["lojas_poupAqui"])

            # 🔹 Define os metadados corretamente após o upload
            cloudinary.api.update(upload_result["public_id"], context={
                "cidade": cidade,
                "endereco": endereco,
                "telefone": telefone,
                "whatsapp": whatsapp,
                "cep": cep  # 🔹 Agora o CEP também é salvo nos metadados
            })

            print("Metadados Atualizados:", cidade, endereco, telefone, whatsapp, cep)

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
        result_top = cloudinary.api.resources_by_tag("banner_top", max_results=3)
        if result_top["resources"]:
            banner_top = f"{result_top['resources'][0]['secure_url']}?t={timestamp}"  # Adiciona timestamp

        # 🔹 Buscar apenas a logo
        result_logo = cloudinary.api.resources_by_tag("logo", max_results=3)
        if result_logo["resources"]:
            logo = f"{result_logo['resources'][0]['secure_url']}?t={timestamp}"  # Adiciona timestamp

        # 🔹 Buscar todos os banners normais
        result_banners = cloudinary.api.resources_by_tag("poupAqui", max_results=120)
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
        result = cloudinary.api.resources_by_tag(tag, max_results=120)
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
