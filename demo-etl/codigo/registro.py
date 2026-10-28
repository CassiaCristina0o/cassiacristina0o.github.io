from datetime import datetime
from pathlib import Path

import config

NIVEIS = ("INFO", "AVISO", "ERRO")


def arquivo_do_dia(dia: datetime | None = None) -> Path:
    dia = dia or datetime.now()
    return config.LOGS / f"log_{dia:%Y-%m-%d}.txt"


def log(nivel: str, etapa: str, mes: str, mensagem: str) -> str:
    config.LOGS.mkdir(parents=True, exist_ok=True)
    linha = f"{datetime.now():%H:%M:%S} | {nivel:<5} | {etapa:<7} | {mes or '-':<7} | {mensagem}"
    with arquivo_do_dia().open("a", encoding="utf-8") as f:
        f.write(linha + "\n")
    return linha


def ler_log_do_dia() -> list[str]:
    arquivo = arquivo_do_dia()
    if not arquivo.exists():
        return []
    return arquivo.read_text(encoding="utf-8").splitlines()


def numero(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def reais(valor: float) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
