import logging
import threading
import time
import schedule

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

import banco
import monitor


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("monitor.log"),
        logging.StreamHandler()
    ]
)

banco.criar_tabelas()

app = FastAPI(title="Monitor de Preços")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

INTERVALO_MINUTOS = 30


class ProdutoIn(BaseModel):
    nome: str
    preco_meta: float
    email: str = ""
    cupom: str = ""
    desconto_pct: float = 0
    alerta_proximo_pct: float = 10
    aceita_usado: bool = True
    aceita_novo: bool = True


def loop_monitoramento():
    try:
        monitor.verificar_todos()
    except Exception as e:
        logging.exception(f"Erro na verificação inicial: {e}")

    schedule.every(INTERVALO_MINUTOS).minutes.do(monitor.verificar_todos)

    while True:
        schedule.run_pending()
        time.sleep(60)


thread = threading.Thread(target=loop_monitoramento, daemon=True)
thread.start()


@app.get("/")
def home():
    return {
        "mensagem": "API do Monitor de Preços online",
        "status": "/status",
        "docs": "/docs"
    }


@app.get("/status")
def status():
    return {
        "status": "online",
        "produtos": len(banco.listar_produtos())
    }


@app.get("/produtos")
def get_produtos():
    return banco.listar_produtos()


@app.post("/produtos")
def post_produto(body: ProdutoIn):
    pid = banco.inserir_produto(
        nome=body.nome,
        preco_meta=body.preco_meta,
        email=body.email,
        cupom=body.cupom,
        desconto_pct=body.desconto_pct,
        alerta_proximo_pct=body.alerta_proximo_pct,
        aceita_usado=body.aceita_usado,
        aceita_novo=body.aceita_novo,
    )

    return {
        "id": pid,
        "mensagem": "Produto adicionado com sucesso!",
    }


@app.put("/produtos/{produto_id}")
def put_produto(produto_id: int, body: ProdutoIn):
    if not banco.buscar_produto(produto_id):
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    banco.atualizar_produto(
        produto_id=produto_id,
        nome=body.nome,
        preco_meta=body.preco_meta,
        email=body.email,
        cupom=body.cupom,
        desconto_pct=body.desconto_pct,
        alerta_proximo_pct=body.alerta_proximo_pct,
        aceita_usado=body.aceita_usado,
        aceita_novo=body.aceita_novo,
    )

    banco.limpar_alertas_produto(produto_id)

    return {"mensagem": "Produto atualizado!"}


@app.delete("/produtos/{produto_id}")
def del_produto(produto_id: int):
    banco.deletar_produto(produto_id)
    return {"mensagem": "Produto removido!"}


@app.post("/buscar")
def buscar(body: ProdutoIn):
    """
    Rota principal do site.

    Cadastra o produto, busca preços reais via scrapers, salva histórico,
    retorna resultados ao frontend e dispara a verificação de alerta.
    """

    pid = banco.inserir_produto(
        nome=body.nome,
        preco_meta=body.preco_meta,
        email=body.email,
        cupom=body.cupom,
        desconto_pct=body.desconto_pct,
        alerta_proximo_pct=body.alerta_proximo_pct,
        aceita_usado=body.aceita_usado,
        aceita_novo=body.aceita_novo,
    )

    produto = banco.buscar_produto(pid)

    resultados = monitor.buscar_em_todos(body.nome)
    resultados = monitor.filtrar_por_condicao(produto, resultados)

    if not resultados:
        return {
            "id": pid,
            "produto_normalizado": body.nome,
            "meta": body.preco_meta,
            "email": body.email,
            "resultados": [],
            "analise": "Nenhum preço foi encontrado agora. O produto foi salvo e continuará sendo monitorado."
        }

    resultados = sorted(resultados, key=lambda x: x.get("preco_final", x["preco"]))

    for r in resultados:
        banco.inserir_historico(
            produto_id=pid,
            loja=r["loja"],
            loja_id=r["loja_id"],
            preco=r.get("preco_final", r["preco"]),
            condicao=r.get("condicao", ""),
            url=r.get("url", ""),
        )

    melhor = resultados[0]
    melhor_preco = melhor.get("preco_final", melhor["preco"])
    meta = body.preco_meta
    limite_proximo = meta * (1 + body.alerta_proximo_pct / 100)

    if melhor_preco <= meta:
        analise = (
            f"O melhor preço encontrado foi R$ {melhor_preco:.2f} na {melhor['loja']}. "
            f"Ele bateu sua meta de R$ {meta:.2f}. O produto foi salvo para alertas por email."
        )
    elif melhor_preco <= limite_proximo:
        analise = (
            f"O melhor preço encontrado foi R$ {melhor_preco:.2f} na {melhor['loja']}. "
            f"Ainda não bateu a meta de R$ {meta:.2f}, mas está próximo."
        )
    else:
        analise = (
            f"O melhor preço encontrado foi R$ {melhor_preco:.2f} na {melhor['loja']}. "
            f"Ainda está distante da meta de R$ {meta:.2f}, mas continuará sendo monitorado."
        )

    # Verificação em background para possível email.
    threading.Thread(target=monitor.verificar_todos, daemon=True).start()

    return {
        "id": pid,
        "produto_normalizado": body.nome,
        "meta": meta,
        "email": body.email,
        "alerta_proximo_pct": body.alerta_proximo_pct,
        "aceita_usado": body.aceita_usado,
        "aceita_novo": body.aceita_novo,
        "resultados": resultados,
        "analise": analise,
    }


@app.get("/produtos/{produto_id}/historico")
def get_historico(produto_id: int, loja_id: str = None):
    return banco.historico_produto(produto_id, loja_id, limite=60)


@app.get("/produtos/{produto_id}/cupons")
def get_cupons(produto_id: int):
    produto = banco.buscar_produto(produto_id)

    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    hist = banco.historico_produto(produto_id, limite=6)
    resultado = []

    for h in hist:
        loja_id = h["loja_id"]
        preco = h["preco"]

        for c in monitor.CUPONS_BASE.get(loja_id, []):
            final = monitor.calc_preco_final(preco, c)

            resultado.append({
                "loja": h["loja"],
                "loja_id": loja_id,
                "preco_base": preco,
                "preco_final_estimado": final,
                "bate_meta": final <= produto["preco_meta"],
                "observacao": "Cupom estimado. Confirme no checkout da loja.",
                **c,
            })

    return sorted(resultado, key=lambda x: x["preco_final_estimado"])


@app.post("/verificar")
def verificar_agora():
    threading.Thread(target=monitor.verificar_todos, daemon=True).start()
    return {"mensagem": "Verificação iniciada!"}
