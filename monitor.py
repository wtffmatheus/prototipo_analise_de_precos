"""
buscador.py — Motor de busca de preços v2
==========================================
Estratégia por loja:
  - Mercado Livre : API REST oficial (sem chave) + fallback scraping HTML
  - Amazon        : scraping HTML + JSON-LD + múltiplos seletores
  - KaBuM         : scraping HTML + JSON-LD + múltiplos seletores
  - Magalu        : scraping HTML + JSON-LD + múltiplos seletores
  - OLX           : scraping HTML + extração __NEXT_DATA__ (SSR)
  - Enjoei        : scraping HTML + JSON-LD

Filtro de relevância v3:
  - Bloqueia kits/combos/PCs Gamer mesmo que contenham o produto buscado
  - Detecta termos de modelo (com dígitos) para maior precisão
  - Limita razão de tamanho título/nome para evitar combos disfarçados

Condição: sempre lida do dado real, nunca hardcoded.
Link: detectar_tipo_link() classifica produto vs busca para o front.
Cupons: listados como possíveis, NUNCA aplicados no preco_final.
"""

from __future__ import annotations

import json
import logging
import os
import re
import smtplib
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

import banco

load_dotenv()
log = logging.getLogger(__name__)

# ── Configuração de e-mail ────────────────────────────────────────────────────
EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE", "")
EMAIL_SENHA = os.getenv("EMAIL_SENHA", "")
EMAIL_DESTINATARIO_PADRAO = os.getenv("EMAIL_DESTINATARIO", EMAIL_REMETENTE)

# ── Headers genéricos para scraping ──────────────────────────────────────────
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

CONDICAO_MAP = {
    "new": "Novo",
    "used": "Usado",
    "refurbished": "Recondicionado",
    "novo": "Novo",
    "usado": "Usado",
    "seminovo": "Seminovo",
    "recondicionado": "Recondicionado",
}

# Palavras que indicam que o produto é um KIT/COMBO — bloquear mesmo se contém o item buscado
KIT_KEYWORDS = {
    "pc gamer", "kit ", "combo ", "desktop gamer", "computador gamer",
    "setup gamer", "pc completo", "sistema completo", "monte seu pc",
}

# ── Cupons possíveis (base interna) ──────────────────────────────────────────
CUPONS_BASE: dict[str, list[dict]] = {
    "mercadolivre": [
        {"codigo": "MELI5",   "tipo": "percentual", "desc_pct": 5,  "desc_fixo": 0,
         "condicao": "Possível cupom para compras selecionadas."},
        {"codigo": "APPML10", "tipo": "percentual", "desc_pct": 10, "desc_fixo": 0,
         "condicao": "Possível desconto via app Mercado Livre."},
    ],
    "amazon": [
        {"codigo": "APP10",   "tipo": "percentual", "desc_pct": 10, "desc_fixo": 0,
         "condicao": "Possível desconto via app Amazon."},
        {"codigo": "PRIME30", "tipo": "fixo",       "desc_pct": 0,  "desc_fixo": 30,
         "condicao": "Possível desconto para clientes Prime."},
    ],
    "kabum": [
        {"codigo": "KABUM10", "tipo": "percentual", "desc_pct": 10, "desc_fixo": 0,
         "condicao": "Possível cupom Pix/boleto ou campanha."},
        {"codigo": "KABUM5",  "tipo": "percentual", "desc_pct": 5,  "desc_fixo": 0,
         "condicao": "Possível cupom para produtos selecionados."},
    ],
    "magalu": [
        {"codigo": "APP15",   "tipo": "percentual", "desc_pct": 15, "desc_fixo": 0,
         "condicao": "Possível cupom via app Magalu."},
        {"codigo": "PIX5",    "tipo": "percentual", "desc_pct": 5,  "desc_fixo": 0,
         "condicao": "Possível desconto via Pix."},
    ],
    "olx": [
        {"codigo": "OLXAPP",  "tipo": "percentual", "desc_pct": 5,  "desc_fixo": 0,
         "condicao": "Possível cupom no app OLX."},
    ],
    "enjoei": [
        {"codigo": "PRIMEIROENJOI", "tipo": "percentual", "desc_pct": 10, "desc_fixo": 0,
         "condicao": "Possível cupom de primeira compra."},
    ],
}


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITÁRIOS HTTP
# ═══════════════════════════════════════════════════════════════════════════════

def get_html(url: str, timeout: int = 20, extra_headers: dict | None = None) -> Optional[str]:
    h = {**HEADERS, **(extra_headers or {})}
    try:
        resp = requests.get(url, headers=h, timeout=timeout, allow_redirects=True)
        if resp.status_code >= 400:
            log.warning(f"HTTP {resp.status_code} em {url}")
            return None
        return resp.text
    except Exception as e:
        log.warning(f"Falha ao acessar {url}: {e}")
        return None


def get_json(url: str, timeout: int = 15, params: dict | None = None) -> Optional[dict | list]:
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
        if resp.status_code >= 400:
            log.warning(f"HTTP {resp.status_code} (JSON) em {url}")
            return None
        return resp.json()
    except Exception as e:
        log.warning(f"Falha JSON em {url}: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITÁRIOS DE DADOS
# ═══════════════════════════════════════════════════════════════════════════════

def limpar_preco(texto: str) -> Optional[float]:
    """Extrai float de string com preço em formato brasileiro (R$ 1.234,56)."""
    if not texto:
        return None
    texto = str(texto).replace("\xa0", " ").replace("R$", " ").strip()
    match = re.search(
        r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d{1,3}(?:\.\d{3})+|\d+(?:,\d{2})?)",
        texto,
    )
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


def normalizar_condicao(raw: str) -> str:
    if not raw:
        return "Não informado"
    # itemCondition do schema.org vem como URL
    if "NewCondition" in raw or raw.strip().lower() in ("new", "novo"):
        return "Novo"
    if "UsedCondition" in raw or raw.strip().lower() in ("used", "usado"):
        return "Usado"
    if "RefurbishedCondition" in raw or "recondicionado" in raw.lower():
        return "Recondicionado"
    return CONDICAO_MAP.get(raw.strip().lower(), raw.strip().capitalize())


def normalizar_url(base: str, href: str, fallback: str) -> str:
    if not href:
        return fallback
    href = href.strip()
    if href.startswith("http"):
        return href
    return urljoin(base, href)


def detectar_tipo_link(url: str) -> str:
    """Classifica se o link leva a um produto específico ou a uma página de busca."""
    if not url:
        return "sem_link"
    u = url.lower()
    # Padrões de página de produto
    if any(p in u for p in [
        "/produto/", "/p/", "/dp/", "/mlb-", "produto.mercadolivre",
        "/item/", "/anuncio/", "/sku/",
    ]):
        return "produto"
    # Padrões de busca
    if any(p in u for p in [
        "/busca", "/s?k=", "?q=", "?query=", "lista.mercadolivre",
        "olx.com.br/brasil", "/busca?", "enjoei.com.br/busca",
    ]):
        return "busca"
    return "produto"  # se não reconheceu como busca, assume produto


def titulo_parece_relevante(titulo: str, nome: str) -> bool:
    """
    Filtro de relevância v3:
    1. Bloqueia kits/combos/PCs Gamer mesmo que contenham o produto.
    2. Verifica cobertura dos termos do nome no título.
    3. Usa termos de modelo (com dígitos) como âncora forte.
    4. Limita a razão de tamanho título/nome para barrar combos disfarçados.
    """
    if not titulo or not nome:
        return True

    titulo_l = titulo.lower()
    nome_l = nome.lower()

    # Regra 0: bloqueia kits e combos explicitamente
    if any(k in titulo_l for k in KIT_KEYWORDS):
        return False

    termos = [t for t in re.split(r"\s+", nome_l) if len(t) >= 3]
    if not termos:
        return True

    encontrados = sum(1 for t in termos if t in titulo_l)
    cobertura = encontrados / len(termos)

    # Termos com dígitos são os mais identificadores (ex: "5700x", "14", "s24")
    termos_modelo = [t for t in termos if re.search(r"\d", t)]
    cobertura_modelo = (
        sum(1 for t in termos_modelo if t in titulo_l) / len(termos_modelo)
        if termos_modelo else 1.0
    )

    palavras_titulo = len(set(re.split(r"[\s|,\(\)\[\]]+", titulo_l)))
    palavras_nome = len(set(re.split(r"\s+", nome_l)))
    razao = palavras_titulo / max(palavras_nome, 1)

    # Regra 1: cobertura alta e título não muito maior que o nome
    if cobertura >= 0.8 and razao <= 5:
        return True
    # Regra 2: cobertura média e tamanho razoável
    if cobertura >= 0.6 and razao <= 3:
        return True
    # Regra 3: todos os termos de modelo presentes (produto certo, marca diferente)
    if cobertura_modelo >= 1.0 and razao <= 5:
        return True

    return False


def calcular_preco_sugerido(meta: float, melhor_preco: float, menor_historico: Optional[float]) -> float:
    if melhor_preco <= meta:
        return round(melhor_preco, 2)
    if menor_historico and menor_historico < meta:
        return round(menor_historico, 2)
    return round(meta, 2)


# ═══════════════════════════════════════════════════════════════════════════════
# JSON-LD
# ═══════════════════════════════════════════════════════════════════════════════

def extrair_json_ld_produtos(soup: BeautifulSoup, base_url: str, fallback_url: str) -> list[dict]:
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
            is_product = ("Product" in tipo) if isinstance(tipo, list) else (tipo == "Product")
            if is_product:
                nome_prod = item.get("name") or item.get("description") or ""
                url_prod = item.get("url") or fallback_url
                offers = item.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                preco_raw = (
                    offers.get("price")
                    or offers.get("lowPrice")
                    or offers.get("highPrice")
                    or item.get("price")
                )
                preco = limpar_preco(str(preco_raw)) if preco_raw else None
                condicao = normalizar_condicao(offers.get("itemCondition", ""))
                if preco:
                    produtos.append({
                        "titulo": nome_prod,
                        "preco": preco,
                        "url": normalizar_url(base_url, url_prod, fallback_url),
                        "condicao": condicao or "Não informado",
                    })
            for v in item.values():
                if isinstance(v, (dict, list)):
                    pilha.append(v)
    return produtos


# ═══════════════════════════════════════════════════════════════════════════════
# CUPONS
# ═══════════════════════════════════════════════════════════════════════════════

def buscar_cupons_na_pagina(soup: BeautifulSoup, loja_id: str) -> list[dict]:
    texto = soup.get_text(" ", strip=True)
    ignorar = {
        "PARA", "COMO", "AQUI", "SITE", "APP", "PIX", "BOLETO",
        "FRETE", "GRATIS", "DESCONTO", "CLIQUE", "COMPRE",
    }
    padroes = [
        r"cupom\s+([A-Z0-9]{4,20})",
        r"c[oó]digo\s+([A-Z0-9]{4,20})",
        r"\buse\s+([A-Z0-9]{4,20})",
        r"aplique\s+([A-Z0-9]{4,20})",
    ]
    unicos: dict[str, dict] = {}
    for padrao in padroes:
        for m in re.finditer(padrao, texto, flags=re.IGNORECASE):
            codigo = m.group(1).upper().strip()
            if codigo in ignorar or len(codigo) < 4 or codigo in unicos:
                continue
            unicos[codigo] = {
                "codigo": codigo,
                "tipo": "desconhecido",
                "desc_pct": 0, "desc_fixo": 0,
                "condicao": "Código encontrado na página. Teste no checkout.",
                "origem": "página da loja",
                "confianca": "média",
                "verificado": False,
            }
    return list(unicos.values())


def montar_possiveis_cupons(loja_id: str, soup: Optional[BeautifulSoup] = None) -> list[dict]:
    possiveis = [
        {**c, "confianca": "baixa", "verificado": False, "origem": "base interna"}
        for c in CUPONS_BASE.get(loja_id, [])
    ]
    if soup:
        possiveis += buscar_cupons_na_pagina(soup, loja_id)
    unicos: dict[str, dict] = {}
    for c in possiveis:
        codigo = c.get("codigo", "").upper()
        if codigo and codigo not in unicos:
            unicos[codigo] = c
    return list(unicos.values())


# ═══════════════════════════════════════════════════════════════════════════════
# MONTAGEM DO RESULTADO
# ═══════════════════════════════════════════════════════════════════════════════

def montar_resultado(
    loja_id: str,
    preco: float,
    titulo: str,
    url: str,
    condicao: str,
    soup: Optional[BeautifulSoup] = None,
) -> dict:
    """
    Constrói o dicionário padronizado de resultado.
    preco_final == preco real (cupons NÃO alteram o preço final).
    """
    cupons = montar_possiveis_cupons(loja_id, soup)
    link_tipo = detectar_tipo_link(url)
    return {
        "loja": LOJAS_NOMES.get(loja_id, loja_id),
        "loja_id": loja_id,
        "preco": round(float(preco), 2),
        "preco_final": round(float(preco), 2),
        "titulo": titulo,
        "url": url,
        "condicao": normalizar_condicao(condicao),
        "link_tipo": link_tipo,
        "possiveis_cupons": cupons,
        "melhor_cupom": cupons[0] if cupons else None,
        "cupom_confirmado": False,
        "observacao_cupom": (
            "Cupons listados são possíveis, não confirmados. Teste no checkout."
            if cupons else ""
        ),
    }


def filtrar_por_condicao(produto: dict, resultados: list[dict]) -> list[dict]:
    aceita_usado = bool(produto.get("aceita_usado", True))
    aceita_novo = bool(produto.get("aceita_novo", True))
    filtrados = []
    for r in resultados:
        cond = str(r.get("condicao", "")).lower()
        eh_usado = "usado" in cond or "seminovo" in cond
        eh_novo = "novo" in cond and "seminovo" not in cond
        if eh_usado and aceita_usado:
            filtrados.append(r)
        elif eh_novo and aceita_novo:
            filtrados.append(r)
        elif not eh_usado and not eh_novo:
            filtrados.append(r)
    return filtrados


# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPERS
# ═══════════════════════════════════════════════════════════════════════════════

# ── Mercado Livre ─────────────────────────────────────────────────────────────

def buscar_mercadolivre(nome: str) -> Optional[dict]:
    """
    Estratégia 1: API REST oficial (sem chave, gratuita).
    Estratégia 2: scraping da lista HTML (fallback se API bloquear).
    """
    # --- Estratégia 1: API oficial ---
    try:
        data = get_json(
            "https://api.mercadolibre.com/sites/MLB/search",
            params={"q": nome, "limit": 10},
        )
        if data and "results" in data:
            for item in data["results"]:
                titulo = item.get("title", "")
                if not titulo_parece_relevante(titulo, nome):
                    continue
                preco = item.get("price")
                if not preco or float(preco) <= 0:
                    continue
                permalink = item.get("permalink", "")
                condicao_raw = item.get("condition", "new")
                resultado = montar_resultado(
                    loja_id="mercadolivre",
                    preco=float(preco),
                    titulo=titulo,
                    url=permalink,
                    condicao=condicao_raw,
                )
                resultado["thumbnail"] = item.get("thumbnail", "")
                resultado["seller"] = (item.get("seller") or {}).get("nickname", "")
                resultado["sold_quantity"] = item.get("sold_quantity", 0)
                return resultado
    except Exception as e:
        log.warning(f"[ML API] {e}")

    # --- Estratégia 2: scraping HTML ---
    try:
        termo = quote_plus(nome).replace("+", "-")
        url_busca = f"https://lista.mercadolivre.com.br/{termo}"
        html = get_html(url_busca)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("li.ui-search-layout__item")

        for card in cards[:10]:
            # Preço: fração inteira + centavos
            preco_el = card.select_one(".andes-money-amount__fraction")
            cents_el = card.select_one(".andes-money-amount__cents")
            if not preco_el:
                continue
            val = preco_el.get_text(strip=True).replace(".", "")
            if cents_el:
                val += "," + cents_el.get_text(strip=True)
            preco = limpar_preco(val)
            if not preco or preco <= 0:
                continue

            titulo_el = card.select_one(
                ".ui-search-item__title, "
                "a.poly-component__title, "
                "h2.ui-search-item__title"
            )
            titulo = titulo_el.get_text(strip=True) if titulo_el else nome
            if not titulo_parece_relevante(titulo, nome):
                continue

            # Link: preferência por links /MLB- (produto direto)
            link_el = (
                card.select_one("a[href*='produto.mercadolivre']")
                or card.select_one("a[href*='/MLB-']")
                or card.select_one("a.ui-search-link[href]")
                or card.select_one("a[href]")
            )
            link = link_el.get("href") if link_el else url_busca

            # Condição: badge no card
            cond_el = card.select_one(
                ".ui-search-item__condition, "
                "[class*='condition'], "
                "[class*='Condition']"
            )
            condicao = cond_el.get_text(strip=True) if cond_el else "Novo"

            return montar_resultado("mercadolivre", preco, titulo, link, condicao, soup)

    except Exception as e:
        log.warning(f"[ML scraping] {e}")

    return None


# ── Amazon ────────────────────────────────────────────────────────────────────

def buscar_amazon(nome: str) -> Optional[dict]:
    """
    Tenta JSON-LD primeiro; fallback para seletores HTML.
    O seletor .a-price .a-offscreen já traz o preço completo formatado.
    """
    try:
        url_busca = f"https://www.amazon.com.br/s?k={quote_plus(nome)}"
        html = get_html(url_busca)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        base = "https://www.amazon.com.br"

        # Tentativa 1: JSON-LD
        for p in extrair_json_ld_produtos(soup, base, url_busca):
            if titulo_parece_relevante(p["titulo"], nome) and p["preco"] > 10:
                return montar_resultado("amazon", p["preco"], p["titulo"], p["url"], p["condicao"], soup)

        # Tentativa 2: cards de resultado
        for card in soup.select('[data-component-type="s-search-result"]')[:10]:
            # Preço — .a-offscreen já tem "R$ 1.235,60" em texto puro
            preco = None
            for sel in [".a-price .a-offscreen", ".a-price-whole"]:
                el = card.select_one(sel)
                if el:
                    preco = limpar_preco(el.get_text(strip=True))
                    if preco and preco > 10:
                        break
            if not preco:
                continue

            titulo_el = card.select_one("h2 a span, h2 span")
            titulo = titulo_el.get_text(strip=True) if titulo_el else nome
            if not titulo_parece_relevante(titulo, nome):
                continue

            # Link direto do produto /dp/
            link_el = (
                card.select_one("a[href*='/dp/']")
                or card.select_one("h2 a[href]")
            )
            link = normalizar_url(base, link_el.get("href") if link_el else "", url_busca)

            # Condição: busca padrão da Amazon é "Novo"
            condicao = "Novo"
            cond_el = card.select_one(".a-color-secondary")
            if cond_el:
                txt = cond_el.get_text(strip=True).lower()
                if "usado" in txt or "used" in txt:
                    condicao = "Usado"
                elif "recondicionado" in txt or "renewed" in txt:
                    condicao = "Recondicionado"

            return montar_resultado("amazon", preco, titulo, link, condicao, soup)

    except Exception as e:
        log.warning(f"[Amazon] {e}")

    return None


# ── KaBuM ─────────────────────────────────────────────────────────────────────

def buscar_kabum(nome: str) -> Optional[dict]:
    """
    Tenta JSON-LD (que inclui URL de produto) primeiro.
    Fallback: cards HTML com seletores prioritários para link /produto/.
    """
    try:
        url_busca = f"https://www.kabum.com.br/busca/{quote_plus(nome)}"
        html = get_html(url_busca)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        base = "https://www.kabum.com.br"

        # Tentativa 1: JSON-LD (mais confiável para URL de produto)
        for p in extrair_json_ld_produtos(soup, base, url_busca):
            if titulo_parece_relevante(p["titulo"], nome) and p["preco"] > 10:
                return montar_resultado("kabum", p["preco"], p["titulo"], p["url"], p["condicao"], soup)

        # Tentativa 2: cards HTML
        cards = soup.select(
            "article.productCard, "
            "[data-testid='product-card'], "
            "div[class*='ProductCard'], "
            "div[class*='product-card'], "
            "article[class*='Card']"
        )
        for card in cards[:15]:
            texto_card = card.get_text(" ", strip=True)
            if "R$" not in texto_card:
                continue

            preco = None
            for sel in [
                "[class*='finalPrice']", "[class*='priceCard']",
                "[data-testid='price']", "span[class*='Price']", "span[class*='price']",
            ]:
                el = card.select_one(sel)
                if el:
                    preco = limpar_preco(el.get_text(" ", strip=True))
                    if preco and preco > 10:
                        break
            if not preco:
                preco = limpar_preco(texto_card)
            if not preco or preco <= 10:
                continue

            titulo_el = card.select_one(
                "[class*='nameCard'], [data-testid='product-name'], "
                "h2, h3, [class*='Name']"
            )
            titulo = titulo_el.get_text(" ", strip=True) if titulo_el else nome
            if not titulo_parece_relevante(titulo, nome):
                continue

            # Link — KaBuM: /produto/CODIGO/slug
            link_el = (
                card.select_one("a[href*='/produto/']")
                or card.select_one("a[href]")
            )
            link = normalizar_url(base, link_el.get("href") if link_el else "", url_busca)

            return montar_resultado("kabum", preco, titulo, link, "Novo", soup)

    except Exception as e:
        log.warning(f"[KaBuM] {e}")

    return None


# ── Magazine Luiza ────────────────────────────────────────────────────────────

def buscar_magalu(nome: str) -> Optional[dict]:
    """
    Tenta JSON-LD primeiro (URL de produto inclusa).
    Fallback: cards HTML com link /p/ ou /produto/.
    """
    try:
        url_busca = f"https://www.magazineluiza.com.br/busca/{quote_plus(nome)}/"
        html = get_html(url_busca)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        base = "https://www.magazineluiza.com.br"

        # Tentativa 1: JSON-LD
        for p in extrair_json_ld_produtos(soup, base, url_busca):
            if titulo_parece_relevante(p["titulo"], nome) and p["preco"] > 10:
                return montar_resultado("magalu", p["preco"], p["titulo"], p["url"], p["condicao"], soup)

        # Tentativa 2: __NEXT_DATA__ (Magalu usa Next.js)
        nd_tag = soup.select_one("script#__NEXT_DATA__")
        if nd_tag:
            try:
                nd = json.loads(nd_tag.string or "")
                # Navega pela árvore procurando listas de produtos
                produtos_nd = (
                    nd.get("props", {})
                    .get("pageProps", {})
                    .get("data", {})
                    .get("search", {})
                    .get("products", [])
                )
                for prod in produtos_nd[:10]:
                    titulo = prod.get("title") or prod.get("description") or ""
                    if not titulo_parece_relevante(titulo, nome):
                        continue
                    preco = limpar_preco(str(prod.get("price") or prod.get("priceTag") or ""))
                    if not preco or preco <= 10:
                        continue
                    slug = prod.get("slug") or prod.get("id") or ""
                    link = normalizar_url(base, f"/{slug}" if slug else "", url_busca)
                    condicao = prod.get("condition") or "Novo"
                    return montar_resultado("magalu", preco, titulo, link, condicao, soup)
            except Exception:
                pass

        # Tentativa 3: cards HTML
        cards = soup.select(
            "[data-testid='product-card'], "
            "li[class*='product'], "
            "article[class*='product'], "
            "div[class*='ProductCard']"
        )
        for card in cards[:15]:
            texto_card = card.get_text(" ", strip=True)
            if "R$" not in texto_card:
                continue

            preco = None
            for sel in [
                "[data-testid='price-value']", "p[data-testid*='price']",
                "span[data-testid*='price']", "[class*='price-template']",
                "[class*='Price']",
            ]:
                el = card.select_one(sel)
                if el:
                    preco = limpar_preco(el.get_text(" ", strip=True))
                    if preco and preco > 10:
                        break
            if not preco:
                preco = limpar_preco(texto_card)
            if not preco or preco <= 10:
                continue

            titulo_el = card.select_one(
                "[data-testid='product-title'], h2, h3, "
                "[class*='ProductTitle'], [class*='product-title']"
            )
            titulo = titulo_el.get_text(" ", strip=True) if titulo_el else nome
            if not titulo_parece_relevante(titulo, nome):
                continue

            # Link — Magalu: /slug/p/CODIGO/
            link_el = (
                card.select_one("a[href*='/p/']")
                or card.select_one("a[href]")
            )
            link = normalizar_url(base, link_el.get("href") if link_el else "", url_busca)

            return montar_resultado("magalu", preco, titulo, link, "Novo", soup)

    except Exception as e:
        log.warning(f"[Magalu] {e}")

    return None


# ── OLX ──────────────────────────────────────────────────────────────────────

def buscar_olx(nome: str) -> Optional[dict]:
    """
    OLX usa React SPA. Tenta extrair de __NEXT_DATA__ (SSR parcial).
    Fallback: seletores HTML.
    NOTA: resultado pode ser vazio se OLX não renderizar no servidor.
    """
    try:
        url_busca = f"https://www.olx.com.br/brasil?q={quote_plus(nome)}"
        html = get_html(url_busca)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")

        # Tentativa 1: __NEXT_DATA__
        nd_tag = soup.select_one("script#__NEXT_DATA__")
        if nd_tag:
            try:
                nd = json.loads(nd_tag.string or "")
                ads = (
                    nd.get("props", {})
                    .get("pageProps", {})
                    .get("ads", [])
                )
                for ad in ads[:10]:
                    preco_raw = ad.get("price", "")
                    preco = limpar_preco(str(preco_raw))
                    if not preco or preco <= 10:
                        continue
                    titulo = ad.get("title") or nome
                    if not titulo_parece_relevante(titulo, nome):
                        continue
                    link = ad.get("url") or url_busca
                    # OLX não tem campo condition estruturado; tenta pelo title
                    condicao_raw = str(ad.get("category", {}).get("name", "")).lower()
                    condicao = "Usado" if "usado" in condicao_raw else "Não informado"
                    return montar_resultado("olx", preco, titulo, link, condicao)
            except Exception:
                pass

        # Tentativa 2: seletores HTML
        cards = soup.select(
            "section[data-ds-component='DS-AdCard'], "
            "[data-testid='ad-card'], "
            "li[class*='AdCard'], "
            "article"
        )
        for card in cards[:15]:
            texto_card = card.get_text(" ", strip=True)
            if "R$" not in texto_card:
                continue

            preco_el = card.select_one(
                '[data-lurker-detail="price"], [aria-label*="Preço"], '
                "[class*='price'], [class*='Price']"
            )
            preco = limpar_preco(preco_el.get_text(" ", strip=True) if preco_el else texto_card)
            if not preco or preco <= 10:
                continue

            titulo_el = card.select_one("h2, h3, [aria-label*='Título'], [class*='title']")
            titulo = titulo_el.get_text(" ", strip=True) if titulo_el else nome
            if not titulo_parece_relevante(titulo, nome):
                continue

            link_el = card.select_one("a[href*='olx.com.br'], a[href]")
            link = link_el.get("href") if link_el else url_busca

            return montar_resultado("olx", preco, titulo, link, "Usado")

    except Exception as e:
        log.warning(f"[OLX] {e}")

    return None


# ── Enjoei ────────────────────────────────────────────────────────────────────

def buscar_enjoei(nome: str) -> Optional[dict]:
    """
    Enjoei é SPA React. Tenta JSON-LD (SSR) e seletores HTML.
    """
    try:
        url_busca = f"https://www.enjoei.com.br/busca?q={quote_plus(nome)}"
        html = get_html(url_busca)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        base = "https://www.enjoei.com.br"

        # Tentativa 1: JSON-LD
        for p in extrair_json_ld_produtos(soup, base, url_busca):
            if titulo_parece_relevante(p["titulo"], nome) and p["preco"] > 5:
                return montar_resultado("enjoei", p["preco"], p["titulo"], p["url"], p["condicao"], soup)

        # Tentativa 2: __NEXT_DATA__
        nd_tag = soup.select_one("script#__NEXT_DATA__")
        if nd_tag:
            try:
                nd = json.loads(nd_tag.string or "")
                produtos = (
                    nd.get("props", {})
                    .get("pageProps", {})
                    .get("products", [])
                    or nd.get("props", {})
                    .get("pageProps", {})
                    .get("items", [])
                )
                for prod in produtos[:10]:
                    titulo = prod.get("title") or prod.get("name") or ""
                    if not titulo_parece_relevante(titulo, nome):
                        continue
                    preco = limpar_preco(str(prod.get("price") or prod.get("amount") or ""))
                    if not preco or preco <= 5:
                        continue
                    slug = prod.get("slug") or prod.get("id") or ""
                    link = normalizar_url(base, f"/p/{slug}" if slug else "", url_busca)
                    return montar_resultado("enjoei", preco, titulo, link, "Seminovo", soup)
            except Exception:
                pass

        # Tentativa 3: seletores HTML
        cards = soup.select(
            "a[href*='/p/'], .product-card, "
            "[data-testid*='product'], article, li"
        )
        for card in cards[:15]:
            texto_card = card.get_text(" ", strip=True)
            if "R$" not in texto_card:
                continue

            preco_el = card.select_one(
                ".price, [data-testid*='price'], "
                "span[class*='price'], span[class*='Price']"
            )
            preco = limpar_preco(preco_el.get_text(" ", strip=True) if preco_el else texto_card)
            if not preco or preco <= 5:
                continue

            titulo_el = card.select_one(".product-title, h2, h3, [class*='title']")
            titulo = titulo_el.get_text(" ", strip=True) if titulo_el else nome
            if not titulo_parece_relevante(titulo, nome):
                continue

            link_el = card if getattr(card, "name", None) == "a" else card.select_one("a[href]")
            link = normalizar_url(base, link_el.get("href") if link_el else "", url_busca)

            return montar_resultado("enjoei", preco, titulo, link, "Seminovo", soup)

    except Exception as e:
        log.warning(f"[Enjoei] {e}")

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# ORQUESTRADOR
# ═══════════════════════════════════════════════════════════════════════════════

BUSCADORES = [
    buscar_mercadolivre,
    buscar_amazon,
    buscar_kabum,
    buscar_magalu,
    buscar_olx,
    buscar_enjoei,
]


def buscar_em_todos(nome: str, delay: float = 0.8) -> list[dict]:
    """
    Executa todos os buscadores sequencialmente com delay entre requisições.
    Retorna lista ordenada por preco_final crescente.
    """
    resultados = []
    for fn in BUSCADORES:
        try:
            res = fn(nome)
            if res:
                resultados.append(res)
                log.info(
                    f"  [{res['loja']}] R$ {res['preco_final']:.2f} | "
                    f"{res['condicao']} | {res['link_tipo']} | {res['titulo'][:50]}"
                )
        except Exception as e:
            log.warning(f"Erro em {fn.__name__}: {e}")
        time.sleep(delay)

    return sorted(resultados, key=lambda x: x["preco_final"])


# ═══════════════════════════════════════════════════════════════════════════════
# E-MAIL
# ═══════════════════════════════════════════════════════════════════════════════

def enviar_email(assunto: str, html: str, destinatario: Optional[str] = None) -> bool:
    dest = destinatario or EMAIL_DESTINATARIO_PADRAO
    if not EMAIL_REMETENTE or not EMAIL_SENHA:
        log.error("Credenciais de e-mail não configuradas!")
        return False
    if not dest:
        log.error("Destinatário de e-mail não configurado!")
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"] = EMAIL_REMETENTE
    msg["To"] = dest
    msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(EMAIL_REMETENTE, EMAIL_SENHA)
            s.sendmail(EMAIL_REMETENTE, dest, msg.as_string())
        log.info(f"✅ E-mail enviado para {dest}: {assunto}")
        return True
    except Exception as e:
        log.error(f"Falha ao enviar e-mail: {e}")
        return False


def montar_email_alerta(
    produto: dict,
    resultados: list[dict],
    tipo_alerta: str = "META_ATINGIDA",
    pct: Optional[float] = None,
) -> str:
    nome = produto["nome"]
    meta = float(produto["preco_meta"])
    melhor = resultados[0]
    melhor_preco = melhor["preco_final"]
    menor_hist = banco.menor_preco_historico(produto["id"])
    preco_sugerido = calcular_preco_sugerido(meta, melhor_preco, menor_hist)

    cor_topo = "#0d1b4b" if tipo_alerta == "META_ATINGIDA" else "#e65100"
    titulo_topo = (
        "🔔 Meta Atingida!"
        if tipo_alerta == "META_ATINGIDA"
        else "⚡ Preço próximo da sua meta"
    )

    lojas_rows = ""
    for r in resultados:
        preco_r = r["preco_final"]
        cor = (
            "#2e7d32" if preco_r <= meta
            else "#e65100" if preco_r <= meta * 1.10
            else "#333"
        )
        cupons = r.get("possiveis_cupons", [])
        cupom_html = (
            "<br>".join(
                f"<code>{c['codigo']}</code> "
                f"<small style='color:#999'>possível, teste no checkout</small>"
                for c in cupons[:2]
            )
            if cupons else "—"
        )
        link_label = "Ver produto →" if r.get("link_tipo") == "produto" else "Ver busca →"
        lojas_rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;">{r['loja']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;font-weight:700;color:{cor};">
            R$ {preco_r:.2f}
          </td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;">{r.get('condicao','—')}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;">{cupom_html}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;">
            <a href="{r['url']}" style="color:#0d1b4b;">{link_label}</a>
          </td>
        </tr>"""

    pct_bloco = f"<p>Distância da meta: <b>{pct:.1f}% acima</b></p>" if pct is not None else ""
    hist_bloco = (
        f"<p>Menor preço histórico: <b>R$ {menor_hist:.2f}</b></p>"
        if menor_hist else ""
    )

    return f"""
    <html>
      <body style="font-family:Arial,sans-serif;max-width:720px;margin:0 auto;color:#212121;">
        <div style="background:{cor_topo};color:#fff;padding:22px 26px;border-radius:10px 10px 0 0;">
          <h1 style="margin:0;font-size:1.3em;">{titulo_topo} — {nome}</h1>
          <p style="margin:6px 0 0;opacity:.8;">{datetime.now().strftime("%d/%m/%Y %H:%M")}</p>
        </div>
        <div style="border:1px solid #e0e0e0;border-top:none;padding:22px 26px;border-radius:0 0 10px 10px;">
          <p>Melhor preço:
            <b style="font-size:1.5em;color:#2e7d32;">R$ {melhor_preco:.2f}</b>
            na <b>{melhor['loja']}</b>
          </p>
          <p>Meta: <b>R$ {meta:.2f}</b> &nbsp;|&nbsp;
             Preço sugerido: <b>R$ {preco_sugerido:.2f}</b>
          </p>
          <p>Condição: <b>{melhor.get('condicao','Não informado')}</b></p>
          {pct_bloco}{hist_bloco}
          <h3 style="margin-top:24px;">Comparativo completo</h3>
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
          <a href="{melhor['url']}"
             style="display:inline-block;margin-top:20px;background:{cor_topo};
                    color:#fff;padding:12px 26px;border-radius:7px;
                    text-decoration:none;font-weight:bold;">
            Ver melhor oferta →
          </a>
          <p style="font-size:11px;color:#999;margin-top:20px;border-top:1px solid #eee;padding-top:12px;">
            Preços mudam a qualquer momento. Cupons precisam ser testados no checkout.
          </p>
        </div>
      </body>
    </html>
    """


# ═══════════════════════════════════════════════════════════════════════════════
# CICLO DE MONITORAMENTO
# ═══════════════════════════════════════════════════════════════════════════════

def verificar_todos() -> None:
    log.info("🔍 Iniciando verificação de preços...")
    produtos = banco.listar_produtos()
    if not produtos:
        log.info("Nenhum produto cadastrado.")
        return

    for p in produtos:
        nome = p["nome"]
        log.info(f"→ Verificando: {nome}")

        resultados = buscar_em_todos(nome)
        if not resultados:
            log.warning(f"  ⚠️  Sem resultados para '{nome}'")
            continue

        resultados = filtrar_por_condicao(p, resultados)
        if not resultados:
            log.warning(f"  ⚠️  Nenhum resultado compatível com condições aceitas para '{nome}'")
            continue

        resultados = sorted(resultados, key=lambda x: x["preco_final"])

        for r in resultados:
            banco.inserir_historico(
                p["id"],
                r["loja"],
                r["loja_id"],
                r["preco_final"],
                r.get("condicao", ""),
                r.get("url", ""),
            )

        melhor = resultados[0]
        meta = float(p["preco_meta"])
        melhor_preco = melhor["preco_final"]
        alerta_pct = float(p.get("alerta_proximo_pct", 10))
        limite_proximo = meta * (1 + alerta_pct / 100)
        destinatario = p.get("email") or EMAIL_DESTINATARIO_PADRAO

        log.info(
            f"  Melhor: {melhor['loja']} R$ {melhor_preco:.2f} | "
            f"Meta: R$ {meta:.2f} | Até próximo: R$ {limite_proximo:.2f} | "
            f"Condição: {melhor.get('condicao')} | Link: {melhor.get('link_tipo')}"
        )

        if melhor_preco <= meta:
            chave = f"{p['id']}_atingiu_{melhor['loja_id']}_{round(melhor_preco)}"
            if not banco.alerta_ja_enviado(chave):
                enviado = enviar_email(
                    f"✅ {nome} — R$ {melhor_preco:.2f} na {melhor['loja']}!",
                    montar_email_alerta(p, resultados, tipo_alerta="META_ATINGIDA"),
                    destinatario=destinatario,
                )
                if enviado:
                    banco.registrar_alerta(p["id"], chave)

        elif melhor_preco <= limite_proximo:
            pct = ((melhor_preco - meta) / meta) * 100
            chave = f"{p['id']}_proximo_{melhor['loja_id']}_{round(pct)}"
            if not banco.alerta_ja_enviado(chave):
                enviado = enviar_email(
                    f"⚡ {nome} próximo da meta: R$ {melhor_preco:.2f}",
                    montar_email_alerta(p, resultados, tipo_alerta="PRECO_PROXIMO", pct=pct),
                    destinatario=destinatario,
                )
                if enviado:
                    banco.registrar_alerta(p["id"], chave)
        else:
            log.info("  Nenhum alerta. Preço ainda distante da meta.")

    log.info("✔️  Verificação concluída.\n")