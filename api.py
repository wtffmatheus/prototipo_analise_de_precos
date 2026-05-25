import logging, threading, time, schedule
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import banco
import monitor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("monitor.log"), logging.StreamHandler()]
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

def loop_monitoramento():
    monitor.verificar_todos()
    schedule.every(INTERVALO_MINUTOS).minutes.do(monitor.verificar_todos)
    while True:
        schedule.run_pending()
        time.sleep(60)

thread = threading.Thread(target=loop_monitoramento, daemon=True)
thread.start()

class ProdutoIn(BaseModel):
    nome:         str
    preco_meta:   float
    cupom:        str   = ""
    desconto_pct: float = 0

@app.get("/produtos")
def get_produtos():
    return banco.listar_produtos()

@app.post("/produtos")
def post_produto(body: ProdutoIn):
    pid = banco.inserir_produto(body.nome, body.preco_meta, body.cupom, body.desconto_pct)
    return {"id": pid, "mensagem": "Produto adicionado com sucesso!"}

@app.put("/produtos/{produto_id}")
def put_produto(produto_id: int, body: ProdutoIn):
    if not banco.buscar_produto(produto_id):
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    banco.atualizar_produto(produto_id, body.nome, body.preco_meta, body.cupom, body.desconto_pct)
    banco.limpar_alertas_produto(produto_id)
    return {"mensagem": "Produto atualizado!"}

@app.delete("/produtos/{produto_id}")
def del_produto(produto_id: int):
    banco.deletar_produto(produto_id)
    return {"mensagem": "Produto removido!"}

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
        lid = h["loja_id"]
        preco = h["preco"]
        for c in monitor.CUPONS_BASE.get(lid, []):
            final = monitor.calc_preco_final(preco, c)
            resultado.append({
                "loja": h["loja"], "loja_id": lid,
                "preco_base": preco, "preco_final": final,
                "bate_meta": final <= produto["preco_meta"],
                **c
            })
    return sorted(resultado, key=lambda x: x["preco_final"])

@app.post("/verificar")
def verificar_agora():
    threading.Thread(target=monitor.verificar_todos, daemon=True).start()
    return {"mensagem": "Verificação iniciada!"}

@app.get("/status")
def status():
    return {"status": "online", "produtos": len(banco.listar_produtos())}