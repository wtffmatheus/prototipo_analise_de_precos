import os
import re
import json
import smtplib
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from urllib.parse import quote_plus, urljoin

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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

LOJAS_NOMES = {
    "mercadolivre": "Mercado Livre",
    "amazon": "Amazon",
    "kabum": "KaBuM!",
    "magalu": "Magalu",
    "olx": "OLX",
    "enjoei": "Enjoei",
}

# Base interna de possíveis cupons.
# Importante: NÃO são aplicados automaticamente ao preço final.
# Eles aparecem como "possíveis" e precisam ser testados no checkout.
CUPONS_BASE = {
    "mercadolivre": [
        {
            "codigo": "MELI5",
            "desc_pct": 5,
            "desc_fixo": 0,
            "tipo": "percentual",
            "condicao": "Possível cupom para compras selecionadas.",
            "origem": "base interna",
            "confianca": "baixa",
            "verificado": False,
        },
        {
            "codigo": "APPML10",
            "desc_pct": 10,
            "desc_fixo": 0,
            "tipo": "percentual",
            "condicao": "Possível desconto em compras pelo app.",
            "origem": "base interna",
            "confianca": "baixa",
            "verificado": False,
        },
    ],
    "amazon": [
        {
            "codigo": "APP10",
            "desc_pct": 10,
            "desc_fixo": 0,
            "tipo": "percentual",
            "condicao": "Possível desconto em compras pelo app.",
            "origem": "base interna",
            "confianca": "baixa",
            "verificado": False,
        },
        {
            "codigo": "PRIME30",
            "desc_pct": 0,
            "desc_fixo": 30,
            "tipo": "fixo",
            "condicao": "Possível desconto para clientes Prime ou campanha selecionada.",
            "origem": "base interna",
            "confianca": "baixa",
            "verificado": False,
        },
    ],
    "kabum": [
        {
            "codigo": "KABUM10",
            "desc_pct": 10,
            "desc_fixo": 0,
            "tipo": "percentual",
            "condicao": "Possível cupom para Pix, boleto ou campanha específica.",
            "origem": "base interna",
            "confianca": "baixa",
            "verificado": False,
        },
        {
            "codigo": "KABUM5",
            "desc_pct": 5,
            "desc_fixo": 0,
            "tipo": "percentual",
            "condicao": "Possível cupom para produtos selecionados.",
            "origem": "base interna",
            "confianca": "baixa",
            "verificado": False,
        },
    ],
    "magalu": [
        {
            "codigo": "APP15",
            "desc_pct": 15,
            "desc_fixo": 0,
            "tipo": "percentual",
            "condicao": "Possível cupom para app Magalu.",
            "origem": "base interna",
            "confianca": "baixa",
            "verificado": False,
        },
        {
            "codigo": "PIX5",
            "desc_pct": 5,
            "desc_fixo": 0,
            "tipo": "percentual",
            "condicao": "Possível desconto via Pix.",
            "origem": "base interna",
            "confianca": "baixa",
            "verificado": False,
        },
    ],
    "olx": [
        {
            "codigo": "OLXAPP",
            "desc_pct": 5,
            "desc_fixo": 0,
            "tipo": "percentual",
            "condicao": "Possível cupom no app OLX, quando disponível.",
            "origem": "base interna",
            "confianca": "baixa",
            "verificado": False,
        },
    ],
    "enjoei": [
        {
            "codigo": "PRIMEIROENJOI",
            "desc_pct": 10,
            "desc_fixo": 0,
            "tipo": "percentual",
            "condicao": "Possível cupom de primeira compra.",
            "origem": "base interna",
            "confianca": "baixa",
            "verificado": False,
        },
    ],
}


def get_html(url: str, timeout: int = 20) -> Optional[str]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)

        if resp.status_code >= 400:
            log.warning(f"HTTP {resp.status_code} em {url}")
            return None

        return resp.text

    except Exception as e:
        log.warning(f"Falha ao acessar {url}: {e}")
        return None


def limpar_preco(texto: str) -> Optional[float]:
    if not texto:
        return None

    texto = str(texto)
    texto = texto.replace("\xa0", " ")
    texto = texto.replace("R$", " ")
    texto = texto.strip()

    match = re.search(r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d{1,3}(?:\.\d{3})+|\d+(?:,\d{2})?)", texto)

    if not match:
        return None

    valor = match.group(1)

    if "," in valor:
        valor = valor.replace(".", "").replace(",", ".")
    else:
        partes = valor.split(".")

        if len(partes) > 1 and len(partes[-1]) == 3:
            valor = "".join(partes)

    try:
        preco = float(valor)
        return preco if preco > 0 else None
    except ValueError:
        return None


def normalizar_url(base: str, href: str, fallback: str) -> str:
    if not href:
        return fallback

    href = href.strip()

    if href.startswith("http"):
        return href

    return urljoin(base, href)


def detectar_tipo_link(url: str) -> str:
    if not url:
        return "sem_link"

    u = url.lower()

    padroes_busca = [
        "/busca",
        "search",
        "?q=",
        "/s?k=",
        "lista.mercadolivre",
        "olx.com.br/brasil",
        "enjoei.com.br/busca",
    ]

    if any(p in u for p in padroes_busca):
        return "busca"

    return "produto"


def titulo_parece_relevante(titulo: str, nome: str) -> bool:
    if not titulo or not nome:
        return True

    titulo_l = titulo.lower()
    termos = [t for t in re.split(r"\s+", nome.lower()) if len(t) >= 3]

    if not termos:
        return True

    encontrados = sum(1 for t in termos if t in titulo_l)

    return encontrados >= max(1, min(2, len(termos)))


def calc_preco_final(preco, cupom):
    if not cupom:
        return round(float(preco), 2)

    if cupom.get("tipo") == "percentual":
        return round(float(preco) * (1 - float(cupom.get("desc_pct", 0)) / 100), 2)

    if cupom.get("tipo") == "fixo":
        return round(max(0, float(preco) - float(cupom.get("desc_fixo", 0))), 2)

    return round(float(preco), 2)


def buscar_cupons_na_pagina(soup: BeautifulSoup, loja_id: str, preco: float):
    """
    Tenta achar possíveis códigos de cupom no texto da página.
    Não valida checkout. Apenas adiciona candidatos com confiança média/baixa.
    """

    texto = soup.get_text(" ", strip=True)
    achados = []

    padroes = [
        r"cupom\s+([A-Z0-9]{4,20})",
        r"código\s+([A-Z0-9]{4,20})",
        r"codigo\s+([A-Z0-9]{4,20})",
        r"use\s+([A-Z0-9]{4,20})",
        r"aplique\s+([A-Z0-9]{4,20})",
    ]

    ignorar = {
        "PARA",
        "COMO",
        "AQUI",
        "SITE",
        "APP",
        "PIX",
        "BOLETO",
        "FRETE",
        "GRATIS",
        "DESCONTO",
    }

    for padrao in padroes:
        for m in re.finditer(padrao, texto, flags=re.IGNORECASE):
            codigo = m.group(1).upper().strip()

            if codigo in ignorar:
                continue

            if len(codigo) < 4:
                continue

            achados.append({
                "codigo": codigo,
                "desc_pct": 0,
                "desc_fixo": 0,
                "tipo": "desconhecido",
                "condicao": "Código encontrado no texto da página. Teste no checkout.",
                "origem": "página da loja",
                "confianca": "média",
                "verificado": False,
                "preco_final_estimado": round(float(preco), 2),
                "economia": 0,
                "aviso": "Cupom encontrado na página, mas não validado no checkout.",
            })

    # remove duplicados
    unicos = {}
    for c in achados:
        unicos[c["codigo"]] = c

    return list(unicos.values())


def analisar_possiveis_cupons(loja_id: str, preco: float, soup: Optional[BeautifulSoup] = None):
    """
    Retorna cupons possíveis, sem aplicar automaticamente no preço final.
    """

    possiveis = []

    for c in CUPONS_BASE.get(loja_id, []):
        estimado = calc_preco_final(preco, c)

        possiveis.append({
            **c,
            "preco_final_estimado": estimado,
            "economia": round(float(preco) - estimado, 2),
            "aviso": "Cupom possível, não confirmado. Teste no checkout antes de considerar o desconto.",
        })

    if soup:
        possiveis.extend(buscar_cupons_na_pagina(soup, loja_id, preco))

    # remove duplicados por código
    unicos = {}
    for c in possiveis:
        codigo = c.get("codigo", "").upper()
        if codigo and codigo not in unicos:
            unicos[codigo] = c

    return sorted(
        list(unicos.values()),
        key=lambda x: x.get("preco_final_estimado", preco)
    )


def enriquecer_resultado(resultado, soup: Optional[BeautifulSoup] = None):
    """
    IMPORTANTE:
    preco_final agora é o preço real encontrado.
    Cupom não altera preco_final, pois não está validado.
    """

    preco = float(resultado["preco"])
    loja_id = resultado["loja_id"]
    possiveis_cupons = analisar_possiveis_cupons(loja_id, preco, soup)

    resultado["preco_final"] = round(preco, 2)
    resultado["possiveis_cupons"] = possiveis_cupons
    resultado["melhor_cupom"] = possiveis_cupons[0] if possiveis_cupons else None
    resultado["cupom_confirmado"] = False
    resultado["observacao_cupom"] = (
        "Cupons listados são possíveis, não confirmados. Teste no checkout."
        if possiveis_cupons
        else ""
    )
    resultado["link_tipo"] = detectar_tipo_link(resultado.get("url", ""))

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


def extrair_json_ld_produtos(soup: BeautifulSoup, base_url: str, fallback_url: str):
    produtos = []

    for tag in soup.select('script[type="application/ld+json"]'):
        raw = tag.string or tag.get_text()

        if not raw:
            continue

        try:
            data = json.loads(raw)
        except Exception:
            continue

        pilha = data if isinstance(data, list) else [data]

        while pilha:
            item = pilha.pop()

            if isinstance(item, list):
                pilha.extend(item)
                continue

            if not isinstance(item, dict):
                continue

            tipo = item.get("@type")

            if isinstance(tipo, list):
                is_product = "Product" in tipo
            else:
                is_product = tipo == "Product"

            if is_product:
                nome = item.get("name") or item.get("description") or ""
                url = item.get("url") or fallback_url

                offers = item.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}

                preco = (
                    offers.get("price")
                    or offers.get("lowPrice")
                    or offers.get("highPrice")
                    or item.get("price")
                )

                preco_limpo = limpar_preco(str(preco)) if preco else None

                if preco_limpo:
                    produtos.append({
                        "titulo": nome,
                        "preco": preco_limpo,
                        "url": normalizar_url(base_url, url, fallback_url),
                    })

            for v in item.values():
                if isinstance(v, (dict, list)):
                    pilha.append(v)

    return produtos


def montar_resultado(loja_id, preco, titulo, url, condicao, soup=None):
    return enriquecer_resultado({
        "loja": LOJAS_NOMES.get(loja_id, loja_id),
        "loja_id": loja_id,
        "preco": round(float(preco), 2),
        "titulo": titulo,
        "url": url,
        "condicao": condicao,
    }, soup)


# ── SCRAPERS ──────────────────────────────────────────────────────────────────

def buscar_mercadolivre(nome):
    try:
        termo = quote_plus(nome).replace("+", "-")
        url = f"https://lista.mercadolivre.com.br/{termo}"
        html = get_html(url)

        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")

        cards = soup.select("li.ui-search-layout__item, .ui-search-result__wrapper")

        for item in cards[:8]:
            preco_el = item.select_one(".andes-money-amount__fraction")
            cents_el = item.select_one(".andes-money-amount__cents")
            titulo_el = item.select_one(".ui-search-item__title, h2, a.poly-component__title")
            link_el = item.select_one("a[href*='/MLB-'], a.ui-search-link, a[href*='produto.mercadolivre']")

            if not preco_el:
                continue

            val = preco_el.get_text(strip=True).replace(".", "")

            if cents_el:
                val += "." + cents_el.get_text(strip=True)

            preco = limpar_preco(val)

            if not preco:
                continue

            titulo = titulo_el.get_text(strip=True) if titulo_el else nome

            if not titulo_parece_relevante(titulo, nome):
                continue

            link = link_el.get("href") if link_el else url

            return montar_resultado(
                loja_id="mercadolivre",
                preco=preco,
                titulo=titulo,
                url=link,
                condicao="Novo",
                soup=soup,
            )

    except Exception as e:
        log.warning(f"[Mercado Livre] {e}")

    return None


def buscar_amazon(nome):
    try:
        url = f"https://www.amazon.com.br/s?k={quote_plus(nome)}"
        html = get_html(url)

        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")

        cards = soup.select('[data-component-type="s-search-result"]')

        for res in cards[:8]:
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

            if not preco or preco <= 10:
                continue

            titulo = titulo_el.get_text(strip=True) if titulo_el else nome

            if not titulo_parece_relevante(titulo, nome):
                continue

            link = normalizar_url(
                "https://www.amazon.com.br",
                link_el.get("href") if link_el else "",
                url
            )

            return montar_resultado(
                loja_id="amazon",
                preco=preco,
                titulo=titulo,
                url=link,
                condicao="Novo",
                soup=soup,
            )

    except Exception as e:
        log.warning(f"[Amazon] {e}")

    return None


def buscar_kabum(nome):
    try:
        url = f"https://www.kabum.com.br/busca/{quote_plus(nome)}"
        html = get_html(url)

        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")

        json_produtos = extrair_json_ld_produtos(
            soup,
            "https://www.kabum.com.br",
            url
        )

        for p in json_produtos:
            if titulo_parece_relevante(p["titulo"], nome):
                return montar_resultado(
                    loja_id="kabum",
                    preco=p["preco"],
                    titulo=p["titulo"],
                    url=p["url"],
                    condicao="Novo",
                    soup=soup,
                )

        cards = soup.select(
            "article, .productCard, [data-testid='product-card'], "
            "div[class*='product'], div[class*='Product']"
        )

        for card in cards[:12]:
            texto_card = card.get_text(" ", strip=True)

            if "R$" not in texto_card:
                continue

            preco_el = card.select_one(
                ".finalPrice, [data-testid='price'], .priceCard, "
                "span[class*='price'], div[class*='price']"
            )
            titulo_el = card.select_one(
                ".nameCard, [data-testid='product-name'], h2, h3, "
                "span[class*='name'], div[class*='name']"
            )
            link_el = card.select_one("a[href*='/produto/'], a.productLink[href], a[href]")

            preco = limpar_preco(preco_el.get_text(" ", strip=True) if preco_el else texto_card)

            if not preco or preco <= 10:
                continue

            titulo = titulo_el.get_text(" ", strip=True) if titulo_el else nome

            if not titulo_parece_relevante(titulo, nome):
                continue

            link = normalizar_url(
                "https://www.kabum.com.br",
                link_el.get("href") if link_el else "",
                url
            )

            return montar_resultado(
                loja_id="kabum",
                preco=preco,
                titulo=titulo,
                url=link,
                condicao="Novo",
                soup=soup,
            )

    except Exception as e:
        log.warning(f"[KaBuM] {e}")

    return None


def buscar_magalu(nome):
    try:
        url = f"https://www.magazineluiza.com.br/busca/{quote_plus(nome)}/"
        html = get_html(url)

        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")

        json_produtos = extrair_json_ld_produtos(
            soup,
            "https://www.magazineluiza.com.br",
            url
        )

        for p in json_produtos:
            if titulo_parece_relevante(p["titulo"], nome):
                return montar_resultado(
                    loja_id="magalu",
                    preco=p["preco"],
                    titulo=p["titulo"],
                    url=p["url"],
                    condicao="Novo",
                    soup=soup,
                )

        cards = soup.select(
            "[data-testid='product-card'], li, article, "
            "div[class*='product'], div[class*='Product']"
        )

        for card in cards[:12]:
            texto_card = card.get_text(" ", strip=True)

            if "R$" not in texto_card:
                continue

            preco_el = card.select_one(
                '[data-testid="price-value"], p[data-testid*="price"], '
                "span[class*='price'], div[class*='price']"
            )
            titulo_el = card.select_one(
                "h2, h3, [data-testid='product-title'], "
                "span[class*='title'], div[class*='title']"
            )
            link_el = card.select_one("a[href*='/p/'], a[href]")

            preco = limpar_preco(preco_el.get_text(" ", strip=True) if preco_el else texto_card)

            if not preco or preco <= 10:
                continue

            titulo = titulo_el.get_text(" ", strip=True) if titulo_el else nome

            if not titulo_parece_relevante(titulo, nome):
                continue

            link = normalizar_url(
                "https://www.magazineluiza.com.br",
                link_el.get("href") if link_el else "",
                url
            )

            return montar_resultado(
                loja_id="magalu",
                preco=preco,
                titulo=titulo,
                url=link,
                condicao="Novo",
                soup=soup,
            )

    except Exception as e:
        log.warning(f"[Magalu] {e}")

    return None


def buscar_olx(nome):
    try:
        url = f"https://www.olx.com.br/brasil?q={quote_plus(nome)}"
        html = get_html(url)

        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")

        cards = soup.select(
            "section[data-ds-component='DS-AdCard'], "
            "[data-testid='ad-card'], li, article"
        )

        for card in cards[:12]:
            texto_card = card.get_text(" ", strip=True)

            if "R$" not in texto_card:
                continue

            preco_el = card.select_one(
                '[data-lurker-detail="price"], [aria-label*="Preço"], '
                "span[class*='price'], div[class*='price']"
            )
            titulo_el = card.select_one("h2, h3, [aria-label*='Título']")
            link_el = card.select_one("a[href*='olx.com.br'], a[href]")

            preco = limpar_preco(preco_el.get_text(" ", strip=True) if preco_el else texto_card)

            if not preco or preco <= 10:
                continue

            titulo = titulo_el.get_text(" ", strip=True) if titulo_el else nome

            if not titulo_parece_relevante(titulo, nome):
                continue

            link = link_el.get("href") if link_el and link_el.get("href") else url

            return montar_resultado(
                loja_id="olx",
                preco=preco,
                titulo=titulo,
                url=link,
                condicao="Usado",
                soup=soup,
            )

    except Exception as e:
        log.warning(f"[OLX] {e}")

    return None


def buscar_enjoei(nome):
    try:
        url = f"https://www.enjoei.com.br/busca?q={quote_plus(nome)}"
        html = get_html(url)

        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")

        cards = soup.select("a[href*='/p/'], .product-card, article, li")

        for card in cards[:12]:
            texto_card = card.get_text(" ", strip=True)

            if "R$" not in texto_card:
                continue

            preco_el = card.select_one(".price, [data-testid*='price'], span[class*='price']")
            titulo_el = card.select_one(".product-title, h2, h3, [class*='title']")
            link_el = card if getattr(card, "name", None) == "a" else card.select_one("a[href]")

            preco = limpar_preco(preco_el.get_text(" ", strip=True) if preco_el else texto_card)

            if not preco or preco <= 10:
                continue

            titulo = titulo_el.get_text(" ", strip=True) if titulo_el else nome

            if not titulo_parece_relevante(titulo, nome):
                continue

            link = normalizar_url(
                "https://www.enjoei.com.br",
                link_el.get("href") if link_el else "",
                url
            )

            return montar_resultado(
                loja_id="enjoei",
                preco=preco,
                titulo=titulo,
                url=link,
                condicao="Seminovo",
                soup=soup,
            )

    except Exception as e:
        log.warning(f"[Enjoei] {e}")

    return None


def buscar_em_todos(nome):
    resultados = []

    funcoes = [
        buscar_mercadolivre,
        buscar_amazon,
        buscar_kabum,
        buscar_magalu,
        buscar_olx,
        buscar_enjoei,
    ]

    for fn in funcoes:
        try:
            res = fn(nome)

            if res:
                resultados.append(res)

        except Exception as e:
            log.warning(f"Erro em {fn.__name__}: {e}")

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
        preco_final = r.get("preco_final", r["preco"])
        cor = "#2e7d32" if preco_final <= meta else "#e65100" if preco_final <= meta * 1.10 else "#333"
        cupons = r.get("possiveis_cupons", [])
        cupom_html = "—"

        if cupons:
            primeiros = cupons[:2]
            cupom_html = "<br>".join(
                f"<code>{c['codigo']}</code> <small>possível, não verificado</small>"
                for c in primeiros
            )

        link_label = "Produto" if r.get("link_tipo") == "produto" else "Busca"

        lojas_rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;">{r['loja']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;font-weight:700;color:{cor};">R$ {r['preco']:.2f}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;">{r.get('condicao','')}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;">{cupom_html}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;"><a href="{r['url']}">{link_label} →</a></td>
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
              <th style="padding:8px 12px;text-align:left;">Preço real</th>
              <th style="padding:8px 12px;text-align:left;">Condição</th>
              <th style="padding:8px 12px;text-align:left;">Possíveis cupons</th>
              <th style="padding:8px 12px;text-align:left;">Link</th>
            </tr>
            {lojas_rows}
          </table>

          <a href="{melhor['url']}" style="display:inline-block;margin-top:18px;background:{cor_topo};
             color:#fff;padding:12px 24px;border-radius:7px;text-decoration:none;font-weight:bold;">
            Ver melhor oferta →
          </a>

          <p style="font-size:12px;color:#777;margin-top:18px;">
            Os preços podem mudar a qualquer momento. Cupons listados são possíveis e precisam ser testados no checkout.
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