import zipfile
from pathlib import Path
from typing import Callable

import pandas as pd

import banco
import registro

ETAPA = "leitura"

COLUNAS_ESPERADAS = [
    "CÓDIGO ÓRGÃO SUPERIOR", "NOME ÓRGÃO SUPERIOR", "CÓDIGO ÓRGÃO", "NOME ÓRGÃO",
    "CÓDIGO UNIDADE GESTORA", "NOME UNIDADE GESTORA", "ANO EXTRATO", "MÊS EXTRATO",
    "CPF PORTADOR", "NOME PORTADOR", "CNPJ OU CPF FAVORECIDO", "NOME FAVORECIDO",
    "TRANSAÇÃO", "DATA TRANSAÇÃO", "VALOR TRANSAÇÃO",
]

COLUNAS_MANTIDAS = {
    "CÓDIGO ÓRGÃO SUPERIOR": "cod_ministerio",
    "NOME ÓRGÃO SUPERIOR": "ministerio",
    "CÓDIGO ÓRGÃO": "cod_orgao",
    "NOME ÓRGÃO": "orgao",
    "CÓDIGO UNIDADE GESTORA": "cod_ug",
    "TRANSAÇÃO": "transacao",
}

COLUNAS_USADAS = list(COLUNAS_MANTIDAS) + ["ANO EXTRATO", "MÊS EXTRATO", "DATA TRANSAÇÃO", "VALOR TRANSAÇÃO"]
COLUNAS_DESCARTADAS = [c for c in COLUNAS_ESPERADAS if c not in COLUNAS_USADAS]
COLUNAS_PESSOAIS = ["CPF PORTADOR", "NOME PORTADOR", "CNPJ OU CPF FAVORECIDO", "NOME FAVORECIDO"]

OCULTO = "████████"
LINHAS_AMOSTRA = 6

Aviso = Callable[[str], None]
Mostrar = Callable[[str, dict], None]


class FormatoMudou(Exception):
    pass


def _sem_aviso(linha: str) -> None:
    pass


def converter_valor(texto: str) -> float:
    return float(str(texto).strip().replace(".", "").replace(",", "."))


def converter_data(texto) -> str | None:
    texto = "" if pd.isna(texto) else str(texto).strip()
    if not texto:
        return None
    dia, mes, ano = texto.split("/")
    return f"{ano}-{mes}-{dia}"


def ler_bruto(caminho: Path) -> pd.DataFrame:
    with zipfile.ZipFile(caminho) as zf:
        csvs = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if len(csvs) != 1:
            raise FormatoMudou(f"esperava 1 CSV no ZIP, encontrei {len(csvs)}")
        with zf.open(csvs[0]) as f:
            bruto = pd.read_csv(f, sep=";", encoding="latin1", dtype=str, keep_default_na=False)
    if list(bruto.columns) != COLUNAS_ESPERADAS:
        faltando = [c for c in COLUNAS_ESPERADAS if c not in bruto.columns]
        sobrando = [c for c in bruto.columns if c not in COLUNAS_ESPERADAS]
        raise FormatoMudou(f"colunas diferentes (faltando: {faltando}; novas: {sobrando})")
    return bruto


def limpar(bruto: pd.DataFrame) -> pd.DataFrame:
    limpo = bruto[list(COLUNAS_MANTIDAS)].rename(columns=COLUNAS_MANTIDAS)
    limpo = limpo.apply(lambda coluna: coluna.str.strip())
    limpo["periodo_extracao"] = bruto["ANO EXTRATO"].str.strip() + "-" + bruto["MÊS EXTRATO"].str.strip().str.zfill(2)
    limpo["data_compra"] = bruto["DATA TRANSAÇÃO"].map(converter_data)
    limpo["valor"] = bruto["VALOR TRANSAÇÃO"].map(converter_valor)
    return limpo


def ler_zip(caminho: Path) -> pd.DataFrame:
    return limpar(ler_bruto(caminho))


def _csv_do_zip(caminho: Path) -> tuple[str, int]:
    with zipfile.ZipFile(caminho) as zf:
        info = next(i for i in zf.infolist() if i.filename.lower().endswith(".csv"))
    return info.filename, info.file_size


def _mostrar_leitura(mostrar: Mostrar, mes: str, caminho: Path, bruto: pd.DataFrame,
                     limpo: pd.DataFrame, pulado: bool) -> None:
    nome_csv, tamanho_csv = _csv_do_zip(caminho)
    mostrar("descompactar", {"mes": mes, "zip": caminho.name, "zip_kb": round(caminho.stat().st_size / 1024),
                             "csv": nome_csv, "csv_kb": round(tamanho_csv / 1024)})
    amostra = bruto.head(LINHAS_AMOSTRA).copy()
    for coluna in COLUNAS_PESSOAIS:
        amostra[coluna] = OCULTO
    mostrar("abrir", {"mes": mes, "csv": nome_csv, "linhas": len(bruto), "colunas": len(bruto.columns),
                      "amostra": amostra})
    mostrar("coletar", {"mes": mes, "linhas": len(limpo), "total": float(limpo["valor"].sum()),
                        "sigilosas": int(limpo["data_compra"].isna().sum()),
                        "amostra": limpo.head(LINHAS_AMOSTRA), "pulado": pulado})


def ler_mes(mes: str, avisar: Aviso = _sem_aviso, forcar: bool = False, mostrar: Mostrar | None = None) -> str:
    controle = banco.controle_do_mes("cpgf", mes)
    if controle is None or not controle["arquivo"] or not Path(controle["arquivo"]).exists():
        return "sem arquivo"
    caminho = Path(controle["arquivo"])
    anterior = banco.leitura_do_mes(mes)
    if anterior is not None and anterior["etag"] == controle["etag"] and not forcar:
        avisar(registro.log("INFO", ETAPA, mes, f"já lido ({anterior['linhas']} linhas); pulado"))
        if mostrar:
            bruto = ler_bruto(caminho)
            _mostrar_leitura(mostrar, mes, caminho, bruto, limpar(bruto), pulado=True)
        return "pulado"

    try:
        bruto = ler_bruto(caminho)
        df = limpar(bruto)
    except (FormatoMudou, zipfile.BadZipFile, UnicodeDecodeError, ValueError) as erro:
        banco.salvar_pendencia(ETAPA, mes, "V6", str(erro))
        avisar(registro.log("ERRO", ETAPA, mes, f"formato mudou: {erro}; segue para o próximo"))
        return "formato mudou"

    if mostrar:
        _mostrar_leitura(mostrar, mes, caminho, bruto, df, pulado=False)
    df["mes"] = mes
    df["arquivo_origem"] = caminho.name
    df["data_coleta"] = controle["baixado_em"]
    linhas = list(df[list(banco.COLUNAS_TRANSACOES)].itertuples(index=False, name=None))
    banco.substituir_transacoes(mes, controle["etag"], linhas)

    sigilosas = int(df["data_compra"].isna().sum())
    total = df["valor"].sum()
    avisar(registro.log(
        "INFO", ETAPA, mes,
        f"{registro.numero(len(df))} linhas lidas · {registro.reais(total)} · "
        f"{registro.numero(sigilosas)} sem data (sigilo) · nome, CPF e favorecido descartados",
    ))
    return "lido"


def ler_tudo(meses: list[str], avisar: Aviso = _sem_aviso, mostrar: Mostrar | None = None) -> dict[str, str]:
    avisar(registro.log("INFO", ETAPA, "", f"início da leitura: {len(meses)} meses"))
    resultados = {mes: ler_mes(mes, avisar, mostrar=mostrar) for mes in meses}
    lidos = sum(r in ("lido", "pulado") for r in resultados.values())
    avisar(registro.log("INFO", ETAPA, "", f"fim da leitura: {lidos} de {len(meses)} meses no banco"))
    return resultados
