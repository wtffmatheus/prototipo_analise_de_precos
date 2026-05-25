import logging
import threading
import time
import schedule

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
        alerta_proximo_pct=body.alerta_proximo_pct,
        aceita_usado=body.aceita_usado,
        aceita_novo=body.aceita_novo,
    )
    return {"id": pid, "mensagem": "Produto adicionado com sucesso!"}


@app.put("/produtos/{produto_id}")
def put_produto(produto_id: int, body: ProdutoIn):
    if not banco.buscar_produto(produto_id):
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    banco.atualizar_produto(
        produto_id=produto_id,
        nome=body.nome,
        preco_meta=body.preco_meta,
        email=body.email,
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
    Cadastra o produto, busca preços reais, salva histórico,
    retorna resultados. simulacao=False sempre — sem fallback fake.
    """
    pid = banco.inserir_produto(
        nome=body.nome,
        preco_meta=body.preco_meta,
        email=body.email,
        alerta_proximo_pct=body.alerta_proximo_pct,
        aceita_usado=body.aceita_usado,
        aceita_novo=body.aceita_novo,
    )

    produto = banco.buscar_produto(pid)

    resultados = monitor.buscar_em_todos(body.nome)
    resultados = monitor.filtrar_por_condicao(produto, resultados)

    # Sem resultados: retorna vazio honestamente, sem simulação
    if not resultados:
        return {
            "id": pid,
            "produto_normalizado": body.nome,
            "meta": body.preco_meta,
            "email": body.email,
            "simulacao": False,
            "resultados": [],
            "analise": (
                "Nenhum preço foi encontrado agora nas lojas monitoradas. "
                "Isso pode ocorrer por bloqueio temporário dos sites ou ausência do produto. "
                "O produto foi salvo e será verificado automaticamente a cada 30 minutos."
            )
        }

    resultados = sorted(resultados, key=lambda x: x.get("preco_final", x["preco"]))

    for r in resultados:
        banco.inserir_historico(
            produto_id=pid,
            loja=r["loja"],
            loja_id=r["loja_id"],
            preco=r["preco_final"],
            condicao=r.get("condicao", ""),
            url=r.get("url", ""),
        )

    melhor = resultados[0]
    melhor_preco = melhor["preco_final"]
    meta = body.preco_meta
    limite_proximo = meta * (1 + body.alerta_proximo_pct / 100)

    if melhor_preco <= meta:
        analise = (
            f"✅ O melhor preço encontrado foi R$ {melhor_preco:.2f} na {melhor['loja']}. "
            f"Ele bateu sua meta de R$ {meta:.2f}! O produto está salvo para alertas por email."
        )
    elif melhor_preco <= limite_proximo:
        analise = (
            f"👀 O melhor preço encontrado foi R$ {melhor_preco:.2f} na {melhor['loja']}. "
            f"Ainda não bateu a meta de R$ {meta:.2f}, mas está próximo ({body.alerta_proximo_pct:.0f}% de margem)."
        )
    else:
        diff_pct = ((melhor_preco - meta) / meta) * 100
        analise = (
            f"📊 O melhor preço encontrado foi R$ {melhor_preco:.2f} na {melhor['loja']}. "
            f"Ainda está {diff_pct:.1f}% acima da meta de R$ {meta:.2f}. "
            f"O produto continuará sendo monitorado a cada 30 minutos."
        )

    # Dispara verificação em background para possível envio de email
    threading.Thread(target=monitor.verificar_todos, daemon=True).start()

    return {
        "id": pid,
        "produto_normalizado": body.nome,
        "meta": meta,
        "email": body.email,
        "alerta_proximo_pct": body.alerta_proximo_pct,
        "aceita_usado": body.aceita_usado,
        "aceita_novo": body.aceita_novo,
        "simulacao": False,
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
            # FIX: calc_preco_final não existe — cupons nunca alteram o preço,
            # então preco_final_estimado == preco (exibido como referência apenas)
            resultado.append({
                "loja": h["loja"],
                "loja_id": loja_id,
                "preco_real": preco,
                "preco_final_estimado": preco,  # cupom NÃO é aplicado
                "bate_meta": preco <= produto["preco_meta"],
                "observacao": "Cupom estimado. Confirme no checkout da loja. Preço não alterado.",
                **c,
            })

    return sorted(resultado, key=lambda x: x["preco_real"])


@app.post("/verificar")
def verificar_agora():
    threading.Thread(target=monitor.verificar_todos, daemon=True).start()
    return {"mensagem": "Verificação iniciada!"}