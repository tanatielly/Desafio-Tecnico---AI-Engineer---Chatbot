"""
Testes das partes do agente que não dependem do LLM.
"""
from datetime import datetime

from agente import disse_que_encaminhou, garantir_protocolo, loja_aberta, proxima_abertura


def test_detecta_quando_diz_que_encaminhou():
    assert disse_que_encaminhou("Seu caso foi encaminhado para a equipe.")
    assert disse_que_encaminhou("Encaminhando seu caso, Ana. O número do protocolo é ANA-1.")
    # oferecer encaminhamento não é afirmar que encaminhou
    assert not disse_que_encaminhou("Quer que eu encaminhe para a equipe?")
    assert not disse_que_encaminhou("Posso encaminhar seu caso, se quiser.")


def test_garantir_protocolo():
    protocolo = "EM-20260325-101500"

    # o modelo esqueceu o protocolo: ele vai para o final da resposta
    texto = garantir_protocolo("Seu caso foi encaminhado para a equipe.", protocolo)
    assert texto.endswith(f"Seu número de protocolo é {protocolo}.")

    # já estava na resposta: não repete
    texto = garantir_protocolo(f"Encaminhado! Protocolo {protocolo}.", protocolo)
    assert texto.count(protocolo) == 1

    # sem encaminhamento nesta mensagem: não muda nada
    assert garantir_protocolo("Oi, tudo bem?", None) == "Oi, tudo bem?"


def test_horario_da_loja():
    assert loja_aberta(datetime(2026, 3, 25, 10, 0))      # quarta, 10h
    assert not loja_aberta(datetime(2026, 3, 25, 19, 0))  # quarta, 19h
    assert loja_aberta(datetime(2026, 3, 28, 12, 30))     # sábado, 12h30
    assert not loja_aberta(datetime(2026, 3, 28, 14, 0))  # sábado, 14h
    assert not loja_aberta(datetime(2026, 3, 29, 10, 0))  # domingo


def test_proxima_abertura():
    # sábado à tarde -> só abre segunda às 9h
    assert proxima_abertura(datetime(2026, 3, 28, 14, 0)) == datetime(2026, 3, 30, 9, 0)
    # quarta à noite -> quinta às 9h
    assert proxima_abertura(datetime(2026, 3, 25, 19, 0)) == datetime(2026, 3, 26, 9, 0)
