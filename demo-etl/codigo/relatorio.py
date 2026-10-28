from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Callable

import pandas as pd

import banco
import categorias
import config
import leitura
import registro

ETAPA = "excel"
FORMATO_REAIS = '#,##0.00'
FORMATO_NUMERO = '#,##0'
FORMATO_DATA = 'dd/mm/yyyy'
FORMATO_PERCENTUAL = '0.0%'
SEM_DATA = "sem data (sigiloso)"

COLUNAS_DADOS = {
    "periodo_extracao": "Período de extração",
    "cod_ministerio": "Código ministério",
    "ministerio": "Ministério",
    "cod_orgao": "Código órgão",
    "orgao": "Órgão",
    "uf": "UF",
    "categoria": "Categoria",
    "data_compra": "Data da compra",
    "valor": "Valor (R$)",
    "arquivo_origem": "Arquivo de origem",
    "data_coleta": "Data da coleta",
}

Aviso = Callable[[str], None]


def _sem_aviso(linha: str) -> None:
    pass


def _resumo(df: pd.DataFrame, chaves: list[str], nomes: list[str]) -> pd.DataFrame:
    tabela = (df.groupby(chaves, dropna=False)
                .agg(transacoes=("valor", "size"), valor=("valor", "sum"))
                .reset_index())
    tabela["percentual"] = tabela["valor"] / df["valor"].sum() if len(df) else 0
    tabela.columns = nomes + ["Transações", "Valor (R$)", "% do valor"]
    return tabela


def aba_dados(df: pd.DataFrame) -> pd.DataFrame:
    dados = df[list(COLUNAS_DADOS)].copy()
    dados["data_compra"] = pd.to_datetime(dados["data_compra"], errors="coerce")
    dados["data_coleta"] = pd.to_datetime(dados["data_coleta"], errors="coerce")
    dados = dados.sort_values(["periodo_extracao", "cod_ministerio", "cod_orgao", "data_compra"])
    return dados.rename(columns=COLUNAS_DADOS)


def por_mes_extracao(df: pd.DataFrame) -> pd.DataFrame:
    return _resumo(df, ["periodo_extracao"], ["Período de extração"]).sort_values("Período de extração")


def por_mes_compra(df: pd.DataFrame) -> pd.DataFrame:
    base = df.assign(mes_compra=df["data_compra"].fillna("").str[:7].replace("", SEM_DATA))
    return _resumo(base, ["mes_compra"], ["Mês da compra"]).sort_values("Mês da compra")


def por_ministerio(df: pd.DataFrame) -> pd.DataFrame:
    return (_resumo(df, ["cod_ministerio", "ministerio"], ["Código ministério", "Ministério"])
            .sort_values("Valor (R$)", ascending=False))


def por_orgao(df: pd.DataFrame) -> pd.DataFrame:
    return (_resumo(df, ["cod_orgao", "orgao", "cod_ministerio", "ministerio"],
                    ["Código órgão", "Órgão", "Código ministério", "Ministério"])
            .sort_values("Valor (R$)", ascending=False))


def por_estado(df: pd.DataFrame) -> pd.DataFrame:
    return _resumo(df, ["uf"], ["UF"]).sort_values("Valor (R$)", ascending=False)


def por_tipo(df: pd.DataFrame) -> pd.DataFrame:
    tabela = _resumo(df, ["categoria"], ["Categoria"])
    ordem = tabela["Categoria"].map({g: i for i, g in enumerate(categorias.ORDEM_GRUPOS)})
    return tabela.assign(_ordem=ordem).sort_values("_ordem").drop(columns="_ordem")


def ministerio_x_tipo(df: pd.DataFrame) -> pd.DataFrame:
    tabela = df.pivot_table(index=["cod_ministerio", "ministerio"], columns="categoria",
                            values="valor", aggfunc="sum", fill_value=0)
    grupos = [g for g in categorias.ORDEM_GRUPOS if g in tabela.columns]
    tabela = tabela[grupos]
    tabela["Total"] = tabela.sum(axis=1)
    tabela = tabela.reset_index().rename(columns={"cod_ministerio": "Código ministério", "ministerio": "Ministério"})
    tabela.columns.name = None
    return tabela.sort_values("Total", ascending=False)


def pendencias() -> pd.DataFrame:
    linhas = banco.listar("pendencias")
    if not linhas:
        return pd.DataFrame([{"Situação": "Nenhuma pendência na última execução."}])
    tabela = pd.DataFrame(linhas).drop(columns="id")
    return tabela.rename(columns={"quando": "Quando", "etapa": "Etapa", "mes": "Mês",
                                  "variante": "Variante", "motivo": "Motivo"})


def _contagem(df: pd.DataFrame) -> Counter:
    colunas = ["cod_ministerio", "cod_orgao", "cod_ug", "transacao", "data_compra", "valor"]
    return Counter(df[colunas].itertuples(index=False, name=None))


def regerados() -> pd.DataFrame:
    linhas = []
    for versao in banco.listar("versoes"):
        base = {"Fonte": versao["fonte"], "Mês": versao["mes"], "Detectado em": versao["quando"],
                "ETag antigo": versao["etag_antigo"], "ETag novo": versao["etag_novo"]}
        controle = banco.controle_do_mes(versao["fonte"], versao["mes"])
        antigo, novo = Path(versao["arquivo_antigo"]), Path(controle["arquivo"]) if controle else None
        if versao["fonte"] != "cpgf" or not antigo.exists() or not novo or not novo.exists():
            linhas.append(base | {"Observação": "comparação linha a linha indisponível"})
            continue
        df_antigo, df_novo = leitura.ler_zip(antigo), leitura.ler_zip(novo)
        a, n = _contagem(df_antigo), _contagem(df_novo)
        linhas.append(base | {
            "Linhas antes": len(df_antigo), "Linhas depois": len(df_novo),
            "Linhas novas": sum((n - a).values()), "Linhas removidas": sum((a - n).values()),
            "Valor antes (R$)": df_antigo["valor"].sum(), "Valor depois (R$)": df_novo["valor"].sum(),
            "Diferença (R$)": df_novo["valor"].sum() - df_antigo["valor"].sum(),
        })
    if not linhas:
        return pd.DataFrame([{"Situação": "Nenhum arquivo regerado desde a primeira coleta."}])
    return pd.DataFrame(linhas)


def montar_abas(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "Dados": aba_dados(df),
        "Por mês de extração": por_mes_extracao(df),
        "Por mês de compra": por_mes_compra(df),
        "Por ministério": por_ministerio(df),
        "Por órgão": por_orgao(df),
        "Por estado": por_estado(df),
        "Por tipo": por_tipo(df),
        "Ministério x tipo": ministerio_x_tipo(df),
        "Pendências": pendencias(),
        "Regerados": regerados(),
    }


def _formato_da_coluna(nome: str) -> str | None:
    if "R$" in nome or nome in categorias.ORDEM_GRUPOS or nome == "Total":
        return FORMATO_REAIS
    if nome in ("Transações", "Linhas antes", "Linhas depois", "Linhas novas", "Linhas removidas"):
        return FORMATO_NUMERO
    if nome.startswith("%"):
        return FORMATO_PERCENTUAL
    return None


def _largura(tabela: pd.DataFrame, coluna: str) -> int:
    amostra = tabela[coluna].head(300).astype(str).str.len().max() if len(tabela) else 0
    return int(min(max(len(coluna), amostra if pd.notna(amostra) else 0) + 2, 60))


def _escrever_aba(escritor: pd.ExcelWriter, nome: str, tabela: pd.DataFrame) -> None:
    livro = escritor.book
    tabela.to_excel(escritor, sheet_name=nome, index=False, startrow=1, header=False)
    folha = escritor.sheets[nome]
    ultima_linha, ultima_coluna = len(tabela), len(tabela.columns) - 1
    cabecalho = livro.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": "#1F4E78",
                                  "text_wrap": True, "valign": "vcenter"})
    for indice, coluna in enumerate(tabela.columns):
        formato = _formato_da_coluna(coluna)
        folha.set_column(indice, indice, _largura(tabela, coluna),
                         livro.add_format({"num_format": formato}) if formato else None)
    if nome == "Dados" and len(tabela):
        folha.add_table(0, 0, ultima_linha, ultima_coluna, {
            "name": "Transacoes", "style": "Table Style Light 9",
            "columns": [{"header": c, "header_format": cabecalho} for c in tabela.columns],
        })
    else:
        for indice, coluna in enumerate(tabela.columns):
            folha.write(0, indice, coluna, cabecalho)
        folha.autofilter(0, 0, ultima_linha, ultima_coluna)
    folha.set_row(0, 32)
    folha.freeze_panes(1, 0)


def gerar_excel(df: pd.DataFrame, avisar: Aviso = _sem_aviso, mostrar=None) -> Path:
    config.SAIDA.mkdir(parents=True, exist_ok=True)
    caminho = config.SAIDA / f"consolidado_{datetime.now():%Y-%m-%d}.xlsx"
    avisar(registro.log("INFO", ETAPA, "", "montando as 10 abas"))
    abas = montar_abas(df)
    with pd.ExcelWriter(caminho, engine="xlsxwriter", datetime_format=FORMATO_DATA,
                        date_format=FORMATO_DATA) as escritor:
        for indice, (nome, tabela) in enumerate(abas.items(), start=1):
            if mostrar:
                mostrar("aba", {"nome": nome, "indice": indice, "total": len(abas), "linhas": len(tabela),
                                "amostra": tabela.head(6)})
            _escrever_aba(escritor, nome, tabela)
            avisar(registro.log("INFO", ETAPA, "", f"aba {nome!r}: {registro.numero(len(tabela))} linhas, colunas formatadas"))
    avisar(registro.log("INFO", ETAPA, "", f"Excel pronto: {caminho.name} "
                        f"({registro.numero(round(caminho.stat().st_size / 1024))} KB)"))
    if mostrar:
        mostrar("excel", {"arquivo": caminho.name, "kb": round(caminho.stat().st_size / 1024), "abas": list(abas)})
    return caminho
