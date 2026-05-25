import sqlite3
from pathlib import Path

DB = "monitor.db"

def conectar():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def criar_tabelas():
    con = conectar()
    con.executescript("""
        CREATE TABLE IF NOT EXISTS produtos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            nome          TEXT NOT NULL,
            preco_meta    REAL NOT NULL,
            cupom         TEXT DEFAULT '',
            desconto_pct  REAL DEFAULT 0,
            ativo         INTEGER DEFAULT 1,
            criado_em     TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS historico (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL,
            loja       TEXT NOT NULL,
            loja_id    TEXT NOT NULL,
            preco      REAL NOT NULL,
            condicao   TEXT DEFAULT 'Novo',
            url        TEXT DEFAULT '',
            coletado_em TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (produto_id) REFERENCES produtos(id)
        );

        CREATE TABLE IF NOT EXISTS alertas_enviados (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL,
            chave      TEXT UNIQUE,
            enviado_em TEXT DEFAULT (datetime('now','localtime'))
        );
    """)
    con.commit()
    con.close()

# ── PRODUTOS ──────────────────────────────────────────────────────────────────
def listar_produtos():
    con = conectar()
    rows = con.execute("SELECT * FROM produtos WHERE ativo = 1 ORDER BY criado_em DESC").fetchall()
    con.close()
    return [dict(r) for r in rows]

def buscar_produto(produto_id: int):
    con = conectar()
    row = con.execute("SELECT * FROM produtos WHERE id = ?", (produto_id,)).fetchone()
    con.close()
    return dict(row) if row else None

def inserir_produto(nome, preco_meta, cupom="", desconto_pct=0):
    con = conectar()
    cur = con.execute(
        "INSERT INTO produtos (nome, preco_meta, cupom, desconto_pct) VALUES (?, ?, ?, ?)",
        (nome, preco_meta, cupom, desconto_pct)
    )
    con.commit()
    produto_id = cur.lastrowid
    con.close()
    return produto_id

def atualizar_produto(produto_id, nome, preco_meta, cupom, desconto_pct):
    con = conectar()
    con.execute(
        "UPDATE produtos SET nome=?, preco_meta=?, cupom=?, desconto_pct=? WHERE id=?",
        (nome, preco_meta, cupom, desconto_pct, produto_id)
    )
    con.commit()
    con.close()

def deletar_produto(produto_id):
    con = conectar()
    con.execute("UPDATE produtos SET ativo = 0 WHERE id = ?", (produto_id,))
    con.commit()
    con.close()

# ── HISTÓRICO ─────────────────────────────────────────────────────────────────
def inserir_historico(produto_id, loja, loja_id, preco, condicao, url):
    con = conectar()
    con.execute(
        "INSERT INTO historico (produto_id, loja, loja_id, preco, condicao, url) VALUES (?,?,?,?,?,?)",
        (produto_id, loja, loja_id, preco, condicao, url)
    )
    con.commit()
    con.close()

def historico_produto(produto_id, loja_id=None, limite=30):
    con = conectar()
    if loja_id:
        rows = con.execute(
            "SELECT * FROM historico WHERE produto_id=? AND loja_id=? ORDER BY coletado_em DESC LIMIT ?",
            (produto_id, loja_id, limite)
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT * FROM historico WHERE produto_id=? ORDER BY coletado_em DESC LIMIT ?",
            (produto_id, limite)
        ).fetchall()
    con.close()
    return [dict(r) for r in rows]

def menor_preco_historico(produto_id, loja_id=None):
    con = conectar()
    if loja_id:
        row = con.execute(
            "SELECT MIN(preco) as menor FROM historico WHERE produto_id=? AND loja_id=?",
            (produto_id, loja_id)
        ).fetchone()
    else:
        row = con.execute(
            "SELECT MIN(preco) as menor FROM historico WHERE produto_id=?",
            (produto_id,)
        ).fetchone()
    con.close()
    return row["menor"] if row else None

def ultimo_preco(produto_id, loja_id):
    con = conectar()
    row = con.execute(
        "SELECT preco FROM historico WHERE produto_id=? AND loja_id=? ORDER BY coletado_em DESC LIMIT 1",
        (produto_id, loja_id)
    ).fetchone()
    con.close()
    return row["preco"] if row else None

# ── ALERTAS ───────────────────────────────────────────────────────────────────
def alerta_ja_enviado(chave: str) -> bool:
    con = conectar()
    row = con.execute("SELECT id FROM alertas_enviados WHERE chave=?", (chave,)).fetchone()
    con.close()
    return row is not None

def registrar_alerta(produto_id: int, chave: str):
    con = conectar()
    try:
        con.execute("INSERT INTO alertas_enviados (produto_id, chave) VALUES (?,?)", (produto_id, chave))
        con.commit()
    except sqlite3.IntegrityError:
        pass
    con.close()

def limpar_alertas_produto(produto_id: int):
    con = conectar()
    con.execute("DELETE FROM alertas_enviados WHERE produto_id=?", (produto_id,))
    con.commit()
    con.close()