from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DADOS = RAIZ / "dados"
HISTORICO = DADOS / "historico"
ZIPS = HISTORICO / "zips"
VERSOES = HISTORICO / "versoes"
TESOURO = HISTORICO / "tesouro"
SAIDA = DADOS / "saida"
LOGS = DADOS / "logs"
BANCO = DADOS / "banco.db"

URL_CPGF = "https://portaldatransparencia.gov.br/download-de-dados/cpgf/{mes}"
URL_TESOURO = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/"
    "54a699f4-55e3-41cc-a900-27c123545472/resource/"
    "7b83145e-6dc5-4ad2-9730-77132188eb2f/download/siafirelatoriounidadesgestoras.csv"
)

INICIO = date(2025, 9, 1)
FIM = date(2026, 8, 1)
MES_NAO_PUBLICADO = "202609"

TENTATIVAS = 3
ESPERA_SEGUNDOS = 2
TIMEOUT_SEGUNDOS = 60
CABECALHOS = {"User-Agent": "Mozilla/5.0 (analise-cartao-corporativo)"}


def meses_do_periodo(inicio: date = INICIO, fim: date = FIM) -> list[str]:
    meses = []
    atual = inicio
    while atual <= fim:
        meses.append(f"{atual:%Y%m}")
        ano, mes = (atual.year + 1, 1) if atual.month == 12 else (atual.year, atual.month + 1)
        atual = date(ano, mes, 1)
    return meses
