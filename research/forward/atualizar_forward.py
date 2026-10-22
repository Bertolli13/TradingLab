from pathlib import Path
import subprocess
import sys


PROJETO = Path(__file__).resolve().parent


ETAPAS = [
    {
        "titulo": "1/9 - Baixar Yahoo cumulativo",
        "comando": [
            sys.executable,
            "baixar_nq_yahoo_forward.py",
        ],
    },
    {
        "titulo": "2/9 - Validar janela Yahoo",
        "comando": [
            sys.executable,
            "validar_yahoo_janela_v4.py",
        ],
    },
    {
        "titulo": "3/9 - Montar base forward",
        "comando": [
            sys.executable,
            "montar_base_forward_v4.py",
        ],
    },
    {
        "titulo": "4/9 - Detectar ORB",
        "comando": [
            sys.executable,
            "detectar_orb_forward_v4.py",
        ],
    },
    {
        "titulo": "5/9 - Detectar FVG",
        "comando": [
            sys.executable,
            "detectar_fvg_forward_v4.py",
        ],
    },
    {
        "titulo": "6/9 - Rodar V4 RR 1.25",
        "comando": [
            sys.executable,
            "backtest_v3_forward_v4.py",
            "--rr-alvo",
            "1.25",
        ],
    },
    {
        "titulo": "7/9 - Atualizar placar V4",
        "comando": [
            sys.executable,
            "forward_test_v4.py",
        ],
    },
    {
        "titulo": "8/9 - Rodar V5 Range 75% / RR 1.50",
        "comando": [
            sys.executable,
            "backtest_v5_forward.py",
            "--stop-modelo",
            "range_75",
            "--rr-alvo",
            "1.50",
        ],
    },
    {
        "titulo": "9/9 - Atualizar placar V5",
        "comando": [
            sys.executable,
            "forward_test_v5.py",
        ],
    },
]


def executar_etapa(numero, etapa):
    print()
    print("=" * 75)
    print(etapa["titulo"])
    print("=" * 75)

    resultado = subprocess.run(
        etapa["comando"],
        cwd=PROJETO,
    )

    if resultado.returncode != 0:
        print()
        print("=" * 75)
        print("ATUALIZAÇÃO INTERROMPIDA")
        print("=" * 75)

        print(
            f"Falha na etapa {numero}: "
            f"{etapa['titulo']}"
        )

        print(
            "Código de saída:",
            resultado.returncode,
        )

        sys.exit(
            resultado.returncode
        )


def main():
    print()
    print("=" * 75)
    print("ATUALIZAÇÃO AUTOMÁTICA - FORWARD V4 + V5")
    print("=" * 75)

    for numero, etapa in enumerate(
        ETAPAS,
        start=1,
    ):
        executar_etapa(
            numero,
            etapa,
        )

    print()
    print("=" * 75)
    print("ATUALIZAÇÃO CONCLUÍDA")
    print("=" * 75)

    print()
    print("Placares atualizados:")

    print(
        PROJETO
        / "data"
        / "forward_placar_v4.csv"
    )

    print(
        PROJETO
        / "data"
        / "forward_placar_v5.csv"
    )

    print()
    print(
        "V4 e V5 foram atualizadas "
        "com os dados disponíveis."
    )


if __name__ == "__main__":
    main()