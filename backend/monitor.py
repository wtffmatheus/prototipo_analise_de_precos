import os, re, smtplib, logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import banco

load_dotenv()
log = logging.getLogger(__name__)

EMAIL_REMETENTE    = os.getenv("EMAIL_REMETENTE", "")
EMAIL_SENHA        = os.getenv("EMAIL_SENHA", "")
EMAIL_DESTINATARIO = os.getenv("EMAIL_DESTINATARIO", EMAIL_REMETENTE)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}

CUPONS_BASE = {
    "mercadolivre": [
        {"codigo": "MELI5",       "desc_pct": 5,  "desc_fixo": 0,  "condicao": "Qualquer compra",        "tipo": "percentual"},
        {"codigo": "MELIBEM",     "desc_pct": 10, "desc_fixo": 0,  "condicao": "Primeira compra do mês", "tipo": "percentual"},
        {"codigo": "APPML10",     "desc_pct": 10, "desc_fixo": 0,  "condicao": "Compra pelo app",        "tipo": "percentual"},
    ],
    "amazon": [
        {"codigo": "PRIMEIRACOMPRA", "desc_pct": 5,  "desc_fixo": 0,  "condicao": "Primeira compra Amazon", "tipo": "percentual"},
        {"codigo": "PRIME30",        "desc_pct": 0,  "desc_fixo": 30, "condicao": "Assinantes Prime",       "tipo": "fixo"},
        {"codigo": "APP10",          "desc_pct": 10, "desc_fixo": 0,  "condicao": "Compra pelo app",        "tipo": "percentual"},
    ],
    "kabum": [
        {"codigo": "KABUM10",   "desc_pct": 10, "desc_fixo": 0, "condicao": "Boleto/Pix",            "tipo": "percentual"},
        {"codigo": "KABUM5",    "desc_pct": 5,  "desc_fixo": 0, "condicao": "Qualquer compra",       "tipo": "percentual"},
        {"codigo": "KBMAGIC15", "desc_pct": 15, "desc_fixo": 0, "condicao": "Produtos selecionados", "tipo": "percentual"},
    ],
    "magalu": [
        {"codigo": "PRIMEIRACOMPRA", "desc_pct": 5,  "desc_fixo": 0, "condicao": "Primeira compra Magalu",     "tipo": "percentual"},
        {"codigo": "APP15",          "desc_pct": 15, "desc_fixo": 0, "condicao": "App Magalu – novos usuários", "tipo": "percentual"},
        {"codigo": "PIX5",           "desc_pct": 5,  "desc_fixo": 0, "condicao": "Pagamento via Pix",           "tipo": "percentual"},
    ],
    "olx": [
        {"codigo": "OLX30",    "desc_pct": 0, "desc_fixo": 30, "condicao": "Primeira compra OLX", "tipo": "fixo"},
        {"codigo": "OLX20OFF", "desc_pct": 0, "desc_fixo": 20, "condicao": "Cupom recorrente OLX","tipo": "fixo"},
        {"codigo": "OLXAPP",   "desc_pct": 5, "desc_fixo": 0,  "condicao": "Compra pelo app OLX", "tipo": "percentual"},
    ],
    "enjoei": [
        {"codigo": "PRIMEIROENJOI", "desc_pct": 10, "desc_fixo": 0, "condicao": "Primeira compra Enjoei", "tipo": "percentual"},
    ],
}

def limpar_preco(texto: str) -> Optional[float]:
    nums = re.sub(r"[^\d,]", "", texto).replace(",", ".")
    partes = nums.split(".")
    if len(partes) > 2:
        nums = "".join(partes[:-1]) + "." + partes[-1]
    try:
        return float(nums) if nums else None
    except ValueError:
        return None

def calc_preco_final(preco, cupom):
    if not cupom:
        return preco
    if cupom["tipo"] == "percentual":
        return preco * (1 - cupom["desc_pct"] / 100)
    if cupom["tipo"] == "fixo":
        return max(0, preco - cupom["desc_fixo"])
    return preco

def melhor_cupom(loja_id, preco):
    melhor, menor = None, preco
    for c in CUPONS_BASE.get(loja_id, []):
        if c["tipo"] == "frete":
            continue
        final = calc_preco_final(preco, c)
        if final < menor:
            menor, melhor = final, c
    return melhor

# ── SCRAPERS ──────────────────────────────────────────────────────────────────
def buscar_mercadolivre(nome):
    try:
        url = f"https://lista.mercadolivre.com.br/{nome.replace(' ','-')}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")
        item = soup.select_one(".ui-search-result__content")
        if not item:
            return None
        preco_el = item.select_one(".andes-money-amount__fraction")
        cents_el = item.select_one(".andes-money-amount__cents")
        titulo_el = item.select_one(".ui-search-item__title")
        link_el = item.select_one("a.ui-search-result__content")
        if not preco_el:
            return None
        val = preco_el.get_text(strip=True).replace(".", "")
        if cents_el:
            val += "." + cents_el.get_text(strip=True)
        return {"loja": "Mercado Livre", "loja_id": "mercadolivre", "preco": float(val),
                "titulo": titulo_el.get_text(strip=True) if titulo_el else nome,
                "url": link_el["href"] if link_el else url, "condicao": "Novo"}
    except Exception as e:
        log.warning(f"[ML] {e}")
        return None

def buscar_amazon(nome):
    try:
        url = f"https://www.amazon.com.br/s?k={nome.replace(' ','+')}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")
        for res in soup.select('[data-component-type="s-search-result"]')[:5]:
            preco_el  = res.select_one(".a-price-whole")
            titulo_el = res.select_one("h2 a span")
            link_el   = res.select_one("h2 a")
            if not preco_el:
                continue
            preco = limpar_preco(preco_el.get_text())
            if preco and preco > 10:
                return {"loja": "Amazon", "loja_id": "amazon", "preco": preco,
                        "titulo": titulo_el.get_text(strip=True) if titulo_el else nome,
                        "url": "https://www.amazon.com.br" + link_el["href"] if link_el else url,
                        "condicao": "Novo"}
    except Exception as e:
        log.warning(f"[Amazon] {e}")
    return None

def buscar_kabum(nome):
    try:
        url = f"https://www.kabum.com.br/busca/{nome.replace(' ','%20')}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")
        for sp, st, sl in [(".finalPrice",".nameCard","a.productLink"),(".sc-eBMEME",".sc-cdc4f3e9","a")]:
            pe = soup.select_one(sp)
            if pe:
                preco = limpar_preco(pe.get_text())
                if preco and preco > 10:
                    te = soup.select_one(st)
                    le = soup.select_one(sl)
                    link = "https://www.kabum.com.br" + le["href"] if le and le.get("href","").startswith("/") else url
                    return {"loja": "KaBuM!", "loja_id": "kabum", "preco": preco,
                            "titulo": te.get_text(strip=True) if te else nome,
                            "url": link, "condicao": "Novo"}
    except Exception as e:
        log.warning(f"[KaBuM] {e}")
    return None

def buscar_magalu(nome):
    try:
        url = f"https://www.magazineluiza.com.br/busca/{nome.replace(' ','%20')}/"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")
        for sp, st, sl in [('[data-testid="price-value"]',"h2","a"),(".sc-kpDqfB","h2","a")]:
            pe = soup.select_one(sp)
            if pe:
                preco = limpar_preco(pe.get_text())
                if preco and preco > 10:
                    te = soup.select_one(st)
                    le = soup.select_one(sl)
                    link = "https://www.magazineluiza.com.br" + le["href"] if le and le.get("href","").startswith("/") else url
                    return {"loja": "Magalu", "loja_id": "magalu", "preco": preco,
                            "titulo": te.get_text(strip=True) if te else nome,
                            "url": link, "condicao": "Novo"}
    except Exception as e:
        log.warning(f"[Magalu] {e}")
    return None

def buscar_olx(nome):
    try:
        url = f"https://www.olx.com.br/brasil?q={nome.replace(' ','+')}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")
        for sp, st, sl in [('[data-lurker-detail="price"]',"h2","a"),(".fnmrjs-0","h2","a")]:
            pe = soup.select_one(sp)
            if pe:
                preco = limpar_preco(pe.get_text())
                if preco and preco > 10:
                    te = soup.select_one(st)
                    le = soup.select_one(sl)
                    return {"loja": "OLX", "loja_id": "olx", "preco": preco,
                            "titulo": te.get_text(strip=True) if te else nome,
                            "url": le["href"] if le and le.get("href") else url,
                            "condicao": "Usado"}
    except Exception as e:
        log.warning(f"[OLX] {e}")
    return None

def buscar_enjoei(nome):
    try:
        url = f"https://www.enjoei.com.br/busca?q={nome.replace(' ','+')}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")
        pe = soup.select_one(".price")
        te = soup.select_one(".product-title")
        le = soup.select_one("a.product-card")
        if pe:
            preco = limpar_preco(pe.get_text())
            if preco and preco > 10:
                link = "https://www.enjoei.com.br" + le["href"] if le and le.get("href","").startswith("/") else url
                return {"loja": "Enjoei", "loja_id": "enjoei", "preco": preco,
                        "titulo": te.get_text(strip=True) if te else nome,
                        "url": link, "condicao": "Seminovo"}
    except Exception as e:
        log.warning(f"[Enjoei] {e}")
    return None

def buscar_em_todos(nome):
    resultados = []
    for fn in [buscar_mercadolivre, buscar_amazon, buscar_kabum, buscar_magalu, buscar_olx, buscar_enjoei]:
        res = fn(nome)
        if res:
            resultados.append(res)
    return sorted(resultados, key=lambda x: x["preco"])

# ── EMAIL ─────────────────────────────────────────────────────────────────────
def enviar_email(assunto, html):
    if not EMAIL_REMETENTE or not EMAIL_SENHA:
        log.error("Credenciais de email não configuradas!")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"]    = EMAIL_REMETENTE
    msg["To"]      = EMAIL_DESTINATARIO
    msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(EMAIL_REMETENTE, EMAIL_SENHA)
            s.sendmail(EMAIL_REMETENTE, EMAIL_DESTINATARIO, msg.as_string())
        log.info(f"✅ Email: {assunto}")
    except Exception as e:
        log.error(f"Falha email: {e}")

def montar_email_alerta(produto, resultados):
    nome  = produto["nome"]
    meta  = produto["preco_meta"]
    melhor = resultados[0]
    menor_hist = banco.menor_preco_historico(produto["id"])

    cupons_rows = ""
    for r in resultados:
        for c in CUPONS_BASE.get(r["loja_id"], []):
            final = calc_preco_final(r["preco"], c)
            if final <= meta and c["tipo"] != "frete":
                cupons_rows += f"""
                <tr>
                  <td style="padding:6px 10px;border-bottom:1px solid #eee;">{r['loja']}</td>
                  <td style="padding:6px 10px;border-bottom:1px solid #eee;font-family:monospace;background:#f9f9f9;">{c['codigo']}</td>
                  <td style="padding:6px 10px;border-bottom:1px solid #eee;color:#2e7d32;font-weight:700;">R$ {final:.2f}</td>
                  <td style="padding:6px 10px;border-bottom:1px solid #eee;font-size:12px;color:#777;">{c['condicao']}</td>
                </tr>"""

    lojas_rows = ""
    for r in resultados:
        mc = melhor_cupom(r["loja_id"], r["preco"])
        pc = calc_preco_final(r["preco"], mc) if mc else None
        cor = "#2e7d32" if r["preco"] <= meta else "#333"
        lojas_rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;">{r['loja']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;font-weight:700;color:{cor};">R$ {r['preco']:.2f}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;color:#777;">{r.get('condicao','')}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;">
            {"<b style='color:#1b5e20;'>R$ " + f"{pc:.2f}</b> c/ <code>" + mc['codigo'] + "</code>" if mc and pc else "—"}
          </td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;"><a href="{r['url']}" style="color:#1565c0;">Ver →</a></td>
        </tr>"""

    hist_bloco = f"<p>📉 Menor preço histórico registrado: <b>R$ {menor_hist:.2f}</b></p>" if menor_hist else ""
    cupons_bloco = f"""
    <h3 style="color:#2e7d32;">🎟️ Cupons que batem sua meta</h3>
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <tr style="background:#e8f5e9;">
        <th style="padding:6px 10px;text-align:left;">Loja</th>
        <th style="padding:6px 10px;text-align:left;">Cupom</th>
        <th style="padding:6px 10px;text-align:left;">Preço final</th>
        <th style="padding:6px 10px;text-align:left;">Condição</th>
      </tr>
      {cupons_rows}
    </table>""" if cupons_rows else ""

    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:650px;margin:0 auto;color:#212121;">
      <div style="background:#0d1b4b;color:#fff;padding:20px 24px;border-radius:8px 8px 0 0;">
        <h1 style="margin:0;font-size:1.3em;">🔔 Alerta de Preço — {nome}</h1>
        <p style="margin:4px 0 0;opacity:.8;">{datetime.now().strftime("%d/%m/%Y %H:%M")}</p>
      </div>
      <div style="border:1px solid #e0e0e0;border-top:none;padding:20px 24px;border-radius:0 0 8px 8px;">
        <p>Melhor preço: <b style="font-size:1.5em;color:#2e7d32;">R$ {melhor['preco']:.2f}</b> na <b>{melhor['loja']}</b></p>
        <p>Sua meta era <b>R$ {meta:.2f}</b> ✅</p>
        {hist_bloco}
        {cupons_bloco}
        <h3 style="margin-top:20px;">📊 Comparativo completo</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px;">
          <tr style="background:#f5f5f5;">
            <th style="padding:8px 12px;text-align:left;">Loja</th>
            <th style="padding:8px 12px;text-align:left;">Preço</th>
            <th style="padding:8px 12px;text-align:left;">Condição</th>
            <th style="padding:8px 12px;text-align:left;">Com cupom</th>
            <th style="padding:8px 12px;text-align:left;">Link</th>
          </tr>
          {lojas_rows}
        </table>
        <a href="{melhor['url']}" style="display:inline-block;margin-top:16px;background:#0d1b4b;
           color:#fff;padding:10px 22px;border-radius:6px;text-decoration:none;font-weight:bold;">
          Comprar agora →
        </a>
      </div>
    </body></html>"""

def montar_email_aproximando(produto, melhor, pct):
    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#212121;">
      <div style="background:#e65100;color:#fff;padding:20px 24px;border-radius:8px 8px 0 0;">
        <h1 style="margin:0;font-size:1.3em;">⚡ Preço se Aproximando!</h1>
      </div>
      <div style="border:1px solid #e0e0e0;border-top:none;padding:20px 24px;border-radius:0 0 8px 8px;">
        <h2 style="color:#e65100;">{produto['nome']}</h2>
        <p>Menor preço agora: <b>R$ {melhor['preco']:.2f}</b> na <b>{melhor['loja']}</b></p>
        <p>Falta <b style="color:#e65100;">{pct:.1f}%</b> para sua meta de <b>R$ {produto['preco_meta']:.2f}</b>.</p>
        <a href="{melhor['url']}" style="display:inline-block;background:#e65100;color:#fff;
           padding:10px 22px;border-radius:6px;text-decoration:none;font-weight:bold;">Ver produto →</a>
      </div>
    </body></html>"""

# ── CICLO DE MONITORAMENTO ────────────────────────────────────────────────────
def verificar_todos():
    log.info("🔍 Iniciando verificação...")
    produtos = banco.listar_produtos()
    if not produtos:
        log.info("Nenhum produto cadastrado.")
        return

    for p in produtos:
        log.info(f"  → {p['nome']}")
        resultados = buscar_em_todos(p["nome"])
        if not resultados:
            log.warning(f"  ⚠️ Sem resultados para '{p['nome']}'")
            continue

        for r in resultados:
            banco.inserir_historico(p["id"], r["loja"], r["loja_id"], r["preco"], r.get("condicao",""), r.get("url",""))

        melhor = resultados[0]
        meta   = p["preco_meta"]
        log.info(f"     Melhor: {melhor['loja']} R$ {melhor['preco']:.2f} | Meta: R$ {meta:.2f}")

        if melhor["preco"] <= meta:
            chave = f"{p['id']}_atingiu_{melhor['preco']:.0f}"
            if not banco.alerta_ja_enviado(chave):
                enviar_email(
                    f"✅ {p['nome']} — R$ {melhor['preco']:.2f} na {melhor['loja']}!",
                    montar_email_alerta(p, resultados)
                )
                banco.registrar_alerta(p["id"], chave)
        else:
            pct = ((melhor["preco"] - meta) / meta) * 100
            if pct <= 10:
                chave = f"{p['id']}_aprox_{round(pct,0)}"
                if not banco.alerta_ja_enviado(chave):
                    enviar_email(
                        f"⚡ {p['nome']} está {pct:.1f}% da meta!",
                        montar_email_aproximando(p, melhor, pct)
                    )
                    banco.registrar_alerta(p["id"], chave)

    log.info("✔️  Verificação concluída.\n")