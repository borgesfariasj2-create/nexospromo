"""
================================================================================
  NEXOS PROMO BOT — Scraper de Promoções + Envio Telegram + WhatsApp
  Hospede no Railway (railway.app) — grátis
================================================================================
"""

import os
import re
import json
import time
import random
import hashlib
import requests
from datetime import datetime
from bs4 import BeautifulSoup

# ── Configurações via variáveis de ambiente no Railway ─────────────────────────
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003723940229")
AMAZON_TAG       = os.getenv("AMAZON_TAG", "")        # Seu ID de afiliado Amazon
ML_TAG           = os.getenv("ML_TAG", "")            # Seu ID afiliado Mercado Livre
EVOLUTION_URL    = os.getenv("EVOLUTION_URL", "")     # URL da Evolution API
EVOLUTION_KEY    = os.getenv("EVOLUTION_KEY", "")     # API Key da Evolution
WHATSAPP_NUMBER  = os.getenv("WHATSAPP_NUMBER", "")   # Número ou grupo WhatsApp
SUPABASE_URL     = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY     = os.getenv("SUPABASE_KEY", "")

# ── Headers para não ser bloqueado ────────────────────────────────────────────
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# ══════════════════════════════════════════════════════════════════════════════
#  SCRAPERS DE PROMOÇÕES
# ══════════════════════════════════════════════════════════════════════════════

def scrape_pelando() -> list:
    """Busca promoções quentes do Pelando."""
    promos = []
    try:
        print("[PELANDO] Buscando promoções...")
        url = "https://www.pelando.com.br/api/graphql"
        query = {
            "query": """
            query {
              hotDeals(page: 1, pageSize: 10) {
                edges {
                  node {
                    title
                    price
                    nextBestPrice
                    url
                    coupon
                    merchant { name }
                    temperature
                  }
                }
              }
            }
            """
        }
        resp = requests.post(url, json=query, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            deals = data.get("data", {}).get("hotDeals", {}).get("edges", [])
            for edge in deals:
                node = edge.get("node", {})
                preco = node.get("price")
                preco_ant = node.get("nextBestPrice")
                if not preco:
                    continue
                desconto = None
                if preco_ant and preco_ant > preco:
                    desconto = round((1 - preco / preco_ant) * 100)
                promos.append({
                    "fonte":    "Pelando",
                    "titulo":   node.get("title", ""),
                    "preco":    preco,
                    "preco_de": preco_ant,
                    "desconto": desconto,
                    "loja":     node.get("merchant", {}).get("name", ""),
                    "cupom":    node.get("coupon", ""),
                    "url":      node.get("url", ""),
                    "temp":     node.get("temperature", 0),
                })
        print(f"[PELANDO] ✓ {len(promos)} promoções encontradas")
    except Exception as e:
        print(f"[PELANDO] Erro: {e}")
    return promos


def scrape_promocao_ofertas() -> list:
    """Busca promoções do site Promoção de Ofertas."""
    promos = []
    try:
        print("[PROMO OFERTAS] Buscando promoções...")
        url = "https://www.promocaodeofertas.com.br/promocoes/"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select(".offer-card, .deal-card, article.offer")[:10]
        for card in cards:
            titulo = card.select_one("h2, h3, .offer-title, .deal-title")
            preco  = card.select_one(".price, .offer-price, .deal-price")
            link   = card.select_one("a")
            cupom  = card.select_one(".coupon, .cupom, .coupon-code")
            if not titulo or not link:
                continue
            preco_val = None
            if preco:
                nums = re.findall(r"[\d.,]+", preco.text)
                if nums:
                    preco_val = float(nums[0].replace(".", "").replace(",", "."))
            promos.append({
                "fonte":  "Promoção de Ofertas",
                "titulo": titulo.text.strip(),
                "preco":  preco_val,
                "cupom":  cupom.text.strip() if cupom else "",
                "url":    link.get("href", ""),
                "loja":   "",
                "temp":   100,
            })
        print(f"[PROMO OFERTAS] ✓ {len(promos)} promoções encontradas")
    except Exception as e:
        print(f"[PROMO OFERTAS] Erro: {e}")
    return promos


def scrape_amazon_ofertas() -> list:
    """Busca ofertas do dia na Amazon Brasil."""
    promos = []
    try:
        print("[AMAZON] Buscando ofertas do dia...")
        url = "https://www.amazon.com.br/deals"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("[data-testid='deal-card'], .dealCard, .a-section.octopus-dlp-asin-section")[:10]
        for item in items:
            titulo = item.select_one(".a-size-base-plus, .dealTitle, h2")
            preco  = item.select_one(".a-price .a-offscreen, .dealPrice")
            link   = item.select_one("a")
            if not titulo or not link:
                continue
            href = link.get("href", "")
            if not href.startswith("http"):
                href = "https://www.amazon.com.br" + href
            # Adiciona tag de afiliado
            if AMAZON_TAG:
                href = adicionar_tag_amazon(href, AMAZON_TAG)
            preco_val = None
            if preco:
                nums = re.findall(r"[\d.,]+", preco.text)
                if nums:
                    preco_val = float(nums[0].replace(".", "").replace(",", "."))
            promos.append({
                "fonte":  "Amazon",
                "titulo": titulo.text.strip(),
                "preco":  preco_val,
                "cupom":  "",
                "url":    href,
                "loja":   "Amazon",
                "temp":   100,
            })
        print(f"[AMAZON] ✓ {len(promos)} ofertas encontradas")
    except Exception as e:
        print(f"[AMAZON] Erro: {e}")
    return promos


def scrape_mercadolivre_ofertas() -> list:
    """Busca ofertas do Mercado Livre."""
    promos = []
    try:
        print("[MERCADO LIVRE] Buscando ofertas...")
        url = "https://www.mercadolivre.com.br/ofertas"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select(".promotion-item, .poly-card, .ui-search-result")[:10]
        for item in items:
            titulo = item.select_one(".promotion-item__title, .poly-component__title, h2")
            preco  = item.select_one(".promotion-item__price, .andes-money-amount__fraction, .price-tag-fraction")
            link   = item.select_one("a")
            if not titulo or not link:
                continue
            href = link.get("href", "")
            if ML_TAG and href:
                href = f"{href}?deal_print_id={ML_TAG}" if "?" not in href else f"{href}&deal_print_id={ML_TAG}"
            preco_val = None
            if preco:
                nums = re.findall(r"[\d.,]+", preco.text)
                if nums:
                    preco_val = float(nums[0].replace(".", "").replace(",", "."))
            promos.append({
                "fonte":  "Mercado Livre",
                "titulo": titulo.text.strip()[:80],
                "preco":  preco_val,
                "cupom":  "",
                "url":    href,
                "loja":   "Mercado Livre",
                "temp":   100,
            })
        print(f"[MERCADO LIVRE] ✓ {len(promos)} ofertas encontradas")
    except Exception as e:
        print(f"[MERCADO LIVRE] Erro: {e}")
    return promos


# ══════════════════════════════════════════════════════════════════════════════
#  AFILIADOS
# ══════════════════════════════════════════════════════════════════════════════

def adicionar_tag_amazon(url: str, tag: str) -> str:
    """Adiciona tag de afiliado Amazon na URL."""
    if "tag=" in url:
        url = re.sub(r"tag=[^&]+", f"tag={tag}", url)
    elif "?" in url:
        url = f"{url}&tag={tag}"
    else:
        url = f"{url}?tag={tag}"
    return url


def gerar_link_afiliado(promo: dict) -> str:
    """Retorna URL com link de afiliado quando possível."""
    url = promo.get("url", "")
    fonte = promo.get("fonte", "")
    if fonte == "Amazon" and AMAZON_TAG:
        return adicionar_tag_amazon(url, AMAZON_TAG)
    if fonte == "Mercado Livre" and ML_TAG:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}deal_print_id={ML_TAG}"
    return url


# ══════════════════════════════════════════════════════════════════════════════
#  FORMATAÇÃO DA MENSAGEM
# ══════════════════════════════════════════════════════════════════════════════

def formatar_mensagem(promo: dict) -> str:
    """Monta a mensagem formatada para Telegram e WhatsApp."""
    titulo  = promo.get("titulo", "Promoção")[:80]
    preco   = promo.get("preco")
    preco_de = promo.get("preco_de")
    desconto = promo.get("desconto")
    loja    = promo.get("loja", promo.get("fonte", ""))
    cupom   = promo.get("cupom", "")
    url     = gerar_link_afiliado(promo)
    fonte   = promo.get("fonte", "")

    # Emoji por fonte
    emojis = {
        "Amazon":             "📦",
        "Mercado Livre":      "🛒",
        "Pelando":            "🔥",
        "Promoção de Ofertas": "💥",
    }
    emoji = emojis.get(fonte, "🏷️")

    msg = f"{emoji} *{titulo}*\n\n"

    if preco:
        preco_fmt = f"R$ {preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        msg += f"💰 *Por apenas {preco_fmt}*\n"

    if preco_de and desconto:
        de_fmt = f"R$ {preco_de:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        msg += f"~~De {de_fmt}~~ → *{desconto}% OFF*\n"

    if loja:
        msg += f"🏪 Loja: {loja}\n"

    if cupom:
        msg += f"\n🎟️ *CUPOM:* `{cupom}`\n"

    msg += f"\n🔗 [PEGAR OFERTA AGORA]({url})\n"
    msg += f"\n_Oferta via {fonte} • NexosPromo_"

    return msg


# ══════════════════════════════════════════════════════════════════════════════
#  ENVIO — TELEGRAM
# ══════════════════════════════════════════════════════════════════════════════

def enviar_telegram(mensagem: str) -> bool:
    """Envia mensagem no canal/grupo do Telegram."""
    if not TELEGRAM_TOKEN:
        print("[TELEGRAM] Token não configurado.")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        resp = requests.post(url, json={
            "chat_id":    TELEGRAM_CHAT_ID,
            "text":       mensagem,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        }, timeout=15)
        if resp.status_code == 200:
            print(f"  [TELEGRAM] ✓ Mensagem enviada!")
            return True
        else:
            print(f"  [TELEGRAM] Erro {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  [TELEGRAM] Erro: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  ENVIO — WHATSAPP (Evolution API)
# ══════════════════════════════════════════════════════════════════════════════

def enviar_whatsapp(mensagem: str) -> bool:
    """Envia mensagem no WhatsApp via Evolution API."""
    if not EVOLUTION_URL or not EVOLUTION_KEY or not WHATSAPP_NUMBER:
        print("[WHATSAPP] Evolution API não configurada — pulando.")
        return False
    try:
        # Remove formatação Markdown do Telegram (WhatsApp usa formato diferente)
        msg_wp = mensagem.replace("*", "").replace("~~", "").replace("`", "")
        url = f"{EVOLUTION_URL}/message/sendText/nexos"
        resp = requests.post(url, json={
            "number":  WHATSAPP_NUMBER,
            "text":    msg_wp,
            "delay":   1000,
        }, headers={
            "apikey":       EVOLUTION_KEY,
            "Content-Type": "application/json",
        }, timeout=15)
        if resp.status_code in (200, 201):
            print(f"  [WHATSAPP] ✓ Mensagem enviada!")
            return True
        else:
            print(f"  [WHATSAPP] Erro {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  [WHATSAPP] Erro: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  CONTROLE DE DUPLICATAS (via Supabase)
# ══════════════════════════════════════════════════════════════════════════════

def gerar_hash(promo: dict) -> str:
    """Gera hash único para cada promoção."""
    chave = f"{promo.get('titulo', '')}{promo.get('preco', '')}{promo.get('url', '')}"
    return hashlib.md5(chave.encode()).hexdigest()


def ja_enviada(hash_promo: str) -> bool:
    """Verifica se a promoção já foi enviada hoje."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False
    try:
        hoje = datetime.now().strftime("%Y-%m-%d")
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/promos_enviadas",
            params={"hash": f"eq.{hash_promo}", "data": f"eq.{hoje}"},
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
            timeout=10
        )
        return len(resp.json()) > 0
    except:
        return False


def marcar_enviada(promo: dict, hash_promo: str):
    """Salva promoção enviada no Supabase para evitar duplicata."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    try:
        requests.post(
            f"{SUPABASE_URL}/rest/v1/promos_enviadas",
            json={
                "hash":   hash_promo,
                "titulo": promo.get("titulo", "")[:100],
                "fonte":  promo.get("fonte", ""),
                "preco":  promo.get("preco"),
                "data":   datetime.now().strftime("%Y-%m-%d"),
            },
            headers={
                "apikey":        SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type":  "application/json",
                "Prefer":        "return=minimal",
            },
            timeout=10
        )
    except Exception as e:
        print(f"  [DB] Erro ao salvar: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  FLUXO PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def scrape_aliexpress() -> list:
    """Busca ofertas do AliExpress Brasil."""
    promos = []
    try:
        print("[ALIEXPRESS] Buscando ofertas...")
        url = "https://pt.aliexpress.com/deals.html"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select(".manhattan--container--1lP57Ag, .product-card, [class*='product']")[:10]
        for item in items:
            titulo = item.select_one("[class*='title'], h3, h2")
            preco  = item.select_one("[class*='price'], .price")
            link   = item.select_one("a")
            if not titulo or not link:
                continue
            href = link.get("href", "")
            if href.startswith("//"):
                href = "https:" + href
            elif not href.startswith("http"):
                href = "https://pt.aliexpress.com" + href
            preco_val = None
            if preco:
                nums = re.findall(r"[\d.,]+", preco.text)
                if nums:
                    try:
                        preco_val = float(nums[0].replace(".", "").replace(",", "."))
                    except:
                        pass
            promos.append({
                "fonte":  "AliExpress",
                "titulo": titulo.text.strip()[:80],
                "preco":  preco_val,
                "cupom":  "",
                "url":    href,
                "loja":   "AliExpress",
                "temp":   90,
            })
        print(f"[ALIEXPRESS] ✓ {len(promos)} ofertas encontradas")
    except Exception as e:
        print(f"[ALIEXPRESS] Erro: {e}")
    return promos


def scrape_shopee() -> list:
    """Busca ofertas da Shopee Brasil via API pública."""
    promos = []
    try:
        print("[SHOPEE] Buscando ofertas...")
        url = "https://shopee.com.br/api/v4/flash_sale/get_all_sessions"
        resp = requests.get(url, headers={**HEADERS, "referer": "https://shopee.com.br"}, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            sessions = data.get("data", {}).get("sessions", [])
            for session in sessions[:2]:
                items = session.get("items", [])[:5]
                for item in items:
                    nome = item.get("name", "")
                    preco = item.get("price", 0) / 100000  # Shopee usa centavos x1000
                    preco_orig = item.get("price_before_discount", 0) / 100000
                    itemid = item.get("itemid", "")
                    shopid = item.get("shopid", "")
                    href = f"https://shopee.com.br/product/{shopid}/{itemid}"
                    desconto = None
                    if preco_orig > preco:
                        desconto = round((1 - preco / preco_orig) * 100)
                    promos.append({
                        "fonte":    "Shopee",
                        "titulo":   nome[:80],
                        "preco":    round(preco, 2),
                        "preco_de": round(preco_orig, 2) if preco_orig else None,
                        "desconto": desconto,
                        "cupom":    "",
                        "url":      href,
                        "loja":     "Shopee",
                        "temp":     95,
                    })
        print(f"[SHOPEE] ✓ {len(promos)} ofertas encontradas")
    except Exception as e:
        print(f"[SHOPEE] Erro: {e}")
    return promos


def scrape_magalu() -> list:
    """Busca ofertas do Magazine Luiza."""
    promos = []
    try:
        print("[MAGALU] Buscando ofertas...")
        url = "https://www.magazineluiza.com.br/oferta-do-dia/"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("[data-testid='product-card'], .productCard, .sc-fqkvVR")[:10]
        for item in items:
            titulo = item.select_one("[data-testid='product-title'], h2, h3")
            preco  = item.select_one("[data-testid='price-value'], .sc-kpDqfm, [class*='price']")
            link   = item.select_one("a")
            if not titulo or not link:
                continue
            href = link.get("href", "")
            if not href.startswith("http"):
                href = "https://www.magazineluiza.com.br" + href
            preco_val = None
            if preco:
                nums = re.findall(r"[\d.,]+", preco.text)
                if nums:
                    try:
                        preco_val = float(nums[0].replace(".", "").replace(",", "."))
                    except:
                        pass
            promos.append({
                "fonte":  "Magazine Luiza",
                "titulo": titulo.text.strip()[:80],
                "preco":  preco_val,
                "cupom":  "",
                "url":    href,
                "loja":   "Magalu",
                "temp":   85,
            })
        print(f"[MAGALU] ✓ {len(promos)} ofertas encontradas")
    except Exception as e:
        print(f"[MAGALU] Erro: {e}")
    return promos


def scrape_casas_bahia() -> list:
    """Busca ofertas das Casas Bahia."""
    promos = []
    try:
        print("[CASAS BAHIA] Buscando ofertas...")
        url = "https://www.casasbahia.com.br/ofertas-do-dia"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select(".product-card, [class*='ProductCard'], [class*='product-item']")[:10]
        for item in items:
            titulo = item.select_one("h2, h3, [class*='title'], [class*='name']")
            preco  = item.select_one("[class*='price'], [class*='Price']")
            link   = item.select_one("a")
            if not titulo or not link:
                continue
            href = link.get("href", "")
            if not href.startswith("http"):
                href = "https://www.casasbahia.com.br" + href
            preco_val = None
            if preco:
                nums = re.findall(r"[\d.,]+", preco.text)
                if nums:
                    try:
                        preco_val = float(nums[0].replace(".", "").replace(",", "."))
                    except:
                        pass
            promos.append({
                "fonte":  "Casas Bahia",
                "titulo": titulo.text.strip()[:80],
                "preco":  preco_val,
                "cupom":  "",
                "url":    href,
                "loja":   "Casas Bahia",
                "temp":   80,
            })
        print(f"[CASAS BAHIA] ✓ {len(promos)} ofertas encontradas")
    except Exception as e:
        print(f"[CASAS BAHIA] Erro: {e}")
    return promos


def scrape_kabum() -> list:
    """Busca ofertas da KaBuM via API pública."""
    promos = []
    try:
        print("[KABUM] Buscando ofertas...")
        url = "https://servicespub.prod.api.aws.grupokabum.com.br/catalog/v2/products-by-category/oferta-do-dia?page_number=1&page_size=10&is_off=true"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("data", [])[:10]
            for item in items:
                nome     = item.get("name", "")
                preco    = item.get("vlr_final", item.get("price", 0))
                preco_de = item.get("vlr_normal", None)
                slug     = item.get("path", "")
                href     = f"https://www.kabum.com.br/produto/{slug}" if slug else ""
                desconto = None
                if preco_de and preco_de > preco:
                    desconto = round((1 - preco / preco_de) * 100)
                promos.append({
                    "fonte":    "KaBuM",
                    "titulo":   nome[:80],
                    "preco":    round(float(preco), 2),
                    "preco_de": round(float(preco_de), 2) if preco_de else None,
                    "desconto": desconto,
                    "cupom":    "",
                    "url":      href,
                    "loja":     "KaBuM",
                    "temp":     88,
                })
        print(f"[KABUM] ✓ {len(promos)} ofertas encontradas")
    except Exception as e:
        print(f"[KABUM] Erro: {e}")
    return promos


def buscar_todas_promos() -> list:
    """Roda todos os scrapers e junta as promoções."""
    todas = []
    todas += scrape_pelando()
    todas += scrape_shopee()
    todas += scrape_kabum()
    todas += scrape_amazon_ofertas()
    todas += scrape_mercadolivre_ofertas()
    todas += scrape_aliexpress()
    todas += scrape_magalu()
    todas += scrape_casas_bahia()
    todas += scrape_promocao_ofertas()
    # Ordena pelas mais quentes
    todas.sort(key=lambda x: x.get("temp", 0), reverse=True)
    return todas


def main():
    print("=" * 60)
    print("  NEXOS PROMO BOT — Iniciando")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 60)

    promos = buscar_todas_promos()
    print(f"\n📦 Total encontrado: {len(promos)} promoções\n")

    enviadas = 0
    for promo in promos:
        if not promo.get("titulo") or not promo.get("url"):
            continue

        hash_p = gerar_hash(promo)

        if ja_enviada(hash_p):
            print(f"  ⏭ Já enviada: {promo['titulo'][:50]}")
            continue

        print(f"\n📢 Enviando: {promo['titulo'][:60]}")
        mensagem = formatar_mensagem(promo)

        ok_tg = enviar_telegram(mensagem)
        time.sleep(2)  # Pausa entre Telegram e WhatsApp
        ok_wp = enviar_whatsapp(mensagem)

        if ok_tg or ok_wp:
            marcar_enviada(promo, hash_p)
            enviadas += 1

        # Pausa entre promoções para não ser bloqueado
        intervalo = random.randint(30, 60)
        print(f"  ⏳ Aguardando {intervalo}s antes da próxima...")
        time.sleep(intervalo)

        # Limita a 10 promoções por execução
        if enviadas >= 10:
            print("\n✅ Limite de 10 promoções por rodada atingido.")
            break

    print(f"\n{'='*60}")
    print(f"  ✅ Concluído! {enviadas} promoções enviadas.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
