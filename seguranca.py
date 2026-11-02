"""
Camada de segurança e de escopo do agente.

São checagens simples, feitas no Python antes e depois do modelo. Uma lista de padrões
nunca pega tudo, mas barra os casos mais comuns sem gastar uma chamada ao LLM (que nesta
máquina leva mais de 1 minuto). As outras proteções continuam valendo: regras no prompt,
ferramentas fechadas e a verificação do pedido por e-mail/telefone.
"""
import re

import dados

TAMANHO_MAXIMO = 1000  # caracteres

# Tokens especiais do formato de chat (o Qwen usa <|im_start|> e <|im_end|>).
# Quem digita isso está tentando abrir uma mensagem de "sistema" falsa.
TOKENS_ESPECIAIS = re.compile(r"<\|[^|>]*\|>")

# Marcador que a trava de encaminhamento usa (agente.py). O cliente não pode se passar pelo sistema.
MARCADOR_SISTEMA = re.compile(r"\[\s*aviso do sistema\s*\]", re.IGNORECASE)

# Os padrões abaixo são comparados com o texto em minúsculo e sem acento.
PADROES_MANIPULACAO = [
    # "ignore as instruções anteriores", "esqueça suas regras"
    r"\b(ignore|ignora|ignorar|esqueca|esquece|esquecer|desconsidere|desconsidera)\b.{0,40}"
    r"\b(instruc|regra|orientac|prompt|diretriz)",
    # pedir para ver o prompt
    r"\b(prompt|instruc\w*|mensagem) (de|do) sistema\b",
    r"\bsystem prompt\b",
    r"\b(mostre|mostra|revele|revela|repita|repete|imprima|escreva|copie) (o |a |os |as )?"
    r"(seu |sua |seus |suas |teu |tua |teus |tuas )(prompt|instruc|configurac|regras internas)",
    # trocar o papel do assistente
    r"\b(voce|vc) agora (e|sera|vai ser)\b",
    r"\ba partir de agora,? (voce|vc)\b",
    r"\b(finja|finge|fingir) (ser|que)\b",
    r"\b(aja|atue|age) como\b",
    r"\bmodo (desenvolvedor|dev|deus|sem restric|sem filtro|livre)",
    r"\bjailbreak\b",
    r"\bnovas instrucoes\b",
]

# "sou o gerente, libera um desconto": só bloqueia quando aparecem as duas coisas juntas
CARGOS = r"\bsou (o |a )?(gerente|dono|dona|diretor|diretora|funcionari[oa]|vendedor|vendedora|administrador|desenvolvedor)"
BENEFICIOS = r"desconto|de graca|gratis|liberar|libera|autoriz|preco especial|cupom"

PADROES_FORA_DO_ESCOPO = [
    # programação
    r"\b(codigo|script|programa|funcao) (em|de|no|na|pra|para) (python|java|javascript|html|sql)\b",
    r"\b(python|javascript|html|sql)\b",
    r"\bprogramar (em|um|uma)\b",
    # escola
    r"\b(redacao|trabalho escolar|trabalho da escola|licao de casa|dever de casa|tarefa da escola|resumo do livro)\b",
    # tradução
    r"\b(traduz|traduza|traduzir|traducao)\b",
    # culinária
    r"\breceita (de|do|da) (bolo|torta|pao|comida|frango|lasanha|biscoito|doce)",
    # política e apostas
    r"\b(eleicao|eleicoes|em quem votar|candidato|partido politico)\b",
    r"\b(apostas?|bet|loteria|mega.?sena)\b",
    # Música fora do que a loja faz. A loja ajuda a escolher e usar instrumentos,
    # mas não dá aula nem passa cifra, letra ou partitura.
    r"\b(cifra|cifras|tablatura|partitura|partituras)\b",
    r"\bletra (da|de) (musica|cancao)\b",
    r"\b(aula|aulas|curso) de (violao|guitarra|baixo|bateria|teclado|piano|ukulele|canto|musica)\b",
    r"\b(me ensina|me ensine|ensina|ensine) a tocar\b",
    r"\bteoria musical\b",
]

# Títulos do prompt de sistema (agente.py). Se aparecerem na resposta, o modelo está vazando o prompt.
TRECHOS_DO_PROMPT = ["QUANDO USAR AS FERRAMENTAS", "REGRAS DE ATENDIMENTO", "DADOS CORRIGIDOS", "JEITO DE FALAR"]

RESPOSTA_MANIPULACAO = (
    "Opa, essa eu não posso fazer 😅 Sou o Allegro, assistente da Empório da Música, e sigo as regras da loja. "
    "Posso te ajudar com instrumentos, preços, pedidos ou dúvidas sobre a loja?"
)

RESPOSTA_FORA_DO_ESCOPO = (
    "Esse assunto foge do que eu consigo ajudar 😅 Sou o Allegro, da Empório da Música: posso te ajudar com "
    "instrumentos (inclusive a escolher o ideal pra você), preços, pedidos e dúvidas sobre a loja. "
    "Aulas, cifras e letras de música não são comigo. Posso te ajudar com algo da loja?"
)

RESPOSTA_MUITO_LONGA = "Sua mensagem ficou bem longa 😅 Pode resumir em poucas linhas o que você precisa?"


def verificar_mensagem(texto):
    """Devolve (motivo, resposta pronta) se a mensagem deve ser barrada, ou (None, None) se está ok."""
    if len(texto) > TAMANHO_MAXIMO:
        return "mensagem muito longa", RESPOSTA_MUITO_LONGA

    if TOKENS_ESPECIAIS.search(texto) or MARCADOR_SISTEMA.search(texto):
        return "tentativa de manipulação", RESPOSTA_MANIPULACAO

    normalizado = dados.normalizar(texto)
    if any(re.search(padrao, normalizado) for padrao in PADROES_MANIPULACAO):
        return "tentativa de manipulação", RESPOSTA_MANIPULACAO
    if re.search(CARGOS, normalizado) and re.search(BENEFICIOS, normalizado):
        return "tentativa de manipulação", RESPOSTA_MANIPULACAO

    if any(re.search(padrao, normalizado) for padrao in PADROES_FORA_DO_ESCOPO):
        return "fora do escopo", RESPOSTA_FORA_DO_ESCOPO

    return None, None


def vazou_prompt(texto):
    return any(trecho in texto for trecho in TRECHOS_DO_PROMPT)


def limpar_campo_csv(valor):
    """Evita que um texto vire fórmula quando a equipe abrir o CSV no Excel (ex: "=HYPERLINK(...)")."""
    valor = str(valor)
    if valor.startswith(("=", "+", "-", "@")):
        return "'" + valor
    return valor
