import os
import re
import smtplib
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from urllib.parse import quote_plus

from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup

import banco

load_dotenv()
log = logging.getLogger(__name__)

EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE", "")
EMAIL_SENHA = os.getenv("EMAIL_SENHA", "")
EMAIL_DESTINATARIO_PADRAO = os.getenv("EMAIL_DESTINATARIO", EMAIL_REMETENTE)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}

# ATENÇÃO:
# Estes cupons são estimativas/sugestões. Sem API oficial das lojas, não dá para garantir validade.
# O sistema mostra preço final estimado e recomenda confirmar o cupom no checkout.
CUPONS_BASE = {
    "mercadolivre": [
        {"codigo": "MELI5", "desc_pct": 5, "desc_fixo": 0, "condicao": "Cupom estimado Mercado Livre", "tipo": "percentual"},
        {"codigo": "APPML10", "desc_pct": 10, "desc_fixo": 0, "condicao": "Estimado para compra pelo app", "tipo": "percentual"},
    ],
    "amazon": [
        {"codigo": "APP10", "desc_pct": 10, "desc_fixo": 0, "condicao": "Cupom estimado Amazon App", "tipo": "percentual"},
        {"codigo": "PRIME30", "desc_pct": 0, "desc_fixo": 30, "condicao": "Estimado para assinantes Prime", "tipo": "fixo"},
    ],
    "kabum": [
        {"codigo": "KABUM10", "desc_pct": 10, "desc_fixo": 0, "condicao": "Estimado para Pix/Boleto", "tipo": "percentual"},
        {"codigo": "KABUM5", "desc_pct": 5, "desc_fixo": 0, "condicao": "Cupom estimado KaBuM", "tipo": "percentual"},
    ],
    "magalu": [
        {"codigo": "APP15", "desc_pct": 15, "desc_fixo": 0, "condicao": "Estimado para app Magalu", "tipo": "percentual"},
        {"codigo": "PIX5", "desc_pct": 5, "desc_fixo": 0, "condicao": "Estimado para Pix", "tipo": "percentual"},
    ],
    "olx": [
        {"codigo": "OLXAPP", "desc_pct": 5, "desc_fixo": 0, "condicao": "Estimado para app OLX", "tipo": "percentual"},
    ],
    "enjoei": [
        {"codigo": "PRIMEIROENJOI", "desc_pct": 10, "desc_fixo": 0, "condicao": "Estimado para primeira compra", "tipo": "percentual"},
    ],
}


def limpar_preco(texto: str) -> Optional[float]:
    if not texto:
        return None

    texto = texto.replace("\xa0", " ")
    nums = re.sub(r"[^\d,\.]", "", texto)

    if "," in nums:
        nums = nums.replace(".", "").replace(",", ".")
    else:
        # Ex: 1.299 -> 1299
        partes = nums.split(".")
        if len(partes) > 2 or (len(partes) == 2 and len(partes[-1]) == 3):
            nums = "".join(partes)

    try:
        preco = float(nums)
        return preco if preco > 0 else None
    except ValueError:
        return None


def normalizar_url(base, href, fallback):
    if not href:
        return fallback

    if href.startswith("http"):
        return href

    if href.startswith("/"):
        return base.rstrip("/") + href

    return fallback


def calc_preco_final(preco, cupom):
    if not cupom:
        return preco

    if cupom["tipo"] == "percentual":
        return round(preco * (1 - cupom["desc_pct"] / 100), 2)

    if cupom["tipo"] == "fixo":
        return round(max(0, preco - cupom["desc_fixo"]), 2)

    return preco


def melhor_cupom(loja_id, preco):
    melhor = None
    menor = preco

    for c in CUPONS_BASE.get(loja_id, []):
        final = calc_preco_final(preco, c)

        if final < menor:
            menor = final
            melhor = c

    return melhor


def enriquecer_resultado_com_cupom(resultado):
    cupom = melhor_cupom(resultado["loja_id"], resultado["preco"])
    preco_final = calc_preco_final(resultado["preco"], cupom) if cupom else resultado["preco"]

    resultado["melhor_cupom"] = cupom
    resultado["preco_final"] = round(preco_final, 2)
    resultado["cupom_confirmado"] = False
    resultado["observacao_cupom"] = (
        "Preço com cupom é estimado. Confirme o cupom no checkout da loja."
        if cupom
        else ""
    )

    return resultado


def filtrar_por_condicao(produto, resultados):
    aceita_usado = bool(produto.get("aceita_usado", True))
    aceita_novo = bool(produto.get("aceita_novo", True))
    filtrados = []

    for r in resultados:
        condicao = str(r.get("condicao", "")).lower()
        eh_usado = "usado" in condicao or "seminovo" in condicao
        eh_novo = "novo" in condicao and "seminovo" not in condicao

        if eh_usado and aceita_usado:
            filtrados.append(r)
        elif eh_novo and aceita_novo:
            filtrados.append(r)
        elif not eh_usado and not eh_novo:
            filtrados.append(r)

    return filtrados


def calcular_preco_sugerido(meta, melhor_preco, menor_historico=None):
    if melhor_preco <= meta:
        return round(melhor_preco, 2)

    if menor_historico and menor_historico < meta:
        return round(menor_historico, 2)

    return round(meta, 2)


# ── SCRAPERS ──────────────────────────────────────────────────────────────────

def buscar_mercadolivre(nome):
    try:
        termo = quote_plus(nome).replace("+", "-")
        url = f"https://lista.mercadolivre.com.br/{termo}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")

        item = soup.select_one("li.ui-search-layout__item") or soup.select_one(".ui-search-result__wrapper")
        if not item:
            return None

        preco_el = item.select_one(".andes-money-amount__fraction")
        cents_el = item.select_one(".andes-money-amount__cents")
        titulo_el = item.select_one(".ui-search-item__title, h2")
        link_el = item.select_one("a[href*='/MLB-'], a.ui-search-link, a[href]")

        if not preco_el:
            return None

        val = preco_el.get_text(strip=True).replace(".", "")
        if cents_el:
            val += "." + cents_el.get_text(strip=True)

        return {
            "loja": "Mercado Livre",
            "loja_id": "mercadolivre",
            "preco": float(val),
            "titulo": titulo_el.get_text(strip=True) if titulo_el else nome,
            "url": link_el["href"] if link_el and link_el.get("href") else url,
            "condicao": "Novo",
        }

    except Exception as e:
        log.warning(f"[Mercado Livre] {e}")
        return None


def buscar_amazon(nome):
    try:
        url = f"https://www.amazon.com.br/s?k={quote_plus(nome)}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")

        for res in soup.select('[data-component-type="s-search-result"]')[:8]:
            preco_whole = res.select_one(".a-price-whole")
            preco_frac = res.select_one(".a-price-fraction")
            titulo_el = res.select_one("h2 a span")
            link_el = res.select_one("h2 a[href]")

            if not preco_whole:
                continue

            texto_preco = preco_whole.get_text(strip=True)
            if preco_frac:
                texto_preco += "," + preco_frac.get_text(strip=True)

            preco = limpar_preco(texto_preco)

            if preco and preco > 10:
                return {
                    "loja": "Amazon",
                    "loja_id": "amazon",
                    "preco": preco,
                    "titulo": titulo_el.get_text(strip=True) if titulo_el else nome,
                    "url": normalizar_url("https://www.amazon.com.br", link_el.get("href") if link_el else "", url),
                    "condicao": "Novo",
                }

    except Exception as e:
        log.warning(f"[Amazon] {e}")

    return None


def buscar_kabum(nome):
    try:
        url = f"https://www.kabum.com.br/busca/{quote_plus(nome)}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")

        item = soup.select_one("article, .productCard, [data-testid='product-card']")
        area = item or soup

        preco_el = area.select_one(".finalPrice, [data-testid='price'], .priceCard")
        titulo_el = area.select_one(".nameCard, [data-testid='product-name'], h2, h3")
        link_el = area.select_one("a.productLink[href], a[href*='/produto/'], a[href]")

        if preco_el:
            preco = limpar_preco(preco_el.get_text())
            if preco and preco > 10:
                return {
                    "loja": "KaBuM!",
                    "loja_id": "kabum",
                    "preco": preco,
                    "titulo": titulo_el.get_text(strip=True) if titulo_el else nome,
                    "url": normalizar_url("https://www.kabum.com.br", link_el.get("href") if link_el else "", url),
                    "condicao": "Novo",
                }

    except Exception as e:
        log.warning(f"[KaBuM] {e}")

    return None


def buscar_magalu(nome):
    try:
        url = f"https://www.magazineluiza.com.br/busca/{quote_plus(nome)}/"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")

        item = soup.select_one("[data-testid='product-card'], li, article")
        area = item or soup

        preco_el = area.select_one('[data-testid="price-value"], .sc-kpDqfB, p[data-testid*="price"]')
        titulo_el = area.select_one("h2, h3, [data-testid='product-title']")
        link_el = area.select_one("a[href*='/p/'], a[href]")

        if preco_el:
            preco = limpar_preco(preco_el.get_text())
            if preco and preco > 10:
                return {
                    "loja": "Magalu",
                    "loja_id": "magalu",
                    "preco": preco,
                    "titulo": titulo_el.get_text(strip=True) if titulo_el else nome,
                    "url": normalizar_url("https://www.magazineluiza.com.br", link_el.get("href") if link_el else "", url),
                    "condicao": "Novo",
                }

    except Exception as e:
        log.warning(f"[Magalu] {e}")

    return None


def buscar_olx(nome):
    try:
        url = f"https://www.olx.com.br/brasil?q={quote_plus(nome)}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")

        item = soup.select_one("section[data-ds-component='DS-AdCard'], li, article")
        area = item or soup

        preco_el = area.select_one('[data-lurker-detail="price"], [aria-label*="Preço"], span')
        titulo_el = area.select_one("h2, h3")
        link_el = area.select_one("a[href*='olx.com.br'], a[href]")

        preco = limpar_preco(preco_el.get_text()) if preco_el else None

        if preco and preco > 10:
            return {
                "loja": "OLX",
                "loja_id": "olx",
                "preco": preco,
                "titulo": titulo_el.get_text(strip=True) if titulo_el else nome,
                "url": link_el.get("href") if link_el and link_el.get("href") else url,
                "condicao": "Usado",
            }

    except Exception as e:
        log.warning(f"[OLX] {e}")

    return None


def buscar_enjoei(nome):
    try:
        url = f"https://www.enjoei.com.br/busca?q={quote_plus(nome)}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")

        item = soup.select_one("a[href*='/p/'], .product-card, article")
        area = item or soup

        preco_el = area.select_one(".price, [data-testid*='price'], span")
        titulo_el = area.select_one(".product-title, h2, h3")
        link_el = area if getattr(area, "name", None) == "a" else area.select_one("a[href]")

        preco = limpar_preco(preco_el.get_text()) if preco_el else None

        if preco and preco > 10:
            return {
                "loja": "Enjoei",
                "loja_id": "enjoei",
                "preco": preco,
                "titulo": titulo_el.get_text(strip=True) if titulo_el else nome,
                "url": normalizar_url("https://www.enjoei.com.br", link_el.get("href") if link_el else "", url),
                "condicao": "Seminovo",
            }

    except Exception as e:
        log.warning(f"[Enjoei] {e}")

    return None


def buscar_em_todos(nome):
    resultados = []

    for fn in [
        buscar_mercadolivre,
        buscar_amazon,
        buscar_kabum,
        buscar_magalu,
        buscar_olx,
        buscar_enjoei,
    ]:
        res = fn(nome)
        if res:
            resultados.append(enriquecer_resultado_com_cupom(res))

    return sorted(resultados, key=lambda x: x.get("preco_final", x["preco"]))


# ── EMAIL ─────────────────────────────────────────────────────────────────────

def enviar_email(assunto, html, destinatario=None):
    destinatario_final = destinatario or EMAIL_DESTINATARIO_PADRAO

    if not EMAIL_REMETENTE or not EMAIL_SENHA:
        log.error("Credenciais de email não configuradas!")
        return False

    if not destinatario_final:
        log.error("Destinatário de email não configurado!")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"] = EMAIL_REMETENTE
    msg["To"] = destinatario_final
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(EMAIL_REMETENTE, EMAIL_SENHA)
            s.sendmail(EMAIL_REMETENTE, destinatario_final, msg.as_string())

        log.info(f"✅ Email enviado para {destinatario_final}: {assunto}")
        return True

    except Exception as e:
        log.error(f"Falha email: {e}")
        return False


def montar_email_alerta(produto, resultados, tipo_alerta="META_ATINGIDA", pct=None):
    nome = produto["nome"]
    meta = float(produto["preco_meta"])
    melhor = resultados[0]
    melhor_preco_final = melhor.get("preco_final", melhor["preco"])
    menor_hist = banco.menor_preco_historico(produto["id"])
    preco_sugerido = calcular_preco_sugerido(meta, melhor_preco_final, menor_hist)

    cor_topo = "#0d1b4b" if tipo_alerta == "META_ATINGIDA" else "#e65100"
    titulo_topo = "🔔 Alerta de Preço" if tipo_alerta == "META_ATINGIDA" else "⚡ Preço próximo da sua meta"

    lojas_rows = ""

    for r in resultados:
        mc = r.get("melhor_cupom")
        preco_final = r.get("preco_final", r["preco"])
        cor = "#2e7d32" if preco_final <= meta else "#e65100" if preco_final <= meta * 1.10 else "#333"

        cupom_html = (
            f"<code>{mc['codigo']}</code><br><small>estimado; confirme no checkout</small>"
            if mc
            else "—"
        )

        lojas_rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;">{r['loja']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;font-weight:700;color:{cor};">R$ {r['preco']:.2f}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;font-weight:700;color:{cor};">R$ {preco_final:.2f}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;">{r.get('condicao','')}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;">{cupom_html}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;"><a href="{r['url']}">Ver produto →</a></td>
        </tr>"""

    pct_bloco = f"<p>Distância da meta: <b>{pct:.1f}% acima</b></p>" if pct is not None else ""
    hist_bloco = f"<p>Menor preço histórico registrado: <b>R$ {menor_hist:.2f}</b></p>" if menor_hist else ""

    return f"""
    <html>
      <body style="font-family:Arial,sans-serif;max-width:720px;margin:0 auto;color:#212121;">
        <div style="background:{cor_topo};color:#fff;padding:22px 26px;border-radius:10px 10px 0 0;">
          <h1 style="margin:0;font-size:1.35em;">{titulo_topo} — {nome}</h1>
          <p style="margin:6px 0 0;opacity:.85;">{datetime.now().strftime("%d/%m/%Y %H:%M")}</p>
        </div>

        <div style="border:1px solid #e0e0e0;border-top:none;padding:22px 26px;border-radius:0 0 10px 10px;">
          <p>Melhor preço encontrado: <b style="font-size:1.5em;color:#2e7d32;">R$ {melhor_preco_final:.2f}</b> na <b>{melhor['loja']}</b></p>
          <p>Sua meta: <b>R$ {meta:.2f}</b></p>
          <p>Preço sugerido para compra: <b>R$ {preco_sugerido:.2f}</b></p>
          <p>Condição: <b>{melhor.get("condicao", "Não informado")}</b></p>
          {pct_bloco}
          {hist_bloco}

          <h3>Comparativo completo</h3>

          <table style="width:100%;border-collapse:collapse;font-size:13px;">
            <tr style="background:#f5f5f5;">
              <th style="padding:8px 12px;text-align:left;">Loja</th>
              <th style="padding:8px 12px;text-align:left;">Preço</th>
              <th style="padding:8px 12px;text-align:left;">Preço c/ cupom estimado</th>
              <th style="padding:8px 12px;text-align:left;">Condição</th>
              <th style="padding:8px 12px;text-align:left;">Cupom</th>
              <th style="padding:8px 12px;text-align:left;">Link</th>
            </tr>
            {lojas_rows}
          </table>

          <a href="{melhor['url']}" style="display:inline-block;margin-top:18px;background:{cor_topo};
             color:#fff;padding:12px 24px;border-radius:7px;text-decoration:none;font-weight:bold;">
            Ver melhor oferta →
          </a>

          <p style="font-size:12px;color:#777;margin-top:18px;">
            Os preços e cupons podem mudar a qualquer momento. Cupons são estimativas e precisam ser confirmados no checkout da loja.
          </p>
        </div>
      </body>
    </html>
    """


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

        resultados = filtrar_por_condicao(p, resultados)

        if not resultados:
            log.warning(f"  ⚠️ Nenhum resultado compatível com as condições aceitas para '{p['nome']}'")
            continue

        resultados = sorted(resultados, key=lambda x: x.get("preco_final", x["preco"]))

        for r in resultados:
            banco.inserir_historico(
                p["id"],
                r["loja"],
                r["loja_id"],
                r.get("preco_final", r["preco"]),
                r.get("condicao", ""),
                r.get("url", ""),
            )

        melhor = resultados[0]
        meta = float(p["preco_meta"])
        melhor_preco_final = float(melhor.get("preco_final", melhor["preco"]))

        alerta_proximo_pct = float(p.get("alerta_proximo_pct", 10))
        limite_proximo = meta * (1 + alerta_proximo_pct / 100)
        destinatario = p.get("email") or EMAIL_DESTINATARIO_PADRAO

        log.info(
            f"     Melhor: {melhor['loja']} R$ {melhor_preco_final:.2f} | "
            f"Meta: R$ {meta:.2f} | Próximo até: R$ {limite_proximo:.2f}"
        )

        if melhor_preco_final <= meta:
            chave = f"{p['id']}_atingiu_{melhor['loja_id']}_{round(melhor_preco_final, 0)}"

            if not banco.alerta_ja_enviado(chave):
                enviado = enviar_email(
                    f"✅ {p['nome']} — R$ {melhor_preco_final:.2f} na {melhor['loja']}!",
                    montar_email_alerta(p, resultados, tipo_alerta="META_ATINGIDA"),
                    destinatario=destinatario,
                )

                if enviado:
                    banco.registrar_alerta(p["id"], chave)

        elif melhor_preco_final <= limite_proximo:
            pct = ((melhor_preco_final - meta) / meta) * 100
            chave = f"{p['id']}_proximo_{melhor['loja_id']}_{round(pct, 0)}"

            if not banco.alerta_ja_enviado(chave):
                enviado = enviar_email(
                    f"⚡ {p['nome']} está próximo da meta: R$ {melhor_preco_final:.2f}",
                    montar_email_alerta(p, resultados, tipo_alerta="PRECO_PROXIMO", pct=pct),
                    destinatario=destinatario,
                )

                if enviado:
                    banco.registrar_alerta(p["id"], chave)

        else:
            log.info("     Nenhum alerta enviado. Preço ainda distante da meta.")

    log.info("✔️ Verificação concluída.\n")
