from flask import Flask, render_template, send_from_directory,request, redirect, url_for, session, jsonify, flash,send_file
import cloudinary
import cloudinary.uploader
import cloudinary.api
import json
import os
import io
from PIL import Image
import time
import re
import psycopg2
from math import radians, sin, cos, sqrt, atan2
import requests

CACHE_FILE = "cep_coordinates_cache.json"


# Configurar a API do Cloudinary
cloudinary.config(
    cloud_name="dizfq460q",
    api_key="218941668123635",
    api_secret="bADJ8clAnP8Ghptg93-I5ZCAVd4"
)


def get_db_connection():
    return psycopg2.connect("postgresql://postgres:Poupaqui123@406279.hstgr.cloud:5432/postgres")


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


def obter_regiao(ip):
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}")
        dados = response.json()

        if dados["status"] == "success":
            return f"{dados['city']}, {dados['regionName']}, {dados['country']}"
        else:
            return "Desconhecido"
    except Exception as e:
        print("Erro ao obter região:", e)
        return "Erro na geolocalização"

# Rota protegida para registrar cliques
@app.route('/registrar-clique', methods=['POST'])
def registrar_clique():
    data = request.json
    botao = data.get('botao', 'desconhecido')
    link = data.get('link', 'sem link')
    ip_usuario = request.remote_addr  # Obtém o IP do usuário
    regiao = obter_regiao(ip_usuario)  # Obtém a região com base no IP

    print("📌 Recebendo clique:", botao, link, "| IP:", ip_usuario, "| Região:", regiao)  # 🔍 Debug para verificar se os dados chegam corretamente

    conn = get_db_connection()
    if not conn:
        print("❌ Falha ao conectar ao banco de dados!")
        return jsonify({"error": "Falha na conexão com o banco"}), 500

    cursor = conn.cursor()

    try:
        # Criar tabela, incluindo IP e região
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS public.cliques (
                id SERIAL PRIMARY KEY,
                botao TEXT NOT NULL,
                link TEXT,
                ip VARCHAR(45),
                regiao TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Tabela verificada/criada com sucesso.")  # 🔍 Log para saber se a criação da tabela ocorreu corretamente

        # Inserir o clique no banco, incluindo IP e região
        cursor.execute("INSERT INTO public.cliques (botao, link, ip, regiao) VALUES (%s, %s, %s, %s)", 
                       (botao, link, ip_usuario, regiao))
        conn.commit()
        print("✅ Clique registrado no banco!")  # 🔍 Log para confirmar que o commit foi feito

        return jsonify({"message": "Clique registrado com sucesso", "regiao": regiao}), 200
    except Exception as e:
        conn.rollback()
        print("❌ Erro ao registrar clique:", e)
        return jsonify({"error": "Erro ao registrar clique"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/ads.txt')
def ads_txt():
    return send_file('ads.txt', mimetype='text/plain')

@app.route('/sobre-nos')
def sobre_nos():
    data = load_store_images() 
    return render_template('sobrenos.html', lojas=data["stores"], logo=data["logo"])

@app.route("/implantacao")
def implantacao():
    if not session.get("admin_logged_in") and not session.get("implantacao_logged_in"):
        flash("Você precisa estar logado para acessar a implantação.", "danger")
        return redirect(url_for("login"))

    data = load_store_images()
    etapas = get_implantacao_etapas()
    return render_template("implantacao.html", logo=data["logo"], etapas=etapas)


@app.route("/admin/implantacao")
def admin_implantacao():
    if not session.get("logged_in"):
        flash("Você precisa estar logado para acessar esta página.", "danger")
        return redirect(url_for("login"))

    data = load_store_images()
    etapas = get_implantacao_etapas()
    return render_template("admin_implantacao.html", logo=data["logo"], etapas=etapas)


def autenticar_usuario_implantacao(usuario, senha):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT usuario, role, ativo
        FROM public.usuarios_implantacao
        WHERE usuario = %s AND senha = %s
        LIMIT 1
    """, (usuario, senha))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return None
    if row[2] is not True:
        return None

    return {"usuario": row[0], "role": row[1]}


@app.route("/admin/implantacao/edit/<int:etapa_id>", methods=["GET", "POST"])
def edit_etapa_implantacao(etapa_id):
    if not session.get("logged_in"):
        flash("Você precisa estar logado para acessar esta página.", "danger")
        return redirect(url_for("login"))

    data = load_store_images()
    logo = data["logo"]

    conn = get_db_connection()
    cur = conn.cursor()

    # Buscar etapa
    cur.execute("""
        SELECT id, numero, titulo, descricao, cor
        FROM public.implantacao_etapas
        WHERE id = %s
    """, (etapa_id,))
    row = cur.fetchone()

    if not row:
        cur.close()
        conn.close()
        flash("Etapa não encontrada!", "danger")
        return redirect(url_for("admin_implantacao"))

    etapa = {"id": row[0], "numero": row[1], "titulo": row[2], "descricao": row[3], "cor": row[4]}

    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        descricao = request.form.get("descricao", "").strip()
        cor = request.form.get("cor", "yellow").strip()

        if not titulo or not descricao:
            flash("Preencha título e descrição.", "danger")
            return render_template("edit_etapa_implantacao.html", logo=logo, etapa=etapa)

        cur.execute("""
            UPDATE public.implantacao_etapas
            SET titulo = %s, descricao = %s, cor = %s, atualizado_em = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (titulo, descricao, cor, etapa_id))
        conn.commit()

        cur.close()
        conn.close()

        flash("Etapa atualizada com sucesso!", "success")
        return redirect(url_for("admin_implantacao"))

    cur.close()
    conn.close()
    return render_template("edit_etapa_implantacao.html", logo=logo, etapa=etapa)


def get_implantacao_etapas():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, numero, titulo, descricao, cor
        FROM public.implantacao_etapas
        ORDER BY numero ASC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    etapas = []
    for r in rows:
        etapas.append({
            "id": r[0],
            "numero": r[1],
            "titulo": r[2],
            "descricao": r[3],
            "cor": r[4] or "yellow"
        })
    return etapas


@app.route('/vitnatu')
def vitnatu():
    data = load_store_images() 
    return render_template('vitnatu.html', lojas=data["stores"], logo=data["logo"])

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
        response = requests.get(url_brasilapi, timeout=10)
        response.raise_for_status()

        try:
            data = response.json()
        except ValueError:
            print(f"❌ Resposta inválida da BrasilAPI para CEP {cep}")
            return None, None

        if "state" in data and "city" in data:
            cidade = data["city"]
            estado = data["state"]
            print(f"🔍 Buscando coordenadas da cidade: {cidade}, {estado}...")

            # Busca coordenadas no OpenStreetMap
            url_osm = f"https://nominatim.openstreetmap.org/search?q={cidade},+{estado},+Brasil&format=json"
            resp_osm = requests.get(url_osm, timeout=5)
            data_osm = resp_osm.json()

            if isinstance(data_osm, list) and len(data_osm) > 0:
                latitude = float(data_osm[0]["lat"])
                longitude = float(data_osm[0]["lon"])
                print(f"✅ Coordenadas da cidade {cidade}: ({latitude}, {longitude})")

                cep_cache[cep] = {"lat": latitude, "lon": longitude}
                save_cache()
                return latitude, longitude

    except requests.exceptions.Timeout:
        print(f"⚠️ Timeout na BrasilAPI para {cep}.")
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

import math


def calcular_distancia_km(lat1, lon1, lat2, lon2):
    """ Calcula a distância em km entre duas coordenadas geográficas. """
    R = 6371  # Raio médio da Terra em km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


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

from geopy.distance import geodesic


@app.route("/buscar_loja", methods=["POST"])
def buscar_loja():
    data = request.get_json()
    cep_usuario = data.get("cep", "").replace("-", "").strip()

    if not cep_usuario or len(cep_usuario) < 5:
        return jsonify({"error": "CEP inválido"}), 400

    lojas = load_store_images()["stores"]

    # Coordenadas do CEP do usuário
    lat_usuario, lon_usuario = get_coordinates_from_cep(cep_usuario)
    lojas_com_distancia = []

    if lat_usuario and lon_usuario:
        for loja in lojas:
            cep_loja = extract_cep(loja.get("endereco", ""))
            if not cep_loja:  
                continue  # Pula lojas sem CEP no endereço

            lat_loja, lon_loja = get_coordinates_from_cep(cep_loja)
            if lat_loja and lon_loja:
                distancia = geodesic((lat_usuario, lon_usuario), (lat_loja, lon_loja)).km
                lojas_com_distancia.append({**loja, "distancia_km": round(distancia, 2)})

        if lojas_com_distancia:
            lojas_ordenadas = sorted(lojas_com_distancia, key=lambda l: l["distancia_km"])
            lojas_proximas = [loja for loja in lojas_ordenadas if loja["distancia_km"] <= 50]
            if lojas_proximas:
                return jsonify({"lojas": lojas_proximas, "modo": "preciso"})

    # 🔹 Fallback — busca por cidade, mas só com lojas que tenham CEP no endereço
    cidade_usuario = get_city_from_cep(cep_usuario)
    if cidade_usuario:
        cidade_usuario = cidade_usuario.lower().strip()
        lojas_cidade = []
        for loja in lojas:
            cep_loja = extract_cep(loja.get("endereco", ""))
            if cep_loja and cidade_usuario in loja.get("cidade", "").lower():
                lojas_cidade.append({**loja, "distancia_km": None})

        if lojas_cidade:
            return jsonify({"lojas": lojas_cidade, "modo": "aproximado"})

    return jsonify({"error": "Nenhuma loja encontrada para este CEP"}), 404



import locale


from pyuca import Collator

@app.route('/lojas')
def lojas():
    data = load_store_images()

    collator = Collator()
    data["stores"] = sorted(
        data["stores"],
        key=lambda x: collator.sort_key(x.get('cidade', '').split('/')[0].strip())
    )

    return render_template('lojas.html', lojas=data["stores"], logo=data["logo"])


@app.route('/admin/lojas', methods=['GET', 'POST'])
def admin_lojas():
     # 🔹 Verifica se o usuário está logado antes de permitir o acesso
    if not session.get('logged_in'):
        flash('Você precisa estar logado para acessar esta página.', 'danger')
        return redirect(url_for('login'))
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

        # ✅ Admin do sistema (edição)
        if username == 'admin' and password == 'admin123':
            session['admin_logged_in'] = True
            session['role'] = 'admin'
            session['user'] = 'admin'
            return redirect(url_for('admin_implantacao'))

        # ✅ Usuários de implantação (acesso restrito)
        user_impl = autenticar_usuario_implantacao(username, password)
        if user_impl:
            session['implantacao_logged_in'] = True
            session['role'] = user_impl['role']  # 'implantacao'
            session['user'] = user_impl['usuario']
            return redirect(url_for('implantacao'))

        return render_template('login.html', error="Credenciais inválidas. Tente novamente.")

    return render_template('login.html', error="Credenciais inválidas. Tente novamente.", logo=load_store_images()["logo"])

from flask import send_file, redirect, url_for, session
import io
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib import colors

@app.route("/admin/implantacao/pdf")
def download_implantacao_pdf():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    etapas = get_implantacao_etapas()  # [{id, numero, titulo, descricao, cor}, ...]
    etapas = sorted(etapas, key=lambda x: int(x["numero"]))

    buffer = io.BytesIO()
    page_w, page_h = landscape(A4)

    c = canvas.Canvas(buffer, pagesize=(page_w, page_h))

    # ====== CONFIG VISUAL ======
    margin_x = 30
    top_line_y = page_h - 18

    # Linha superior
    c.setStrokeColor(colors.black)
    c.setLineWidth(1)
    c.line(margin_x, top_line_y, page_w - margin_x, top_line_y)

    # Grid: 5 colunas na primeira linha, 5 na segunda, 4 na terceira
    rows_spec = [5, 5, 4]

    gap_x = 22
    gap_y = 18
    box_h = 160
    start_y = page_h - 40 - box_h

    title_font = "Helvetica-Bold"
    body_font = "Helvetica"
    title_size = 10.5
    body_size = 8.5

    red = colors.HexColor("#D61F1F")
    yellow = colors.HexColor("#F2C300")

    def circle_color(numero):
        return yellow if int(numero) % 2 == 1 else red

    def number_color_bg(bg):
        return colors.HexColor("#D61F1F") if bg == yellow else colors.HexColor("#F2C300")

    def draw_wrapped_text(text, x, y, max_width, line_height, font_name, font_size, max_lines=None):
        """
        Desenha texto quebrando linha por largura usando o ReportLab.
        y é o topo.
        Retorna o y final.
        Se max_lines for definido, limita a quantidade de linhas.
        """
        c.setFont(font_name, font_size)
        words = (text or "").split()
        line = ""
        lines = []

        for w in words:
            test = (line + " " + w).strip()
            if c.stringWidth(test, font_name, font_size) <= max_width:
                line = test
            else:
                if line:
                    lines.append(line)
                line = w
        if line:
            lines.append(line)

        if max_lines is not None:
            lines = lines[:max_lines]

        yy = y
        for ln in lines:
            c.drawString(x, yy, ln)
            yy -= line_height
        return yy

    # ====== DESENHAR OS BLOCOS ======
    etapa_idx = 0
    for row_i, cols in enumerate(rows_spec):
        col_w = (page_w - 2 * margin_x - (cols - 1) * gap_x) / cols
        y = start_y - row_i * (box_h + gap_y)

        for col_i in range(cols):
            if etapa_idx >= len(etapas):
                break

            e = etapas[etapa_idx]
            etapa_idx += 1

            x = margin_x + col_i * (col_w + gap_x)

            # Círculo + número
            bg = circle_color(e["numero"])
            num_color = number_color_bg(bg)

            circle_r = 18
            circle_x = x + circle_r + 2
            circle_y = y + box_h - circle_r - 8

            c.setFillColor(bg)
            c.setStrokeColor(bg)
            c.circle(circle_x, circle_y, circle_r, stroke=1, fill=1)

            c.setFillColor(num_color)
            c.setFont(title_font, 14)
            num_txt = str(e["numero"])
            tw = c.stringWidth(num_txt, title_font, 14)
            c.drawString(circle_x - tw / 2, circle_y - 5, num_txt)

            # ===== TÍTULO =====
            title_x = x + (circle_r * 2) + 10
            title_y = y + box_h - 18

            c.setFillColor(colors.black)
            titulo = (e.get("titulo") or "").upper()

            title_end_y = draw_wrapped_text(
                titulo,
                title_x,
                title_y,
                max_width=col_w - (circle_r * 2) - 14,
                line_height=13,
                font_name=title_font,
                font_size=title_size,
                max_lines=3  # evita invadir a descrição
            )

            # ===== DESCRIÇÃO (agora DENTRO do loop) =====
            desc_x = x + 2
            desc_start_y = title_end_y - 8

            c.setFillColor(colors.HexColor("#333333"))

            # Limita linhas para não invadir a próxima linha do grid
            draw_wrapped_text(
                e.get("descricao") or "",
                desc_x,
                desc_start_y,
                max_width=col_w - 6,
                line_height=11,
                font_name=body_font,
                font_size=body_size,
                max_lines=7
            )

    c.showPage()
    c.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="implantacao_poupaqui.pdf",
        mimetype="application/pdf"
    )


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
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
