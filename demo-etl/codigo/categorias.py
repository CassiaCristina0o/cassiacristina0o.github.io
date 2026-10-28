import csv
from pathlib import Path
from typing import Callable

import pandas as pd

import banco
import config
import registro

ETAPA = "categ"

GRUPOS = {
    "COMPRA A/V - R$ - APRES": "Compra nacional",
    "COMP A/V-SOL DISP C/CLI-R$ ANT VENC": "Compra nacional",
    "COMPRA A/V - INT$ - APRES": "Compra internacional",
    "SAQUE CASH/ATM BB": "Saque",
    "SAQUE - INT$ - APRES": "Saque",
    "SAQUE MANUAL-CARTOES BB NA AGENCIA": "Saque",
    "Informações protegidas por sigilo": "Sigiloso",
}
NAO_CLASSIFICADO = "Não classificado"
UF_NAO_ENCONTRADA = "não encontrada"
ORDEM_GRUPOS = ["Compra nacional", "Compra internacional", "Saque", "Sigiloso", NAO_CLASSIFICADO]

Aviso = Callable[[str], None]


def _sem_aviso(linha: str) -> None:
    pass


def _codigo(texto: str) -> str:
    return str(texto).strip().lstrip("0") or "0"


def grupo_da_transacao(transacao: str) -> str:
    return GRUPOS.get(str(transacao).strip(), NAO_CLASSIFICADO)


def carregar_ufs(caminho: Path | None = None) -> dict[str, str]:
    caminho = caminho or config.TESOURO / "unidades_gestoras.csv"
    if not caminho.exists():
        return {}
    with caminho.open(encoding="utf-8", newline="") as f:
        leitor = csv.DictReader(f)
        return {_codigo(linha["UG"]): linha["UF"].strip() for linha in leitor if linha.get("UF", "").strip()}


def aplicar(df: pd.DataFrame, ufs: dict[str, str], avisar: Aviso = _sem_aviso) -> pd.DataFrame:
    df = df.copy()
    df["categoria"] = df["transacao"].map(grupo_da_transacao)
    df["uf"] = df["cod_ug"].map(lambda c: ufs.get(_codigo(c), UF_NAO_ENCONTRADA))

    novos_tipos = sorted(df.loc[df["categoria"] == NAO_CLASSIFICADO, "transacao"].unique())
    for tipo in novos_tipos:
        avisar(registro.log("AVISO", ETAPA, "", f"tipo de transação novo, sem grupo: {tipo!r}"))

    for mes, grupo in df.groupby("mes"):
        partes = [f"{registro.numero(int((grupo['categoria'] == g).sum()))} {g.lower()}"
                  for g in ORDEM_GRUPOS if (grupo["categoria"] == g).any()]
        sem_uf = grupo[grupo["uf"] == UF_NAO_ENCONTRADA]
        avisar(registro.log("INFO", ETAPA, mes, " · ".join(partes) + f" · {grupo['uf'].nunique()} UFs"))
        if len(sem_uf):
            unidades = sorted(sem_uf["cod_ug"].unique())
            motivo = f"{len(sem_uf)} linhas de {len(unidades)} unidade(s) fora da tabela do Tesouro: {', '.join(unidades[:10])}"
            banco.salvar_pendencia(ETAPA, mes, "V8", motivo)
            avisar(registro.log("AVISO", ETAPA, mes, f"UF não encontrada: {motivo}"))
    return df


def carregar_e_aplicar(avisar: Aviso = _sem_aviso, mostrar=None) -> pd.DataFrame:
    with banco.conectar() as c:
        df = pd.read_sql_query("SELECT * FROM transacoes ORDER BY mes", c)
    ufs = carregar_ufs()
    avisar(registro.log("INFO", ETAPA, "", f"início: {registro.numero(len(df))} linhas · "
                        f"{registro.numero(len(ufs))} unidades gestoras na tabela do Tesouro"))
    if not ufs:
        avisar(registro.log("AVISO", ETAPA, "", "tabela do Tesouro ausente; todas as UFs ficam como não encontradas"))
    resultado = aplicar(df, ufs, avisar)
    if mostrar and len(resultado):
        presentes = [g for g in ORDEM_GRUPOS if g in set(resultado["categoria"])]
        por_categoria = (resultado.groupby("categoria")["valor"].agg(["size", "sum"])
                         .reindex(presentes).reset_index())
        por_categoria.columns = ["Categoria", "Transações", "Valor (R$)"]
        mostrar("organizar", {"linhas": len(resultado), "ufs": int(resultado["uf"].nunique()),
                              "categorias": por_categoria,
                              "amostra": resultado[["periodo_extracao", "ministerio", "orgao", "uf",
                                                    "categoria", "valor"]].sample(6, random_state=1)})
    return resultado
