from pathlib import Path
import subprocess
import sys


PROJETO = Path(__file__).resolve().parent


ETAPAS = [
    [
        sys.executable,
        str(PROJETO / "baixar_nq_yahoo_forward.py"),
    ],
    [
        sys.executable,
        str(PROJETO / "validar_yahoo_janela_v4.py"),
    ],
    [
        sys.executable,
        str(PROJETO / "montar_base_forward_v4.py"),
    ],
    [
        sys.executable,
        str(PROJETO / "detectar_orb_forward_v4.py"),
    ],
    [
        sys.executable,
        str(PROJETO / "detectar_fvg_forward_v4.py"),
    ],
    [
        sys.executable,
        str(PROJETO / "backtest_v3_forward_v4.py"),
        "--rr-alvo",
        "1.25",
    ],
    [
        sys.executable,
        str(PROJETO / "forward_test_v4.py"),
    ],
]


def executar(nome, comando):
    print()
    print("=" * 75)
    print(nome)
    print("=" * 75)

    resultado = subprocess.run(
        comando,
        cwd=PROJETO
    )

    if resultado.returncode != 0:
        print()
        print(f"ERRO na etapa: {nome}")
        print(
            f"Código de saída: "
            f"{resultado.returncode}"
        )

        sys.exit(
            resultado.returncode
        )


def main():
    print()
    print("=" * 75)
    print(
        "ATUALIZAÇÃO AUTOMÁTICA - FORWARD V4"
    )
    print("=" * 75)

    nomes = [
        "1/7 - Baixar Yahoo",
        "2/7 - Validar janela Yahoo",
        "3/7 - Montar base forward",
        "4/7 - Detectar ORB",
        "5/7 - Detectar FVG",
        "6/7 - Rodar V3 RR 1.25",
        "7/7 - Atualizar placar OOS",
    ]

    for nome, comando in zip(
        nomes,
        ETAPAS
    ):
        executar(
            nome,
            comando
        )

    print()
    print("=" * 75)
    print("ATUALIZAÇÃO CONCLUÍDA")
    print("=" * 75)

    print(
        "O placar oficial está em:"
    )

    print(
        PROJETO
        / "data"
        / "forward_placar_v4.csv"
    )


if __name__ == "__main__":
    main()