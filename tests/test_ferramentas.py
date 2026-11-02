"""
Testes das ferramentas. Não usam o LLM, então rodam rápido e sem internet.
Rodar com: pytest
"""
import re

import ferramentas


def buscar_um(texto):
    """Busca um produto pelo nome, esteja ele disponível ou não."""
    resultado = ferramentas.buscar_produtos(texto=texto)
    produtos = resultado.get("produtos_disponiveis") or resultado.get("produtos_indisponiveis")
    return produtos[0]


def test_preco_takamine_gd20():
    resultado = ferramentas.buscar_produtos(texto="Takamine GD20")
    assert resultado["total_disponiveis"] == 1

    produto = resultado["produtos_disponiveis"][0]
    assert produto["nome"] == "Takamine GD20 Dreadnought Natural"
    assert produto["preco"] == "R$ 2.199,00"
    assert produto["preco_no_pix"].startswith("R$ 2.089,05")
    assert produto["parcelamento"] == "até 12x de R$ 183,25 sem juros"


def test_promocao_inativa_nao_aparece():
    # o GD20 tem uma "Oferta Especial" no CSV, mas ela está com is_active = 0
    assert "promocao_ativa" not in buscar_um("Takamine GD20")


def test_promocao_ativa_sem_desconto_pix():
    # Kalani KAL-700T (id 127) tem 10% de desconto ativo: 359 -> 323,10
    produto = buscar_um("Kalani KAL-700T")
    assert produto["preco_promocional"] == "R$ 323,10"
    assert "preco_no_pix" not in produto


def test_parcelamento():
    assert ferramentas.calcular_parcelamento(2199) == (12, 183.25)
    assert ferramentas.calcular_parcelamento(250) == (3, 83.33)
    assert ferramentas.calcular_parcelamento(40) == (1, 40)


def test_violoes_ate_mil_separa_indisponiveis():
    resultado = ferramentas.buscar_produtos(categoria="Violões", preco_maximo=1000)
    disponiveis = [p["nome"] for p in resultado["produtos_disponiveis"]]
    indisponiveis = [p["nome"] for p in resultado["produtos_indisponiveis"]]

    assert resultado["total_disponiveis"] == 12
    assert len(disponiveis) == ferramentas.LIMITE_RESULTADOS
    assert "aviso" in resultado
    assert all(p["situacao"].startswith("disponível") for p in resultado["produtos_disponiveis"])
    # estoque zerado e descontinuado ficam separados
    assert "Giannini GF-3D Dreadnought Sunburst" in indisponiveis
    assert "Shelby SN-7C 7 Cordas Nylon Natural" in indisponiveis


def test_produto_esgotado_e_descontinuado():
    assert buscar_um("Giannini GF-3D")["situacao"] == "esgotado no momento"
    assert buscar_um("Shelby SN-7C")["situacao"].startswith("descontinuado")


def test_busca_corrige_erro_de_digitacao():
    resultado = ferramentas.buscar_produtos(texto="Takamini GD20")
    assert [p["nome"] for p in resultado["produtos_disponiveis"]] == ["Takamine GD20 Dreadnought Natural"]
    assert resultado["busca_entendida_como"] == "takamine gd20"


def test_busca_corrige_mais_de_uma_palavra():
    resultado = ferramentas.buscar_produtos(texto="ukelele kalanni")
    nomes = [p["nome"] for p in resultado["produtos_disponiveis"]]
    assert nomes
    assert all(nome.startswith("Kalani") for nome in nomes)


def test_busca_com_sinonimo_em_ingles():
    resultado = ferramentas.buscar_produtos(texto="guitar fender")
    nomes = [p["nome"] for p in resultado["produtos_disponiveis"]]
    assert nomes
    assert all(nome.startswith("Fender") for nome in nomes)


def test_busca_ignora_hifen_no_codigo():
    # no catálogo o nome é "GF-3D"
    assert buscar_um("GF3D")["nome"] == "Giannini GF-3D Dreadnought Sunburst"


def test_busca_de_acessorio():
    for texto in ["amplificador", "cordas de guitarra", "jogo de cordas pra violão"]:
        resultado = ferramentas.buscar_produtos(texto=texto)
        assert "não vende acessórios" in resultado["mensagem"], texto
        assert "produtos_disponiveis" not in resultado


def test_violao_com_cordas_de_aco_nao_e_acessorio():
    resultado = ferramentas.buscar_produtos(texto="violão com cordas de aço")
    assert resultado["total_disponiveis"] > 0


def test_busca_nao_inventa_produto_que_nao_existe():
    # saxofone não tem no catálogo e a correção não pode trocar por outra coisa
    resultado = ferramentas.buscar_produtos(texto="saxofone")
    assert resultado["mensagem"].startswith("Nenhum produto")


def test_esgotado_ja_traz_alternativas():
    resultado = ferramentas.buscar_produtos(texto="Giannini GF-3D")
    alternativas = resultado["alternativas_disponiveis"]

    assert 0 < len(alternativas) <= 3
    assert all(p["categoria"] == "Violões" for p in alternativas)
    assert all(p["situacao"].startswith("disponível") for p in alternativas)


def test_promocoes_mostram_campanhas_ativas():
    resultado = ferramentas.buscar_produtos(apenas_promocao=True)
    assert resultado["total_disponiveis"] == 4
    assert resultado["campanhas_ativas"] == ["Desconto Exclusivo", "Oferta Especial"]
    assert "Black Friday" not in resultado["campanhas_ativas"]


def test_descricao_errada_nao_e_enviada():
    # a descrição do "Music Man Bass 1X" fala de um Fender Jazz Bass, então ela é removida
    assert "descricao" not in buscar_um("Music Man Bass 1X")


def test_pedido_com_email_errado_e_negado():
    resultado = ferramentas.consultar_pedido(8, "outra.pessoa@jmail.com")
    assert "erro" in resultado
    assert "itens" not in resultado


def test_pedido_enviado_e_atrasado(monkeypatch):
    monkeypatch.setenv("DATA_REFERENCIA", "2026-03-25")
    # pedido 8 é da Ana Carolina, testando com o telefone em outro formato
    resultado = ferramentas.consultar_pedido(8, "67 99654 7821")

    assert resultado["status"].startswith("enviado")
    assert resultado["codigo_rastreio"] == "BRJL5544332BR"
    assert "atrasado" in resultado
    # como ainda não chegou, o prazo de arrependimento nem começou
    assert "AINDA NÃO COMEÇOU" in resultado["prazos"]["arrependimento (7 dias após receber)"]


def test_prazos_pedido_entregue(monkeypatch):
    monkeypatch.setenv("DATA_REFERENCIA", "2025-10-28")
    resultado = ferramentas.consultar_pedido(1, "pedro.oliveira@jmail.com")
    assert resultado["prazos"]["arrependimento (7 dias após receber)"] == "dentro do prazo"

    monkeypatch.setenv("DATA_REFERENCIA", "2026-03-25")
    resultado = ferramentas.consultar_pedido(1, "pedro.oliveira@jmail.com")
    assert resultado["prazos"]["arrependimento (7 dias após receber)"] == "fora do prazo"


def test_extrai_subsecao_de_arrependimento():
    texto = ferramentas.REGRAS_ARREPENDIMENTO
    assert texto.startswith("4.1 Direito de Arrependimento")
    assert "10 dias úteis" in texto
    assert "frete de devolução" in texto
    assert "4.2" not in texto  # não pode vazar a subseção seguinte


def test_pedido_enviado_traz_condicoes_de_devolucao(monkeypatch):
    monkeypatch.setenv("DATA_REFERENCIA", "2026-03-25")
    resultado = ferramentas.consultar_pedido(8, "anacarol.ferreira@coldmail.com")

    assert "embalagem original" in resultado["condicoes_de_devolucao"]
    # o reembolso volta para a forma de pagamento do pedido
    assert "cartão de débito" in resultado["proximos_passos"]
    # ainda não recebeu, então não faz sentido falar de defeito
    assert "troca_por_defeito" not in resultado


def test_pedido_entregue_traz_troca_por_defeito(monkeypatch):
    monkeypatch.setenv("DATA_REFERENCIA", "2026-03-25")
    resultado = ferramentas.consultar_pedido(1, "pedro.oliveira@jmail.com")

    assert "condicoes_de_devolucao" in resultado
    assert "30 (trinta) dias" in resultado["troca_por_defeito"]


def test_politica_loja_traz_endereco_e_horario():
    texto = ferramentas.consultar_politicas("loja_contato_e_horario")["texto"]
    assert "Rua 14 de Maio, 3200" in texto
    assert "09:00 às 18:00" in texto
    assert "Sábado | 09:00 às 13:00" in texto


def test_politica_email_corrigido():
    texto = ferramentas.consultar_politicas("loja_contato_e_horario")["texto"]
    assert "contato@emporiodamusica.com.br" in texto


def test_politica_assunto_invalido():
    assert "erro" in ferramentas.consultar_politicas("receita_de_bolo")


def test_encaminhar_atendente_gera_protocolo(monkeypatch, tmp_path):
    # grava numa pasta temporária para não sujar atendimentos/ de verdade
    monkeypatch.setattr(ferramentas, "PASTA_ATENDIMENTOS", tmp_path)
    monkeypatch.setenv("DATA_REFERENCIA", "2026-03-25")

    resultado = ferramentas.encaminhar_atendente("pedido 8 atrasado", "Ana", "(67) 99654-7821")
    protocolo = resultado["protocolo"]

    assert re.fullmatch(r"EM-20260325-\d{6}", protocolo)
    assert protocolo in resultado["mensagem_para_o_cliente"]
    assert protocolo in (tmp_path / "encaminhamentos.csv").read_text(encoding="utf-8")


def test_ferramenta_inexistente():
    assert "erro" in ferramentas.executar_ferramenta("apagar_tudo", {})
