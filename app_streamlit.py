"""
Interface web simples para conversar com o Allegro.

Uso: streamlit run app_streamlit.py
"""
import streamlit as st

from agente import Agente

st.set_page_config(page_title="Empório da Música", page_icon="🎸")
st.title("🎸 Empório da Música")
st.caption("Sua música começa aqui. Converse com o Allegro, nosso assistente virtual.")

# O Streamlit roda o arquivo todo de novo a cada interação,
# então o agente e as mensagens ficam guardados no session_state.
if "agente" not in st.session_state:
    st.session_state.agente = Agente()
    st.session_state.mensagens = []  # lista de (papel, texto, avisos: ferramentas usadas e bloqueios)
    st.session_state.arquivo = None

agente = st.session_state.agente


def mostrar_texto(texto):
    # o Streamlit entende "$...$" como fórmula matemática, o que bagunça os preços em R$
    st.markdown(texto.replace("$", "\\$"))


def avisos_da_resposta():
    """Legendas que aparecem em cima da resposta: ferramentas chamadas e bloqueios de segurança."""
    avisos = []
    if agente.ultimas_ferramentas:
        avisos.append("🔧 " + " | ".join(agente.ultimas_ferramentas))
    if agente.ultimo_bloqueio:
        avisos.append(f"🛡️ bloqueado: {agente.ultimo_bloqueio}")
    return avisos


with st.sidebar:
    st.write(f"Modelo: `{agente.modelo}`")
    mostrar_avisos = st.checkbox("Mostrar ferramentas e bloqueios", value=True)
    if st.button("Nova conversa"):
        agente.limpar()
        st.session_state.mensagens = []
        st.session_state.arquivo = None
        st.rerun()

with st.chat_message("assistant"):
    mostrar_texto("Oi! Eu sou o Allegro, da Empório da Música 🎶 Posso te ajudar com instrumentos, preços, pedidos ou dúvidas sobre a loja.")

for papel, texto, avisos in st.session_state.mensagens:
    with st.chat_message(papel):
        if mostrar_avisos:
            for aviso in avisos:
                st.caption(aviso)
        mostrar_texto(texto)

pergunta = st.chat_input("Digite sua mensagem...")
if pergunta:
    st.session_state.mensagens.append(("user", pergunta, []))
    with st.chat_message("user"):
        mostrar_texto(pergunta)

    with st.chat_message("assistant"):
        with st.spinner("Allegro está digitando..."):
            try:
                resposta = agente.responder(pergunta)
            except Exception as erro:
                resposta = f"Ops, não consegui falar com o modelo agora ({erro}). Confira se o Ollama está rodando."
        avisos = avisos_da_resposta()
        if mostrar_avisos:
            for aviso in avisos:
                st.caption(aviso)
        mostrar_texto(resposta)

    st.session_state.mensagens.append(("assistant", resposta, avisos))
    # salva a cada mensagem, para não perder a conversa se fechar o navegador
    st.session_state.arquivo = agente.salvar_conversa(st.session_state.arquivo)
