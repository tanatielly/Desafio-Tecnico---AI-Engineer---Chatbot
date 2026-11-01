"""
Interface web simples para conversar com o Tom.

Uso: streamlit run app_streamlit.py
"""
import streamlit as st

from agente import Agente

st.set_page_config(page_title="Empório da Música", page_icon="🎸")
st.title("🎸 Empório da Música")
st.caption("Sua música começa aqui. Converse com o Tom, nosso assistente virtual.")

# O Streamlit roda o arquivo todo de novo a cada interação,
# então o agente e as mensagens ficam guardados no session_state.
if "agente" not in st.session_state:
    st.session_state.agente = Agente()
    st.session_state.mensagens = []  # lista de (papel, texto, ferramentas usadas)
    st.session_state.arquivo = None

agente = st.session_state.agente


def mostrar_texto(texto):
    # o Streamlit entende "$...$" como fórmula matemática, o que bagunça os preços em R$
    st.markdown(texto.replace("$", "\\$"))


with st.sidebar:
    st.write(f"Modelo: `{agente.modelo}`")
    mostrar_ferramentas = st.checkbox("Mostrar ferramentas usadas", value=True)
    if st.button("Nova conversa"):
        agente.limpar()
        st.session_state.mensagens = []
        st.session_state.arquivo = None
        st.rerun()

with st.chat_message("assistant"):
    mostrar_texto("Oi! Eu sou o Tom, da Empório da Música 🎶 Posso te ajudar com instrumentos, preços, pedidos ou dúvidas sobre a loja.")

for papel, texto, ferramentas in st.session_state.mensagens:
    with st.chat_message(papel):
        if mostrar_ferramentas and ferramentas:
            st.caption("🔧 " + " | ".join(ferramentas))
        mostrar_texto(texto)

pergunta = st.chat_input("Digite sua mensagem...")
if pergunta:
    st.session_state.mensagens.append(("user", pergunta, []))
    with st.chat_message("user"):
        mostrar_texto(pergunta)

    with st.chat_message("assistant"):
        with st.spinner("Tom está digitando..."):
            try:
                resposta = agente.responder(pergunta)
            except Exception as erro:
                resposta = f"Ops, não consegui falar com o modelo agora ({erro}). Confira se o Ollama está rodando."
        if mostrar_ferramentas and agente.ultimas_ferramentas:
            st.caption("🔧 " + " | ".join(agente.ultimas_ferramentas))
        mostrar_texto(resposta)

    st.session_state.mensagens.append(("assistant", resposta, list(agente.ultimas_ferramentas)))
    # salva a cada mensagem, para não perder a conversa se fechar o navegador
    st.session_state.arquivo = agente.salvar_conversa(st.session_state.arquivo)
