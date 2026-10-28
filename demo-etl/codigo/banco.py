import sqlite3
from contextlib import contextmanager
from datetime import datetime

import config

TABELAS = """
CREATE TABLE IF NOT EXISTS controle (
    fonte TEXT NOT NULL,
    mes TEXT NOT NULL,
    etag TEXT,
    tamanho INTEGER,
    arquivo TEXT,
    baixado_em TEXT,
    situacao TEXT NOT NULL,
    PRIMARY KEY (fonte, mes)
);
CREATE TABLE IF NOT EXISTS pendencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quando TEXT NOT NULL,
    etapa TEXT NOT NULL,
    mes TEXT,
    variante TEXT NOT NULL,
    motivo TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS versoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fonte TEXT NOT NULL,
    mes TEXT NOT NULL,
    etag_antigo TEXT,
    etag_novo TEXT,
    arquivo_antigo TEXT,
    quando TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS leituras (
    mes TEXT PRIMARY KEY,
    etag TEXT,
    linhas INTEGER NOT NULL,
    lido_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transacoes (
    mes TEXT NOT NULL,
    periodo_extracao TEXT NOT NULL,
    cod_ministerio TEXT,
    ministerio TEXT,
    cod_orgao TEXT,
    orgao TEXT,
    cod_ug TEXT,
    transacao TEXT,
    data_compra TEXT,
    valor REAL NOT NULL,
    arquivo_origem TEXT NOT NULL,
    data_coleta TEXT
);
CREATE INDEX IF NOT EXISTS idx_transacoes_mes ON transacoes (mes);
"""

COLUNAS_TRANSACOES = (
    "mes", "periodo_extracao", "cod_ministerio", "ministerio", "cod_orgao", "orgao",
    "cod_ug", "transacao", "data_compra", "valor", "arquivo_origem", "data_coleta",
)


def agora() -> str:
    return f"{datetime.now():%Y-%m-%d %H:%M:%S}"


@contextmanager
def conectar():
    config.DADOS.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(config.BANCO)
    conexao.row_factory = sqlite3.Row
    try:
        conexao.executescript(TABELAS)
        yield conexao
        conexao.commit()
    finally:
        conexao.close()


def controle_do_mes(fonte: str, mes: str) -> sqlite3.Row | None:
    with conectar() as c:
        return c.execute(
            "SELECT * FROM controle WHERE fonte = ? AND mes = ?", (fonte, mes)
        ).fetchone()


def salvar_controle(fonte: str, mes: str, situacao: str, etag: str | None = None,
                    tamanho: int | None = None, arquivo: str | None = None) -> None:
    with conectar() as c:
        c.execute(
            """INSERT INTO controle (fonte, mes, etag, tamanho, arquivo, baixado_em, situacao)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (fonte, mes) DO UPDATE SET
                   etag = COALESCE(excluded.etag, controle.etag),
                   tamanho = COALESCE(excluded.tamanho, controle.tamanho),
                   arquivo = COALESCE(excluded.arquivo, controle.arquivo),
                   baixado_em = COALESCE(excluded.baixado_em, controle.baixado_em),
                   situacao = excluded.situacao""",
            (fonte, mes, etag, tamanho, arquivo, agora() if arquivo else None, situacao),
        )


def limpar_pendencias() -> None:
    with conectar() as c:
        c.execute("DELETE FROM pendencias")


def salvar_pendencia(etapa: str, mes: str, variante: str, motivo: str) -> None:
    with conectar() as c:
        c.execute(
            "INSERT INTO pendencias (quando, etapa, mes, variante, motivo) VALUES (?, ?, ?, ?, ?)",
            (agora(), etapa, mes, variante, motivo),
        )


def salvar_versao(fonte: str, mes: str, etag_antigo: str, etag_novo: str, arquivo_antigo: str) -> None:
    with conectar() as c:
        c.execute(
            """INSERT INTO versoes (fonte, mes, etag_antigo, etag_novo, arquivo_antigo, quando)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (fonte, mes, etag_antigo, etag_novo, arquivo_antigo, agora()),
        )


def leitura_do_mes(mes: str) -> sqlite3.Row | None:
    with conectar() as c:
        return c.execute("SELECT * FROM leituras WHERE mes = ?", (mes,)).fetchone()


def substituir_transacoes(mes: str, etag: str, linhas: list[tuple]) -> None:
    marcadores = ", ".join("?" for _ in COLUNAS_TRANSACOES)
    with conectar() as c:
        c.execute("DELETE FROM transacoes WHERE mes = ?", (mes,))
        c.executemany(
            f"INSERT INTO transacoes ({', '.join(COLUNAS_TRANSACOES)}) VALUES ({marcadores})", linhas
        )
        c.execute(
            """INSERT INTO leituras (mes, etag, linhas, lido_em) VALUES (?, ?, ?, ?)
               ON CONFLICT (mes) DO UPDATE SET etag = excluded.etag,
                   linhas = excluded.linhas, lido_em = excluded.lido_em""",
            (mes, etag, len(linhas), agora()),
        )


def listar(tabela: str) -> list[dict]:
    with conectar() as c:
        return [dict(r) for r in c.execute(f"SELECT * FROM {tabela} ORDER BY 1, 2")]
