"""
Leitura do manual de políticas (PDF) e separação por seção.

O manual é pequeno (8 páginas) e já vem dividido em seções numeradas,
então em vez de usar embeddings eu separo o texto por seção e o agente
pede a seção pelo assunto.
"""
import re
from pathlib import Path

from pypdf import PdfReader

ARQUIVO_PDF = Path(__file__).parent / "data" / "políticas_da_loja.pdf"

# assunto usado pela ferramenta -> seções do manual que entram nele.
# "Sobre a loja" e "horário" ficaram juntos porque o cliente costuma perguntar os dois na mesma
# mensagem e, testando, o modelo consultava só um deles e inventava o outro.
# A seção 7 (diretrizes de atendimento) é instrução interna para a equipe, então ela
# vai para o prompt do agente e não para o cliente. A seção 10 é só encerramento.
ASSUNTOS = {
    "loja_contato_e_horario": [1, 2],
    "pagamento": [3],
    "trocas_e_devolucoes": [4],
    "frete_e_entrega": [5],
    "promocoes": [6],
    "garantia": [8],
    "privacidade": [9],
}


def ler_linhas_pdf():
    leitor = PdfReader(ARQUIVO_PDF)
    linhas = []
    for pagina in leitor.pages:
        # o modo padrão do pypdf quebrava cada palavra numa linha; o modo "layout" mantém as linhas
        for linha in pagina.extract_text(extraction_mode="layout").splitlines():
            linha = linha.strip()
            # cabeçalho e rodapé se repetem em todas as páginas
            if not linha or linha.startswith("Empório da Música Manual de") or re.fullmatch(r"Página \d+", linha):
                continue
            linha = re.sub(r"^•\s+", "- ", linha)
            # nas tabelas as colunas vêm separadas por vários espaços, troco por " | "
            linha = re.sub(r"\s{2,}", " | ", linha)
            linhas.append(linha)
    return linhas


def carregar_secoes():
    """Retorna um dict {assunto: texto da seção}."""
    secoes = {}
    numero_atual = None

    for linha in ler_linhas_pdf():
        # título de seção: "4. Política de Trocas e Devoluções".
        # Itens de lista como "1. Saudação: cumprimentar..." têm ":" e não entram.
        titulo = re.match(r"^(\d{1,2})\. ([^:]+)$", linha)
        if titulo and int(titulo.group(1)) == len(secoes) + 1:
            numero_atual = int(titulo.group(1))
            secoes[numero_atual] = []

        # o que vem antes da seção 1 é a capa, então é ignorado
        if numero_atual:
            secoes[numero_atual].append(linha)

    resultado = {}
    for assunto, numeros in ASSUNTOS.items():
        linhas = []
        for numero in numeros:
            linhas += secoes.get(numero, [])
        texto = "\n".join(linhas)
        # o e-mail na tabela do manual está com acento ("empóriodamusica"), o que não é um e-mail válido.
        # Uso a versão da capa do manual.
        texto = texto.replace("empóriodamusica", "emporiodamusica")
        resultado[assunto] = texto

    # A tabela diz "cartão até 12x, parcela mínima de R$ 100", mas a seção 3.1 traz regras diferentes
    # por faixa de parcelas. Considero a 3.1, que é mais detalhada, e deixo isso explícito para o agente.
    resultado["pagamento"] += "\nObservação: para parcelamento no cartão, valem as regras detalhadas da seção 3.1."

    return resultado


def extrair_subsecao(texto, numero):
    """Pega só uma subseção (ex: "4.1") de dentro do texto de uma seção."""
    linhas = []
    dentro = False
    for linha in texto.splitlines():
        # títulos de subseção começam com "4.1 ", "4.2 "...; as linhas quebradas do PDF não
        if re.match(r"^\d+\.\d+ ", linha):
            dentro = linha.startswith(numero + " ")
        if dentro:
            linhas.append(linha)
    return "\n".join(linhas)


if __name__ == "__main__":
    # para conferir rápido se a extração ficou boa: python politicas.py
    for assunto, texto in carregar_secoes().items():
        print(f"===== {assunto} =====")
        print(texto)
        print()
