"""
Ferramentas (tools) que o agente pode chamar.

Cada ferramenta é uma função Python comum que devolve um dict.
As contas (promoção, PIX, parcelamento, prazos) são feitas aqui e não pelo LLM,
porque modelos pequenos erram bastante em aritmética e datas.
No final do arquivo ficam as descrições das ferramentas no formato que o LLM entende.
"""
import csv
import os
from datetime import date, datetime
from pathlib import Path

import pandas as pd

import busca
import dados
import politicas
import seguranca

PRODUTOS = dados.carregar_produtos()
TEXTOS_BUSCA = PRODUTOS["texto_busca"].tolist()
VOCABULARIO = busca.montar_vocabulario(TEXTOS_BUSCA)
PEDIDOS, ITENS, CLIENTES = dados.carregar_pedidos()
CATEGORIAS = dados.listar_categorias()
SECOES_POLITICAS = politicas.carregar_secoes()
# regras de devolução que vão junto com o pedido (seções 4.1 e 4.2 do manual)
REGRAS_ARREPENDIMENTO = politicas.extrair_subsecao(SECOES_POLITICAS["trocas_e_devolucoes"], "4.1")
REGRAS_DEFEITO = politicas.extrair_subsecao(SECOES_POLITICAS["trocas_e_devolucoes"], "4.2")

PASTA_ATENDIMENTOS = Path(__file__).parent / "atendimentos"

# máximo de produtos devolvidos por busca, para não estourar o contexto do modelo
# e para a resposta não virar uma lista gigante no chat
LIMITE_RESULTADOS = 8

STATUS_PEDIDO = {
    "pending": "pendente (pedido recebido, aguardando processamento)",
    "confirmed": "confirmado (em separação, ainda não foi enviado)",
    "shipped": "enviado (a caminho)",
    "delivered": "entregue",
    "cancelled": "cancelado",
}

FORMAS_PAGAMENTO = {
    "pix": "PIX",
    "debit": "cartão de débito",
    "boleto": "boleto bancário",
}


def hoje():
    """Data usada como 'hoje'. Pode ser fixada no .env (DATA_REFERENCIA) para testes."""
    data_fixa = os.getenv("DATA_REFERENCIA")
    if data_fixa:
        return date.fromisoformat(data_fixa)
    return date.today()


def formatar_reais(valor):
    """1234.5 -> 'R$ 1.234,50'"""
    texto = f"{valor:,.2f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def formatar_data(data_iso):
    """'2026-02-28' -> '28/02/2026'"""
    return date.fromisoformat(str(data_iso)).strftime("%d/%m/%Y")


def traduzir_pagamento(codigo):
    # no CSV o crédito vem como "credit_6x", "credit_12x"...
    if codigo.startswith("credit_"):
        return f"cartão de crédito em {codigo.replace('credit_', '')}"
    return FORMAS_PAGAMENTO.get(codigo, codigo)


def calcular_parcelamento(valor):
    """
    Maior número de parcelas sem juros permitido, seguindo a seção 3.1 do manual:
    até 3x com parcela mínima de R$ 50, de 4x a 6x mínimo R$ 80 e de 7x a 12x mínimo R$ 100.
    """
    parcelas = 1
    for vezes in range(2, 13):
        if vezes <= 3:
            minimo = 50
        elif vezes <= 6:
            minimo = 80
        else:
            minimo = 100

        if valor / vezes >= minimo:
            parcelas = vezes

    return parcelas, round(valor / parcelas, 2)


def situacao_produto(produto):
    if produto["status"] == "discontinued":
        return "descontinuado (não faz mais parte do catálogo)"
    if produto["status"] == "coming_soon":
        return "em breve (ainda não está à venda)"
    if produto["stock_quantity"] <= 0:
        return "esgotado no momento"
    if produto["stock_quantity"] <= 2:
        return "disponível (últimas unidades)"
    return "disponível"


def montar_produto(produto, detalhado):
    """Transforma uma linha da tabela no dict que vai para o LLM."""
    preco = float(produto["price_brl"])
    item = {
        "nome": produto["name"],
        "categoria": produto["categoria"],
        "situacao": situacao_produto(produto),
        "preco": formatar_reais(preco),
    }

    # só mando descrição e specs quando são poucos resultados, para a resposta não ficar enorme
    if detalhado:
        if produto["description"]:
            item["descricao"] = produto["description"]
        item["especificacoes"] = produto["specs"]

    if pd.notna(produto["desconto"]):
        preco_final = round(preco * (1 - produto["desconto"] / 100), 2)
        item["promocao_ativa"] = f"{produto['promocao']} - {int(produto['desconto'])}% de desconto"
        item["preco_promocional"] = formatar_reais(preco_final)
        item["pix"] = "o desconto de 5% do PIX não vale junto com promoção"
    else:
        preco_final = preco
        item["preco_no_pix"] = formatar_reais(preco * 0.95) + " (5% de desconto)"

    parcelas, valor_parcela = calcular_parcelamento(preco_final)
    if parcelas > 1:
        item["parcelamento"] = f"até {parcelas}x de {formatar_reais(valor_parcela)} sem juros"
    else:
        item["parcelamento"] = "somente à vista"

    return item


def buscar_produtos(texto=None, categoria=None, preco_maximo=None, apenas_promocao=False):
    resultado = PRODUTOS.copy()
    resultado["preco_final"] = resultado["price_brl"] * (1 - resultado["desconto"].fillna(0) / 100)

    if categoria:
        resultado = resultado[resultado["categoria"].apply(dados.normalizar) == dados.normalizar(categoria)]

    correcoes = {}
    if texto:
        if busca.busca_de_acessorio(texto):
            return {"mensagem": "A loja não vende acessórios (cordas avulsas, palhetas, cabos, cases, "
                                "pedais, amplificadores). Trabalhamos só com instrumentos musicais."}

        # troca sinônimos e corrige erros de digitação ("takamini" -> "takamine")
        termos, correcoes = busca.preparar_termos(texto, TEXTOS_BUSCA, VOCABULARIO)

        # cada palavra encontrada vale 1 ponto; ficam só os produtos com mais pontos.
        # Assim "Takamine GD20" traz só o GD20 e não todos os Takamine.
        if termos:
            pontos = resultado["texto_busca"].apply(lambda t: sum(p in t for p in termos))
            if pontos.max() > 0:
                resultado = resultado[pontos == pontos.max()]
            else:
                resultado = resultado.iloc[0:0]

    if preco_maximo:
        resultado = resultado[resultado["preco_final"] <= float(preco_maximo)]

    # o modelo às vezes manda "true" como texto
    if str(apenas_promocao).lower() == "true":
        resultado = resultado[resultado["desconto"].notna()]

    if resultado.empty:
        resposta = {"mensagem": "Nenhum produto encontrado com esses filtros."}
        # Testando "tem promoção de Black Friday?", o modelo inventou um filtro de categoria,
        # não achou nada e disse que a loja não tinha nenhuma promoção (tem 4). Se a busca era
        # de promoções, mostro as que existem na loja.
        if str(apenas_promocao).lower() == "true" and (texto or categoria or preco_maximo):
            todas = buscar_produtos(apenas_promocao=True)
            resposta["mensagem"] = "Nenhuma promoção com esses filtros, mas existem promoções ativas em outros produtos."
            resposta["promocoes_ativas_na_loja"] = todas["produtos_disponiveis"]
            resposta["campanhas_ativas"] = todas["campanhas_ativas"]
            resposta["aviso_campanhas"] = todas["aviso_campanhas"]
        return resposta

    # Separo disponíveis e indisponíveis em listas diferentes. Quando vinha tudo junto,
    # o modelo às vezes oferecia produto esgotado como se estivesse disponível.
    tem_estoque = (resultado["status"] == "active") & (resultado["stock_quantity"] > 0)
    disponiveis = resultado[tem_estoque].sort_values("preco_final")
    indisponiveis = resultado[~tem_estoque]

    detalhado = len(resultado) <= 3
    resposta = {
        "total_disponiveis": len(disponiveis),
        "produtos_disponiveis": [montar_produto(linha, detalhado) for _, linha in disponiveis.head(LIMITE_RESULTADOS).iterrows()],
    }
    # avisa o modelo quando a busca corrigiu algo, para ele poder dizer "você quis dizer..."
    if correcoes:
        resposta["busca_entendida_como"] = " ".join(termos)
    if len(disponiveis) > LIMITE_RESULTADOS:
        resposta["aviso"] = (
            f"Mostrando só os {LIMITE_RESULTADOS} mais baratos. "
            "Pergunte ao cliente o que ele prefere (tipo, marca, faixa de preço) para filtrar melhor."
        )
    if not indisponiveis.empty:
        resposta["produtos_indisponiveis"] = [
            {"nome": linha["name"], "situacao": situacao_produto(linha)} for _, linha in indisponiveis.iterrows()
        ]

    # Se o cliente procurou um produto que não está disponível, já mando alternativas.
    # Testando, o modelo só perguntava se o cliente queria alternativas em vez de buscar.
    if disponiveis.empty and not indisponiveis.empty:
        resposta["alternativas_disponiveis"] = buscar_alternativas(indisponiveis.iloc[0])

    # Testando, o modelo chamou "Oferta Especial" de Black Friday, então deixo explícito
    # quais campanhas estão ativas de verdade.
    if str(apenas_promocao).lower() == "true":
        campanhas = sorted(disponiveis["promocao"].dropna().unique())
        resposta["campanhas_ativas"] = campanhas
        resposta["aviso_campanhas"] = (
            f"Só estas campanhas estão ativas agora: {', '.join(campanhas)}. "
            "Qualquer outra campanha (Black Friday, Aniversário da Loja, Semana do Músico etc.) NÃO está ativa."
        )

    return resposta


def buscar_alternativas(produto, quantidade=3):
    """Produtos disponíveis da mesma categoria e com preço parecido (30% para mais ou para menos)."""
    preco = produto["price_brl"]
    parecidos = PRODUTOS[
        (PRODUTOS["category_id"] == produto["category_id"])
        & (PRODUTOS["status"] == "active")
        & (PRODUTOS["stock_quantity"] > 0)
        & (PRODUTOS["price_brl"].between(preco * 0.7, preco * 1.3))
    ].copy()
    # os de preço mais próximo primeiro
    parecidos["diferenca"] = (parecidos["price_brl"] - preco).abs()
    parecidos = parecidos.sort_values("diferenca").head(quantidade)
    return [montar_produto(linha, detalhado=False) for _, linha in parecidos.iterrows()]


def consultar_pedido(numero_pedido, email_ou_telefone):
    try:
        numero = int(str(numero_pedido).strip().lstrip("#"))
    except ValueError:
        return {"erro": "Número de pedido inválido. Peça o número ao cliente."}

    pedido = PEDIDOS[PEDIDOS["order_id"] == numero]
    if pedido.empty:
        return {"erro": f"Não existe pedido com o número {numero}."}
    pedido = pedido.iloc[0]
    cliente = CLIENTES[CLIENTES["customer_id"] == pedido["customer_id"]].iloc[0]

    # LGPD: só mostro o pedido se o e-mail ou telefone informado for do dono do pedido
    contato = str(email_ou_telefone).strip().lower()
    digitos = dados.so_digitos(contato)
    confere_email = contato == cliente["email"]
    confere_telefone = len(digitos) >= 8 and (
        cliente["telefone_digitos"].endswith(digitos) or digitos.endswith(cliente["telefone_digitos"])
    )
    if not (confere_email or confere_telefone):
        return {"erro": "O e-mail/telefone informado não confere com o cadastro do pedido. "
                        "Por segurança não é possível mostrar os dados."}

    itens = ITENS[ITENS["order_id"] == numero].merge(PRODUTOS[["product_id", "name"]], on="product_id", how="left")

    resposta = {
        "numero_pedido": numero,
        "primeiro_nome_cliente": cliente["name"].split()[0],
        "data_do_pedido": formatar_data(pedido["order_date"]),
        "status": STATUS_PEDIDO.get(pedido["status"], pedido["status"]),
        "itens": [f"{linha.quantity}x {linha.name}" for linha in itens.itertuples()],
        "total": formatar_reais(pedido["total_brl"]),
        "forma_de_pagamento": traduzir_pagamento(pedido["payment_method"]),
    }

    if pedido["tracking_code"]:
        resposta["codigo_rastreio"] = pedido["tracking_code"]
    if pedido["notes"]:
        resposta["observacao"] = pedido["notes"]

    if pedido["estimated_delivery"]:
        previsao = date.fromisoformat(pedido["estimated_delivery"])
        resposta["previsao_de_entrega"] = formatar_data(previsao)

        if pedido["status"] == "shipped":
            if previsao < hoje():
                resposta["atrasado"] = f"sim, a previsão de entrega passou há {(hoje() - previsao).days} dias"
            # Escrevo bem explícito porque, testando, o modelo entendeu que o prazo já tinha acabado
            resposta["prazos"] = {
                "arrependimento (7 dias após receber)": (
                    "AINDA NÃO COMEÇOU: o cliente ainda não recebeu o produto. "
                    "Ele pode desistir da compra em até 7 dias depois que receber."
                ),
            }

        if pedido["status"] == "delivered":
            # não temos a data real de recebimento, então uso a previsão de entrega como aproximação
            dias_recebido = (hoje() - previsao).days
            dias_compra = (hoje() - date.fromisoformat(pedido["order_date"])).days
            resposta["dias_desde_o_recebimento_aprox"] = dias_recebido
            resposta["prazos"] = {
                "arrependimento (7 dias após receber)": "dentro do prazo" if dias_recebido <= 7 else "fora do prazo",
                "troca por defeito na loja (30 dias após a compra)": "dentro do prazo" if dias_compra <= 30 else "fora do prazo",
                "garantia legal (90 dias após receber)": "dentro do prazo" if dias_recebido <= 90 else "fora do prazo",
            }

    # Testando, o modelo não chamava a política de trocas depois de consultar o pedido,
    # então as regras de devolução que valem para o pedido já vão junto aqui.
    if pedido["status"] in ("shipped", "delivered"):
        resposta["condicoes_de_devolucao"] = REGRAS_ARREPENDIMENTO
        if pedido["status"] == "delivered":
            resposta["troca_por_defeito"] = REGRAS_DEFEITO
        resposta["proximos_passos"] = (
            "Se o cliente quiser desistir ou devolver, explique TODAS as condições de 'condicoes_de_devolucao' "
            f"(o reembolso volta para: {resposta['forma_de_pagamento']})."
        )
    else:
        resposta["proximos_passos"] = (
            "Se o cliente quiser trocar ou devolver, chame consultar_politicas com o assunto "
            "trocas_e_devolucoes e explique as condições."
        )

    if "atrasado" in resposta:
        resposta["proximos_passos"] += " O pedido está atrasado: ofereça encaminhar para a equipe com encaminhar_atendente."

    return resposta


def consultar_politicas(assunto):
    texto = SECOES_POLITICAS.get(assunto)
    if texto is None:
        return {"erro": f"Assunto inválido. Use um destes: {', '.join(SECOES_POLITICAS)}"}
    return {"assunto": assunto, "texto": texto}


def encaminhar_atendente(motivo, nome="", contato=""):
    """Registra o pedido de atendimento humano num CSV (no futuro poderia abrir um ticket)."""
    PASTA_ATENDIMENTOS.mkdir(exist_ok=True)
    arquivo = PASTA_ATENDIMENTOS / "encaminhamentos.csv"
    arquivo_novo = not arquivo.exists()
    # usa hoje() para o protocolo bater com a data da conversa quando DATA_REFERENCIA está definida
    protocolo = "EM-" + datetime.combine(hoje(), datetime.now().time()).strftime("%Y%m%d-%H%M%S")

    with open(arquivo, "a", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        if arquivo_novo:
            escritor.writerow(["protocolo", "data_hora", "nome", "contato", "motivo"])
        # os campos vêm do cliente (via modelo), então limpo para não virarem fórmula no Excel
        escritor.writerow([
            protocolo,
            datetime.now().isoformat(timespec="seconds"),
            seguranca.limpar_campo_csv(nome),
            seguranca.limpar_campo_csv(contato),
            seguranca.limpar_campo_csv(motivo),
        ])

    return {
        "protocolo": protocolo,
        "mensagem_para_o_cliente": (
            f"Seu caso foi encaminhado. Protocolo {protocolo}. "
            "A equipe vai entrar em contato em até 24 horas úteis."
        ),
    }


# ligação entre o nome que o LLM usa e a função Python
FUNCOES = {
    "buscar_produtos": buscar_produtos,
    "consultar_pedido": consultar_pedido,
    "consultar_politicas": consultar_politicas,
    "encaminhar_atendente": encaminhar_atendente,
}


def executar_ferramenta(nome, argumentos):
    funcao = FUNCOES.get(nome)
    if funcao is None:
        return {"erro": f"A ferramenta {nome} não existe."}

    # alguns modelos mandam parâmetros vazios como null, então tiro eles
    argumentos = {chave: valor for chave, valor in argumentos.items() if valor not in (None, "")}
    try:
        return funcao(**argumentos)
    except Exception as erro:
        # devolvo o erro para o modelo, assim ele pode tentar de novo com outros argumentos
        return {"erro": f"Erro ao executar {nome}: {erro}"}


# Descrição das ferramentas no formato de "tools" da API (compatível com Ollama e Groq)
FERRAMENTAS = [
    {
        "type": "function",
        "function": {
            "name": "buscar_produtos",
            "description": (
                "Busca instrumentos no catálogo da loja. Use sempre que o cliente perguntar sobre produtos, "
                "preço, disponibilidade, estoque ou promoções. Retorna situação de estoque, preço, promoção ativa, "
                "preço no PIX e parcelamento."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "texto": {
                        "type": "string",
                        "description": "Marca, modelo ou tipo do produto. Ex: 'Takamine GD20', 'Yamaha', 'violão 7 cordas'.",
                    },
                    "categoria": {
                        "type": "string",
                        "enum": CATEGORIAS,
                        "description": "Categoria do produto, se o cliente mencionar uma.",
                    },
                    "preco_maximo": {
                        "type": "number",
                        "description": "Preço máximo em reais, se o cliente mencionar um orçamento.",
                    },
                    "apenas_promocao": {
                        "type": "boolean",
                        "description": "true para trazer só produtos com promoção ativa.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_pedido",
            "description": (
                "Consulta status, itens, rastreio e prazos de um pedido. Só chame depois que o cliente "
                "informar o número do pedido E o e-mail ou telefone usado na compra."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "numero_pedido": {"type": "integer", "description": "Número do pedido."},
                    "email_ou_telefone": {
                        "type": "string",
                        "description": "E-mail ou telefone do cliente, para confirmar que ele é o dono do pedido.",
                    },
                },
                "required": ["numero_pedido", "email_ou_telefone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_politicas",
            "description": (
                "Consulta o manual de políticas da loja. Use para dúvidas sobre endereço e contato, horário, "
                "formas de pagamento e parcelamento, trocas e devoluções, frete e entrega, regras de promoções, "
                "garantia e privacidade de dados."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "assunto": {
                        "type": "string",
                        "enum": list(SECOES_POLITICAS.keys()),
                        "description": "Assunto da dúvida do cliente.",
                    },
                },
                "required": ["assunto"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "encaminhar_atendente",
            "description": (
                "Encaminha o caso para a equipe humana. Use para reclamações, pedidos atrasados, "
                "quando o cliente pedir para falar com uma pessoa ou quando você não conseguir resolver."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "motivo": {"type": "string", "description": "Resumo do problema do cliente."},
                    "nome": {"type": "string", "description": "Nome do cliente, se souber."},
                    "contato": {"type": "string", "description": "Telefone ou e-mail para retorno, se souber."},
                },
                "required": ["motivo"],
            },
        },
    },
]
