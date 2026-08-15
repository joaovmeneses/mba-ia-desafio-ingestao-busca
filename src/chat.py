"""Chat de linha de comando sobre o conteúdo do PDF ingerido.

Uso: `python src/chat.py`. Requer que `ingest.py` já tenha rodado.
"""

from search import search_prompt

COMANDOS_DE_SAIDA = {"sair", "exit", "quit"}


def main():
    chain = search_prompt()

    if not chain:
        print("Não foi possível iniciar o chat. Verifique os erros de inicialização.")
        return

    print("Faça sua pergunta (digite 'sair' para encerrar).\n")

    while True:
        try:
            pergunta = input("PERGUNTA: ").strip()
        except (EOFError, KeyboardInterrupt):
            # Ctrl+D / Ctrl+C encerram sem stacktrace.
            print()
            break

        if not pergunta:
            continue

        if pergunta.lower() in COMANDOS_DE_SAIDA:
            break

        try:
            resposta = chain.invoke(pergunta)
        except KeyboardInterrupt:
            print("\nConsulta interrompida.\n")
            continue
        except Exception as erro:
            print(f"Erro ao responder: {erro}\n")
            continue

        print(f"RESPOSTA: {resposta}\n")

    print("Até mais!")


if __name__ == "__main__":
    main()