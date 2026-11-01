"""
Carregamento e tratamento dos CSVs da loja.
"""
import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

PASTA_DADOS = Path(__file__).parent / "data"

# Nas categorias Baixos (2), Baterias (3) e Teclados (4) a descrição não bate com o nome
# do produto. Ex: "Music Man Bass 1X" está descrito como "Fender Jazz Bass".
# Para o agente não passar informação errada, a descrição dessas categorias é ignorada.
CATEGORIAS_COM_DESCRICAO_ERRADA = [2, 3, 4]


def normalizar(texto):
    """Deixa o texto em minúsculo e sem acento, para facilitar a busca."""
    if not isinstance(texto, str):
        return ""
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def so_digitos(texto):
    """Remove tudo que não é número. Usado para comparar telefones."""
    return re.sub(r"\D", "", str(texto))


def ler_csv(nome):
    return pd.read_csv(PASTA_DADOS / f"desafio_tecnico_ai_eng - {nome}.csv")


def carregar_produtos():
    """Junta produtos + categoria + promoção ativa em uma tabela só."""
    produtos = ler_csv("products")
    categorias = ler_csv("categories")
    promocoes = ler_csv("promotions")

    categorias = categorias[["category_id", "name"]].rename(columns={"name": "categoria"})
    produtos = produtos.merge(categorias, on="category_id", how="left")

    # specs vem como texto JSON (e com formatação diferente entre linhas), então converto para dict
    produtos["specs"] = produtos["specs"].apply(lambda s: json.loads(s) if isinstance(s, str) else {})

    produtos["description"] = produtos["description"].fillna("")
    produtos.loc[produtos["category_id"].isin(CATEGORIAS_COM_DESCRICAO_ERRADA), "description"] = ""

    # A tabela de promoções não tem datas, então só considero as marcadas como ativas.
    # Se um produto tiver mais de uma ativa, fica a de maior desconto (promoções não acumulam).
    ativas = promocoes[promocoes["is_active"] == 1]
    ativas = ativas.sort_values("discount_percent", ascending=False).drop_duplicates("product_id")
    ativas = ativas[["product_id", "discount_percent", "description"]].rename(
        columns={"discount_percent": "desconto", "description": "promocao"}
    )
    produtos = produtos.merge(ativas, on="product_id", how="left")

    # coluna auxiliar só para a busca por texto
    produtos["texto_busca"] = (
        produtos["name"] + " " + produtos["categoria"] + " " + produtos["description"]
    ).apply(normalizar)

    return produtos


def carregar_pedidos():
    """Retorna as tabelas de pedidos, itens dos pedidos e clientes."""
    pedidos = ler_csv("orders")
    itens = ler_csv("order_items")
    clientes = ler_csv("customers")

    # pedidos que ainda não foram enviados não têm rastreio nem previsão
    for coluna in ["tracking_code", "estimated_delivery", "notes"]:
        pedidos[coluna] = pedidos[coluna].fillna("")

    # deixo e-mail e telefone num formato fácil de comparar com o que o cliente digitar
    clientes["email"] = clientes["email"].str.strip().str.lower()
    clientes["telefone_digitos"] = clientes["phone"].apply(so_digitos)

    return pedidos, itens, clientes


def listar_categorias():
    return ler_csv("categories")["name"].tolist()
