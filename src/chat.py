from search import search_prompt

EXIT_COMMANDS = {"sair", "exit", "quit"}
END_OF_INPUT = None


def read_question():
    try:
        return input("PERGUNTA: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return END_OF_INPUT


def answer(chain, question) -> str:
    try:
        return chain.invoke(question)
    except KeyboardInterrupt:
        return "Consulta interrompida."
    except Exception as error:
        return f"Erro ao responder: {error}"


def main():
    chain = search_prompt()

    if not chain:
        print("Não foi possível iniciar o chat. Verifique os erros de inicialização.")
        return

    print("Faça sua pergunta (digite 'sair' para encerrar).\n")

    while True:
        question = read_question()

        if question is END_OF_INPUT or question.lower() in EXIT_COMMANDS:
            break

        if not question:
            continue

        print(f"RESPOSTA: {answer(chain, question)}\n")

    print("Até mais!")


if __name__ == "__main__":
    main()
