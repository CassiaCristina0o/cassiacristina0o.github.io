import time
from pathlib import Path

import pandas as pd
import streamlit as st

MESES = ["202606", "202607", "202608"]

st.set_page_config(page_title="Cartão corporativo: o processo", layout="wide")
st.markdown("<style>[data-testid='stHeader']{display:none}.block-container{padding-top:1.5rem;padding-bottom:1rem}</style>",
            unsafe_allow_html=True)
EMBUTIDO = Path("modo_embutido.txt").exists()
if EMBUTIDO:
    st.markdown("<style>[data-testid='stElementContainer']:has(.stButton){width:100%}.stButton{display:flex;justify-content:center;width:100%}</style>", unsafe_allow_html=True)
if not EMBUTIDO:
    st.markdown("**ETL em Python que coleta e trata o uso do cartão corporativo do governo federal e entrega uma "
                "planilha Excel com os dados organizados em abas.** Clique em ▶ para ver o processo rodando aqui "
                "no seu navegador, com uma amostra de 3 meses. Por privacidade (LGPD), dados pessoais como nome "
                "e CPF foram ocultados.")
    st.markdown("[Ver o código no GitHub](https://github.com/CassiaCristina0o/analise-cartao-corporativo)")

resultados = []


def passo(nome, funcao):
    inicio = time.perf_counter()
    try:
        valor = funcao()
    except Exception as erro:
        resultados.append((nome, False, time.perf_counter() - inicio))
        st.error(f"❌ {nome}")
        st.exception(erro)
        return None
    resultados.append((nome, True, time.perf_counter() - inicio))
    st.markdown(f"✅ **{nome}** · {resultados[-1][2]:.2f} s")
    return valor


def importar_codigo():
    import banco, categorias, config, leitura, registro, relatorio
    return True


def descompactar_e_abrir():
    import leitura
    return {mes: leitura.ler_bruto(Path(f"demo/{mes}_CPGF.zip")) for mes in MESES}


def limpar_tudo(brutos):
    import leitura
    partes = []
    for mes, bruto in brutos.items():
        limpo = leitura.limpar(bruto)
        limpo["mes"] = mes
        limpo["arquivo_origem"] = f"{mes}_CPGF.zip"
        limpo["data_coleta"] = "2026-10-21 00:00:00"
        partes.append(limpo)
    return pd.concat(partes, ignore_index=True)


def categorizar(df):
    import categorias
    return categorias.aplicar(df, categorias.carregar_ufs(Path("demo/unidades_gestoras.csv")))


def montar_abas(df):
    import relatorio
    return relatorio.montar_abas(df)


def gerar_excel(df):
    import relatorio
    caminho = relatorio.gerar_excel(df)
    return caminho.read_bytes(), caminho.name


def tabela_simples(df):
    st.dataframe(df.head(5), hide_index=True, width="stretch")
    return True


def tabela_colorida(brutos):
    import leitura
    amostra = next(iter(brutos.values())).head(5)

    def pintar(coluna):
        cor = "#d6efd9" if coluna.name in leitura.COLUNAS_USADAS else "#f4d3d3"
        return [f"background-color: {cor}; color: #1b1b1b"] * len(coluna)

    st.dataframe(amostra.style.apply(pintar, axis=0), hide_index=True, width="stretch")
    return True


if st.button("▶ Ver como funciona", type="primary"):
    inicio_total = time.perf_counter()
    passo("Importar o código do robô", importar_codigo)
    brutos = passo("Descompactar e abrir os 3 ZIPs", descompactar_e_abrir)
    df = passo("Limpar os dados", lambda: limpar_tudo(brutos)) if brutos else None
    if df is not None:
        st.write(f"{len(df):,} transações nos 3 meses".replace(",", "."))
        df = passo("Categorias e estado", lambda: categorizar(df))
    if df is not None:
        abas = passo("Montar as 10 abas do Excel", lambda: montar_abas(df))
        excel = passo("Gerar o arquivo Excel", lambda: gerar_excel(df))
        if excel:
            dados, nome = excel
            st.write(f"{nome}: {len(dados) / 1024:.0f} KB")
            st.download_button("⬇️ Baixar o Excel", dados, file_name=nome,
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        passo("Mostrar uma tabela na tela (st.dataframe)", lambda: tabela_simples(df))
    if brutos:
        passo("Tabela com colunas coloridas (verde usa, vermelho descarta)", lambda: tabela_colorida(brutos))
    ok = sum(1 for _, bom, _ in resultados if bom)
    st.divider()
    st.subheader(f"Resultado: {ok} de {len(resultados)} passos funcionaram · {time.perf_counter() - inicio_total:.1f} s no total")
else:
    if EMBUTIDO:
        st.markdown("<style>.block-container{padding-top:34vh}</style>", unsafe_allow_html=True)
    else:
        st.info("Clique em **▶ Ver como funciona**.")
