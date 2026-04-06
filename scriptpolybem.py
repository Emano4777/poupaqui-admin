import pandas as pd

# ========= CAMINHOS =========
ARQ_COTACAO = "COTAÇÃO NOVA BASE.xlsx"
ARQ_POLYBEM = "POLYBEMATUALIZADA.xlsx"
SAIDA = "POLYBEM_itens_faltantes_para_cotacao.xlsx"

# ========= FUNÇÃO NORMALIZAR EAN =========
def normalize_ean(x):
    try:
        return str(int(x))
    except:
        return str(x).strip()

# ========= LER DADOS =========
print("Lendo cotação...")
cotacao = pd.read_excel(ARQ_COTACAO, usecols=["EAN"])

print("Lendo polybem...")
polybem = pd.read_excel(ARQ_POLYBEM)

# ========= NORMALIZAR =========
cotacao["EAN_norm"] = cotacao["EAN"].apply(normalize_ean)

# Detectar colunas automaticamente
def find_col(df, palavras):
    for col in df.columns:
        if any(p in col.lower() for p in palavras):
            return col
    return None

ean_poly = find_col(polybem, ["ean", "barra", "codigo"])
desc_poly = find_col(polybem, ["descr", "produto", "nome"])
lab_poly = find_col(polybem, ["lab", "fabric", "marca"])
preco_poly = find_col(polybem, ["preco", "valor"])

polybem["EAN_norm"] = polybem[ean_poly].apply(normalize_ean)

# ========= FILTRAR FALTANTES =========
faltantes = polybem[~polybem["EAN_norm"].isin(cotacao["EAN_norm"])].copy()

# ========= CLASSIFICAÇÃO =========
def classificar(lab):
    lab = str(lab).upper()
    if "GENERIC" in lab:
        return "Genérico"
    elif "SIMILAR" in lab:
        return "Similar"
    else:
        return "Varejo"

faltantes["Classificação"] = faltantes[lab_poly].apply(classificar)

# ========= MONTAR SAÍDA =========
df_out = pd.DataFrame({
    "EAN": faltantes["EAN_norm"],
    "Produto": faltantes[desc_poly],
    "Classificação": faltantes["Classificação"],
    "Lab": faltantes[lab_poly],
    "Preço POLYBEM": faltantes[preco_poly],
    "fabric": "POLYBEM"
})

# ========= SALVAR =========
df_out.to_excel(SAIDA, index=False)

print(f"✅ Finalizado! Total de itens faltantes: {len(df_out)}")