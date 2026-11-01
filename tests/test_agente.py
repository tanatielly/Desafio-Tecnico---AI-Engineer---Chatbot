"""
Testes das partes do agente que não dependem do LLM.
"""
import json
import re
from datetime import datetime
from types import SimpleNamespace

import ferramentas
from agente import Agente, disse_que_encaminhou, garantir_protocolo, loja_aberta, proxima_abertura


class ClienteFalso:
    """Imita o cliente da OpenAI devolvendo respostas prontas, para testar o loop do agente sem LLM."""

    def __init__(self, respostas):
        self.respostas = respostas
        self.ferramentas_recebidas = []  # nomes das ferramentas enviadas em cada chamada
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.ferramentas_recebidas.append([f["function"]["name"] for f in kwargs["tools"]])
        return SimpleNamespace(choices=[SimpleNamespace(message=self.respostas.pop(0))])


def resposta_texto(texto):
    return SimpleNamespace(content=texto, tool_calls=None)


def resposta_ferramenta(nome, argumentos):
    chamada = SimpleNamespace(id="call_1", function=SimpleNamespace(name=nome, arguments=json.dumps(argumentos)))
    return SimpleNamespace(content="", tool_calls=[chamada])


def criar_agente(monkeypatch, tmp_path, respostas):
    # grava os encaminhamentos numa pasta temporária
    monkeypatch.setattr(ferramentas, "PASTA_ATENDIMENTOS", tmp_path)
    agente = Agente()
    agente.cliente = ClienteFalso(respostas)
    return agente


def test_trava_faz_o_modelo_chamar_a_ferramenta_de_verdade(monkeypatch, tmp_path):
    agente = criar_agente(monkeypatch, tmp_path, [
        resposta_texto("Encaminhei seu caso! Protocolo ANA-123."),  # inventou o encaminhamento
        resposta_ferramenta("encaminhar_atendente", {"motivo": "pedido atrasado", "contato": "67 99654-7821"}),
        resposta_texto("Pronto, seu caso foi encaminhado!"),  # esqueceu o protocolo
    ])
    texto = agente.responder("Encaminha pra equipe, por favor")

    # na segunda tentativa só a ferramenta de encaminhar é oferecida ao modelo
    assert agente.cliente.ferramentas_recebidas[1] == ["encaminhar_atendente"]
    # o protocolo inventado não aparece; o verdadeiro é acrescentado no final
    assert "ANA-123" not in texto
    assert re.search(r"EM-\d{8}-\d{6}", texto)
    assert (tmp_path / "encaminhamentos.csv").exists()


def test_trava_nao_deixa_promessa_falsa_chegar_ao_cliente(monkeypatch, tmp_path):
    agente = criar_agente(monkeypatch, tmp_path, [
        resposta_texto("Encaminhado! Protocolo X-1."),
        resposta_texto("Encaminhei sim, protocolo X-2."),  # mesmo depois do aviso não chamou
    ])
    texto = agente.responder("Encaminha pra equipe, por favor")

    assert "WhatsApp" in texto
    assert "X-1" not in texto and "X-2" not in texto
    assert not (tmp_path / "encaminhamentos.csv").exists()


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
