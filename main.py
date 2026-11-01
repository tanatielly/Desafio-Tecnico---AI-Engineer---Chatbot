"""
Conversa com o Allegro pelo terminal.

Uso:
    python main.py
    python main.py < roteiro.txt   (lê as mensagens de um arquivo, uma por linha)

Comandos: "sair" encerra e salva a conversa, "limpar" começa uma conversa nova.
"""
import sys

from agente import Agente

# no Windows o terminal nem sempre usa UTF-8, e aí acentos e emojis quebram.
# "utf-8-sig" na entrada remove o BOM que o PowerShell coloca quando a entrada vem de pipe.
sys.stdout.reconfigure(encoding="utf-8")
sys.stdin.reconfigure(encoding="utf-8-sig")


def main():
    agente = Agente()
    entrada_por_arquivo = not sys.stdin.isatty()

    print("=" * 60)
    print("Empório da Música - Sua música começa aqui.")
    print(f"Atendimento virtual com o Allegro (modelo: {agente.modelo})")
    print('Digite "sair" para encerrar ou "limpar" para começar de novo.')
    print("=" * 60)

    while True:
        try:
            mensagem = input("\nVocê: ").strip()
        except (EOFError, KeyboardInterrupt):
            # EOF acontece quando o arquivo de roteiro acaba
            break

        if not mensagem:
            continue
        if mensagem.lower() == "sair":
            break
        if mensagem.lower() == "limpar":
            agente.salvar_conversa()
            agente.limpar()
            print("Conversa reiniciada.")
            continue

        # quando a mensagem vem de arquivo ela não aparece na tela, então mostro aqui
        if entrada_por_arquivo:
            print(mensagem)

        try:
            resposta = agente.responder(mensagem)
        except Exception as erro:
            print(f"\n[erro ao falar com o modelo: {erro}]")
            print("Confira se o Ollama está rodando ou se as configurações do .env estão certas.")
            continue

        for chamada in agente.ultimas_ferramentas:
            print(f"  [ferramenta] {chamada}")
        print(f"\nAllegro: {resposta}")

    arquivo = agente.salvar_conversa()
    if arquivo:
        print(f"\nConversa salva em {arquivo}")


if __name__ == "__main__":
    main()
