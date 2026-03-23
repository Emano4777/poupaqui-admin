import os
import time
import json
import base64
import requests
import cloudinary
import cloudinary.api
from dotenv import load_dotenv

load_dotenv()

# =========================
# CONFIG CLOUDINARY
# =========================
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

# =========================
# CONFIG IMAGEKIT
# =========================
IMAGEKIT_PRIVATE_KEY = os.getenv("IMAGEKIT_PRIVATE_KEY")
IMAGEKIT_UPLOAD_URL = "https://upload.imagekit.io/api/v1/files/upload"
IMAGEKIT_LIST_URL = "https://api.imagekit.io/v1/files"

if not IMAGEKIT_PRIVATE_KEY:
    raise RuntimeError("IMAGEKIT_PRIVATE_KEY não configurada")

def _imagekit_auth_header():
    token = base64.b64encode(f"{IMAGEKIT_PRIVATE_KEY}:".encode()).decode()
    return {
        "Authorization": f"Basic {token}"
    }

def _cloudinary_get_resource(public_id):
    return cloudinary.api.resource(public_id, image_metadata=True)


import os
import time
import json
import base64
import requests
import cloudinary
import cloudinary.api
from dotenv import load_dotenv

load_dotenv()

# =========================
# CONFIG CLOUDINARY
# =========================
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

# =========================
# CONFIG IMAGEKIT
# =========================
IMAGEKIT_PRIVATE_KEY = os.getenv("IMAGEKIT_PRIVATE_KEY")
IMAGEKIT_UPLOAD_URL = "https://upload.imagekit.io/api/v1/files/upload"
IMAGEKIT_LIST_URL = "https://api.imagekit.io/v1/files"

if not IMAGEKIT_PRIVATE_KEY:
    raise RuntimeError("IMAGEKIT_PRIVATE_KEY não configurada")

def _imagekit_auth_header():
    token = base64.b64encode(f"{IMAGEKIT_PRIVATE_KEY}:".encode()).decode()
    return {
        "Authorization": f"Basic {token}"
    }

def _cloudinary_get_resource(public_id):
    return cloudinary.api.resource(public_id, image_metadata=True)

def _imagekit_arquivo_existe_por_nome_e_pasta(file_name, folder_path):
    resp = requests.get(
        IMAGEKIT_LIST_URL,
        headers=_imagekit_auth_header(),
        params={
            "path": folder_path,
            "type": "file",
            "limit": 100,
            "skip": 0
        },
        timeout=60
    )
    resp.raise_for_status()
    files = resp.json()

    for f in files:
        if (f.get("name") or "").strip() == file_name.strip():
            return f
    return None

def _upload_cloudinary_asset_para_imagekit(public_id, folder, tags=None, custom_metadata=None):
    resource = _cloudinary_get_resource(public_id)

    file_url = resource.get("secure_url")
    fmt = (resource.get("format") or "").strip().lower()
    base_name = public_id.split("/")[-1]

    if not fmt:
        fmt = "jpg"

    file_name = f"{base_name}.{fmt}"

    existente = _imagekit_arquivo_existe_por_nome_e_pasta(file_name, folder)
    if existente:
        print(f"[SKIP] Já existe em {folder}: {file_name}")
        return existente

    payload = {
        "file": file_url,
        "fileName": file_name,
        "useUniqueFileName": "false",
        "folder": folder
    }

    if tags:
        payload["tags"] = json.dumps(tags)

    if custom_metadata:
        custom_metadata = {k: v for k, v in custom_metadata.items() if str(v or "").strip()}
        if custom_metadata:
            payload["customMetadata"] = json.dumps(custom_metadata)

    resp = requests.post(
        IMAGEKIT_UPLOAD_URL,
        headers=_imagekit_auth_header(),
        data=payload,
        timeout=120
    )

    if not resp.ok:
        print("\n================= ERRO IMAGEKIT =================")
        print("public_id:", public_id)
        print("file_url:", file_url)
        print("file_name:", file_name)
        print("folder:", folder)
        print("status_code:", resp.status_code)
        print("response_text:", resp.text)
        print("=================================================\n")
        resp.raise_for_status()

    return resp.json()


def _cloudinary_listar_por_tag(tag, max_results=50):
    resources = []
    next_cursor = None

    while True:
        params = {
            "tag": tag,
            "max_results": max_results
        }
        if next_cursor:
            params["next_cursor"] = next_cursor

        result = cloudinary.api.resources_by_tag(**params)
        batch = result.get("resources", [])
        resources.extend(batch)

        next_cursor = result.get("next_cursor")
        if not next_cursor:
            break

    return resources


def _cloudinary_listar_por_prefixo(prefixo="", max_results=100):
    resources = []
    next_cursor = None

    while True:
        params = {
            "type": "upload",
            "max_results": max_results
        }

        if prefixo:
            params["prefix"] = prefixo

        if next_cursor:
            params["next_cursor"] = next_cursor

        result = cloudinary.api.resources(**params)
        batch = result.get("resources", [])
        resources.extend(batch)

        next_cursor = result.get("next_cursor")
        if not next_cursor:
            break

    return resources
def migrar_assets_home():
    logo_public_ids = [
        "f5jacl8k23kajzp50qon"
    ]

    banner_top_public_ids = [
        "y70khnyqdylqcwkfe806"
    ]

    banners_public_ids = [
        "ihm6ipbpibpo3z73vxhk",
        "feoylwbsfviqxxvip0qu",
        "ddetdgswawrtsoprxblh",
    ]

    ok = 0
    erro = 0

    print("\n=== MIGRANDO LOGO ===")
    for public_id in logo_public_ids:
        try:
            result = _upload_cloudinary_asset_para_imagekit(
                public_id=public_id,
                folder="/logo/",
                tags=["logo"]
            )
            print(f"[OK][LOGO] {public_id} -> {result.get('url')}")
            ok += 1
            time.sleep(0.2)
        except Exception as e:
            print(f"[ERRO][LOGO] {public_id}: {e}")
            erro += 1

    print("\n=== MIGRANDO BANNER TOP ===")
    for public_id in banner_top_public_ids:
        try:
            result = _upload_cloudinary_asset_para_imagekit(
                public_id=public_id,
                folder="/site_assets/banner_top/",
                tags=["banner_top"]
            )
            print(f"[OK][BANNER_TOP] {public_id} -> {result.get('url')}")
            ok += 1
            time.sleep(0.2)
        except Exception as e:
            print(f"[ERRO][BANNER_TOP] {public_id}: {e}")
            erro += 1

    print("\n=== MIGRANDO BANNERS DO CARROSSEL ===")
    for i, public_id in enumerate(banners_public_ids, start=1):
        try:
            result = _upload_cloudinary_asset_para_imagekit(
                public_id=public_id,
                folder="/site_assets/banners/",
                tags=["home_banner", "carrossel"]
            )
            print(f"[OK][BANNER_{i}] {public_id} -> {result.get('url')}")
            ok += 1
            time.sleep(0.2)
        except Exception as e:
            print(f"[ERRO][BANNER_{i}] {public_id}: {e}")
            erro += 1

    print(f"\nMigração concluída. OK={ok} | ERRO={erro}")

if __name__ == "__main__":
    migrar_assets_home()
