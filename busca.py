"""
Ajuda a busca de produtos a entender sinônimos e erros de digitação.

Usa só a biblioteca padrão: o difflib compara a palavra digitada com as palavras
que existem no catálogo e sugere a mais parecida ("takamini" -> "takamine").
"""
import difflib
import re

import dados

# jeito que o cliente pode escrever -> palavra que existe no catálogo
SINONIMOS = {
    # em inglês
    "guitar": "guitarra",
    "bass": "baixo",
    "drum": "bateria",
    "drums": "bateria",
    "keyboard": "teclado",
    "steel": "aco",
    # gírias e outros jeitos de falar
    "batera": "bateria",
    "uke": "ukulele",
    "erudito": "classico",
    "sete": "7",
}

# A loja não vende acessórios (seção 1 do manual). Sem essa lista, uma busca por
# "amplificador" achava os violões que têm "pré-amplificador" na descrição.
ACESSORIOS = {
    "amplificador", "amplificadores", "amp", "palheta", "palhetas", "cabo", "cabos",
    "case", "cases", "pedal", "pedais", "correia", "correias", "encordoamento",
    "capotraste", "baqueta", "baquetas",
}

# "cordas de guitarra" é acessório, mas "violão com cordas de aço" é um tipo de violão,
# então só considero acessório quando vem o nome de um instrumento depois de "cordas de/para"
CORDAS_AVULSAS = re.compile(
    r"\bcordas? (de|da|do|pra|para) (guitarra|violao|baixo|ukulele|violino|cavaquinho)|jogo de cordas"
)

# quão parecida a palavra precisa ser para ser corrigida (0 a 1).
# Com 0.8 corrige "takamini" e "ukelele", mas não inventa nada para "saxofone" ou "flauta".
SEMELHANCA_MINIMA = 0.8


def palavras(texto):
    """Quebra o texto em palavras sem acento e sem hífen ("GF-3D" vira "gf3d")."""
    texto = dados.normalizar(texto).replace("-", "")
    todas = re.findall(r"[a-z0-9]+", texto)
    # palavras curtas como "de" e "o" atrapalham, mas códigos com número ("f310", "20") ficam
    return [p for p in todas if len(p) > 2 or any(c.isdigit() for c in p)]


def montar_vocabulario(textos):
    """Todas as palavras que aparecem no catálogo, usadas para corrigir erros de digitação."""
    vocabulario = set()
    for texto in textos:
        vocabulario.update(p for p in re.findall(r"[a-z0-9]+", texto) if len(p) > 2)
    return sorted(vocabulario)


def busca_de_acessorio(texto):
    if CORDAS_AVULSAS.search(dados.normalizar(texto)):
        return True
    return any(p in ACESSORIOS for p in palavras(texto))


def preparar_termos(texto, textos_produtos, vocabulario):
    """Devolve as palavras prontas para a busca e um dict com as que foram trocadas."""
    termos = []
    correcoes = {}
    for palavra in palavras(texto):
        original = palavra
        palavra = SINONIMOS.get(palavra, palavra)

        # se a palavra não aparece em nenhum produto, pode ser erro de digitação
        if not any(palavra in t for t in textos_produtos):
            parecidas = difflib.get_close_matches(palavra, vocabulario, n=1, cutoff=SEMELHANCA_MINIMA)
            if parecidas:
                palavra = parecidas[0]

        if palavra != original:
            correcoes[original] = palavra
        termos.append(palavra)

    return termos, correcoes
