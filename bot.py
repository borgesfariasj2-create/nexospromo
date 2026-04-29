"""
================================================================================
  NEXOS PROMO BOT v4
  - Qualquer produto (sem filtro)
  - Envia FOTO do produto no Telegram
  - Sem necessidade de API da Amazon ou Shopee
  - Fontes: Pelando, KaBuM, Pichau, Terabyte, Nuuvem, ML, Promoção de Ofertas
================================================================================
"""

import os
import re
import time
import random
import hashlib
import requests
from datetime import datetime
from bs4 import BeautifulSoup

# ── Configurações ──────────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003723940229")
AMAZON_TAG       = os.getenv("AMAZON_TAG", "20070b1-20")
ML_TAG           = os.getenv("ML_TAG", "")
SUPABASE_URL     = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY     = os.getenv("SUPABASE_KEY", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# ══════════════════════════════════════════════════════════════════════════════
#  SCRAPERS — Fontes que funcionam SEM API
# ══════════════════════════════════════════════════════════════════════════════

def scrape_pelando() -> list:
    """Pelando via GraphQL — retorna foto, título, preço, cupom."""
    promos = []
    try:
        print("[PELANDO] Buscando promoções...")
        url = "https://www.pelando.com.br/api/graphql"
        query = {
            "query": """
            query {
              hotDeals(page: 1, pageSize: 20) {
                edges {
                  node {
                    title
                    price
                    nextBestPrice
                    url
                    coupon
                    temperature
                    imageUrl
                    merchant { name }
                  }
                }
              }
            }
            """
        }
        resp = requests.post(url, json=query, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            deals = resp.json().get("data", {}).get("hotDeals", {}).get("edges", [])
            for edge in deals:
                node     = edge.get("node", {})
                preco    = node.get("price")
                preco_de = node.get("nextBestPrice")
                if not preco:
                    continue
                desconto = None
                if preco_de and preco_de > preco:
                    desconto = round((1 - preco / preco_de) * 100)
                promos.append({
                    "fonte":    "Pelando",
                    "titulo":   node.get("title", "")[:80],
                    "preco":    preco,
                    "preco_de": preco_de,
                    "desconto": desconto,
                    "loja":     node.get("merchant", {}).get("name", ""),
                    "cupom":    node.get("coupon", "") or "",
                    "url":      node.get("url", ""),
                    "foto":     node.get("imageUrl", "") or "",
                    "temp":     node.get("temperature", 0),
                })
        print(f"[PELANDO] ✓ {len(promos)} promoções")
    except Exception as e:
        print(f"[PELANDO] Erro: {e}")
    return promos


def scrape_kabum() -> list:
    """KaBuM via API pública — retorna foto e preço."""
    promos = []
    try:
        print("[KABUM] Buscando ofertas...")
        cats = ["oferta-do-dia", "computadores", "hardware", "perifericos",
                "smartphones-tablets", "games", "monitores-e-tvs",
                "tv-e-video", "eletrodomesticos", "casa-e-decoracao"]
        for cat in cats:
            url = (f"https://servicespub.prod.api.aws.grupokabum.com.br/catalog/v2/"
                   f"products-by-category/{cat}?page_number=1&page_size=10&is_off=true")
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue
            for item in resp.json().get("data", [])[:10]:
                nome     = item.get("name", "")
                preco    = float(item.get("vlr_final", item.get("price", 0)) or 0)
                preco_de = item.get("vlr_normal")
                slug     = item.get("path", "")
                foto     = item.get("img", item.get("image", "")) or ""
                href     = f"https://www.kabum.com.br/produto/{slug}" if slug else ""
                desconto = None
                if preco_de and float(preco_de) > preco:
                    desconto = round((1 - preco / float(preco_de)) * 100)
                if not nome or not href:
                    continue
                promos.append({
                    "fonte":    "KaBuM",
                    "titulo":   nome[:80],
                    "preco":    round(preco, 2),
                    "preco_de": round(float(preco_de), 2) if preco_de else None,
                    "desconto": desconto,
                    "cupom":    "",
                    "url":      href,
                    "foto":     foto,
                    "loja":     "KaBuM",
                    "temp":     95,
                })
            time.sleep(0.5)
        print(f"[KABUM] ✓ {len(promos)} ofertas")
    except Exception as e:
        print(f"[KABUM] Erro: {e}")
    return promos


def scrape_pichau() -> list:
    """Pichau via GraphQL — retorna foto."""
    promos = []
    try:
        print("[PICHAU] Buscando ofertas...")
        url  = "https://www.pichau.com.br/api/pichau/getOffers"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            items = resp.json().get("data", {}).get("products", {}).get("items", [])[:15]
            for item in items:
                nome     = item.get("name", "")
                preco    = float(item.get("price_range", {}).get("minimum_price", {})
                                 .get("final_price", {}).get("value", 0) or 0)
                preco_de = item.get("price_range", {}).get("minimum_price", {}) \
                               .get("regular_price", {}).get("value")
                url_key  = item.get("url_key", "")
                href     = f"https://www.pichau.com.br/{url_key}" if url_key else ""
                # Foto
                media    = item.get("media_gallery", [])
                foto     = media[0].get("url", "") if media else ""
                desconto = None
                if preco_de and float(preco_de) > preco:
                    desconto = round((1 - preco / float(preco_de)) * 100)
                if not nome or not href:
                    continue
                promos.append({
                    "fonte":    "Pichau",
                    "titulo":   nome[:80],
                    "preco":    round(preco, 2),
                    "preco_de": round(float(preco_de), 2) if preco_de else None,
                    "desconto": desconto,
                    "cupom":    "",
                    "url":      href,
                    "foto":     foto,
                    "loja":     "Pichau",
                    "temp":     90,
                })
        print(f"[PICHAU] ✓ {len(promos)} ofertas")
    except Exception as e:
        print(f"[PICHAU] Erro: {e}")
    return promos


def scrape_mercadolivre() -> list:
    """Mercado Livre scraping — pega foto da listagem."""
    promos = []
    try:
        print("[MERCADO LIVRE] Buscando ofertas...")
        url  = "https://www.mercadolivre.com.br/ofertas"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select(".promotion-item, .poly-card")[:20]
        for item in items:
            titulo = item.select_one(".promotion-item__title, .poly-component__title, h2")
            preco  = item.select_one(".promotion-item__price, .andes-money-amount__fraction")
            link   = item.select_one("a")
            img    = item.select_one("img")
            if not titulo or not link:
                continue
            href = link.get("href", "")
            if ML_TAG and href:
                sep  = "&" if "?" in href else "?"
                href = f"{href}{sep}deal_print_id={ML_TAG}"
            foto = ""
            if img:
                foto = img.get("data-src", img.get("src", "")) or ""
            preco_val = None
            if preco:
                nums = re.findall(r"[\d.,]+", preco.text)
                if nums:
                    try:
                        preco_val = float(nums[0].replace(".", "").replace(",", "."))
                    except:
                        pass
            promos.append({
                "fonte":  "Mercado Livre",
                "titulo": titulo.text.strip()[:80],
                "preco":  preco_val,
                "cupom":  "",
                "url":    href,
                "foto":   foto,
                "loja":   "Mercado Livre",
                "temp":   92,
            })
        print(f"[MERCADO LIVRE] ✓ {len(promos)} ofertas")
    except Exception as e:
        print(f"[MERCADO LIVRE] Erro: {e}")
    return promos


def scrape_terabyte() -> list:
    """Terabyte Shop scraping."""
    promos = []
    try:
        print("[TERABYTE] Buscando ofertas...")
        url  = "https://www.terabyteshop.com.br/promocoes"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select(".prd-bloco, .product-item")[:15]
        for item in items:
            titulo = item.select_one("h2, h3, .prd-nome")
            preco  = item.select_one(".prd-preco, [class*='price']")
            link   = item.select_one("a")
            img    = item.select_one("img")
            if not titulo or not link:
                continue
            href = link.get("href", "")
            if not href.startswith("http"):
                href = "https://www.terabyteshop.com.br" + href
            foto = ""
            if img:
                foto = img.get("data-src", img.get("src", "")) or ""
            preco_val = None
            if preco:
                nums = re.findall(r"[\d.,]+", preco.text)
                if nums:
                    try:
                        preco_val = float(nums[0].replace(".", "").replace(",", "."))
                    except:
                        pass
            promos.append({
                "fonte":  "Terabyte",
                "titulo": titulo.text.strip()[:80],
                "preco":  preco_val,
                "cupom":  "",
                "url":    href,
                "foto":   foto,
                "loja":   "Terabyte",
                "temp":   85,
            })
        print(f"[TERABYTE] ✓ {len(promos)} ofertas")
    except Exception as e:
        print(f"[TERABYTE] Erro: {e}")
    return promos


def scrape_nuuvem() -> list:
    """Nuuvem — jogos com maior desconto."""
    promos = []
    try:
        print("[NUUVEM] Buscando jogos...")
        url  = "https://www.nuuvem.com/br-pt/catalog/page/1/filter/discounted/sort/discount"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select(".product-card, [class*='product-item']")[:15]
        for item in items:
            titulo   = item.select_one("h3, h2, .product-title")
            preco    = item.select_one(".product-price--final, [class*='price']")
            desconto = item.select_one(".discount-tag, [class*='discount']")
            link     = item.select_one("a")
            img      = item.select_one("img")
            if not titulo or not link:
                continue
            href = link.get("href", "")
            if not href.startswith("http"):
                href = "https://www.nuuvem.com" + href
            foto = ""
            if img:
                foto = img.get("data-src", img.get("src", "")) or ""
            preco_val = None
            if preco:
                nums = re.findall(r"[\d.,]+", preco.text)
                if nums:
                    try:
                        preco_val = float(nums[0].replace(".", "").replace(",", "."))
                    except:
                        pass
            desc_val = None
            if desconto:
                nums = re.findall(r"\d+", desconto.text)
                if nums:
                    desc_val = int(nums[0])
            promos.append({
                "fonte":    "Nuuvem",
                "titulo":   titulo.text.strip()[:80],
                "preco":    preco_val,
                "desconto": desc_val,
                "cupom":    "",
                "url":      href,
                "foto":     foto,
                "loja":     "Nuuvem",
                "temp":     82,
            })
        print(f"[NUUVEM] ✓ {len(promos)} jogos")
    except Exception as e:
        print(f"[NUUVEM] Erro: {e}")
    return promos


def scrape_promocao_ofertas() -> list:
    """Promoção de Ofertas — scraping geral."""
    promos = []
    try:
        print("[PROMO OFERTAS] Buscando promoções...")
        url  = "https://www.promocaodeofertas.com.br/promocoes/"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("article, .offer-card, .deal-card")[:15]
        for item in items:
            titulo = item.select_one("h2, h3, .offer-title")
            preco  = item.select_one(".price, .offer-price")
            link   = item.select_one("a")
            img    = item.select_one("img")
            cupom  = item.select_one(".coupon, .cupom, .coupon-code")
            if not titulo or not link:
                continue
            href = link.get("href", "")
            foto = ""
            if img:
                foto = img.get("data-src", img.get("src", "")) or ""
            preco_val = None
            if preco:
                nums = re.findall(r"[\d.,]+", preco.text)
                if nums:
                    try:
                        preco_val = float(nums[0].replace(".", "").replace(",", "."))
                    except:
                        pass
            promos.append({
                "fonte":  "Promoção de Ofertas",
                "titulo": titulo.text.strip()[:80],
                "preco":  preco_val,
                "cupom":  cupom.text.strip() if cupom else "",
                "url":    href,
                "foto":   foto,
                "loja":   "",
                "temp":   80,
            })
        print(f"[PROMO OFERTAS] ✓ {len(promos)} promoções")
    except Exception as e:
        print(f"[PROMO OFERTAS] Erro: {e}")
    return promos


# ══════════════════════════════════════════════════════════════════════════════
#  AFILIADO AMAZON
# ══════════════════════════════════════════════════════════════════════════════

def adicionar_tag_amazon(url: str, tag: str) -> str:
    if "tag=" in url:
        return re.sub(r"tag=[^&]+", f"tag={tag}", url)
    return f"{url}&tag={tag}" if "?" in url else f"{url}?tag={tag}"


def gerar_link_afiliado(promo: dict) -> str:
    url   = promo.get("url", "")
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
    titulo   = promo.get("titulo", "Promoção")[:80]
    preco    = promo.get("preco")
    preco_de = promo.get("preco_de")
    desconto = promo.get("desconto")
    loja     = promo.get("loja", promo.get("fonte", ""))
    cupom    = promo.get("cupom", "")
    url      = gerar_link_afiliado(promo)
    fonte    = promo.get("fonte", "")

    emojis = {
        "Pelando":            "🔥",
        "KaBuM":              "💻",
        "Pichau":             "🖥️",
        "Terabyte":           "⚡",
        "Nuuvem":             "🎮",
        "Mercado Livre":      "🛒",
        "Promoção de Ofertas":"💥",
        "Amazon":             "📦",
    }
    emoji = emojis.get(fonte, "🏷️")

    msg = f"{emoji} *{titulo}*\n\n"

    if preco:
        pf = f"R$ {preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        msg += f"💰 *Por apenas {pf}*\n"

    if preco_de and desconto:
        df = f"R$ {preco_de:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        msg += f"~~De {df}~~ → *{desconto}% OFF* 🔥\n"
    elif desconto:
        msg += f"*{desconto}% OFF* 🔥\n"

    if loja:
        msg += f"🏪 Loja: {loja}\n"

    if cupom:
        msg += f"\n🎟️ *CUPOM:* `{cupom}`\n"

    msg += f"\n🔗 [PEGAR OFERTA AGORA]({url})\n"
    msg += f"\n_📢 @NexosPromoBot • {fonte}_"

    return msg


# ══════════════════════════════════════════════════════════════════════════════
#  ENVIO TELEGRAM — COM FOTO
# ══════════════════════════════════════════════════════════════════════════════

def enviar_telegram(promo: dict) -> bool:
    if not TELEGRAM_TOKEN:
        print("[TELEGRAM] Token não configurado.")
        return False

    mensagem = formatar_mensagem(promo)
    foto     = promo.get("foto", "")

    try:
        # Se tem foto válida, envia como foto com legenda
        if foto and foto.startswith("http"):
            url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            resp = requests.post(url, json={
                "chat_id":    TELEGRAM_CHAT_ID,
                "photo":      foto,
                "caption":    mensagem,
                "parse_mode": "Markdown",
            }, timeout=15)

            if resp.status_code == 200:
                print("  [TELEGRAM] ✓ Enviado com foto!")
                return True

            # Se foto falhou, tenta sem foto
            print(f"  [TELEGRAM] Foto falhou ({resp.status_code}), enviando sem foto...")

        # Envia só texto
        url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        resp = requests.post(url, json={
            "chat_id":                  TELEGRAM_CHAT_ID,
            "text":                     mensagem,
            "parse_mode":               "Markdown",
            "disable_web_page_preview": False,
        }, timeout=15)

        if resp.status_code == 200:
            print("  [TELEGRAM] ✓ Enviado!")
            return True

        print(f"  [TELEGRAM] Erro {resp.status_code}: {resp.text}")
        return False

    except Exception as e:
        print(f"  [TELEGRAM] Erro: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  CONTROLE DE DUPLICATAS
# ══════════════════════════════════════════════════════════════════════════════

def gerar_hash(promo: dict) -> str:
    chave = f"{promo.get('titulo','')}{preco_str(promo)}{promo.get('url','')}"
    return hashlib.md5(chave.encode()).hexdigest()

def preco_str(promo: dict) -> str:
    p = promo.get("preco")
    return str(p) if p else ""

def ja_enviada(hash_promo: str) -> bool:
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
        print(f"  [DB] Erro: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  NEXOS PROMO BOT v4 — Todos os produtos + Fotos")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 60)

    # Coleta de todos os scrapers
    todas = []
    todas += scrape_pelando()
    todas += scrape_kabum()
    todas += scrape_pichau()
    todas += scrape_mercadolivre()
    todas += scrape_terabyte()
    todas += scrape_nuuvem()
    todas += scrape_promocao_ofertas()

    # Filtra inválidos e ordena por temperatura
    todas = [p for p in todas if p.get("titulo") and p.get("url")]
    todas.sort(key=lambda x: x.get("temp", 0), reverse=True)

    # Remove duplicatas por título
    vistos = set()
    unicas = []
    for p in todas:
        chave = p["titulo"].lower()[:40]
        if chave not in vistos:
            vistos.add(chave)
            unicas.append(p)

    print(f"\n📦 Total único encontrado: {len(unicas)} promoções\n")

    enviadas = 0
    for promo in unicas:
        hash_p = gerar_hash(promo)

        if ja_enviada(hash_p):
            print(f"  ⏭ Já enviada: {promo['titulo'][:50]}")
            continue

        tem_foto = "📸" if promo.get("foto") else "📝"
        print(f"\n{tem_foto} [{promo['fonte']}] {promo['titulo'][:55]}")

        ok = enviar_telegram(promo)

        if ok:
            marcar_enviada(promo, hash_p)
            enviadas += 1

        # Pausa entre envios — evita flood
        intervalo = random.randint(30, 60)
        print(f"  ⏳ Aguardando {intervalo}s...")
        time.sleep(intervalo)

        if enviadas >= 15:
            print("\n✅ Limite de 15 promoções por rodada atingido.")
            break

    print(f"\n{'='*60}")
    print(f"  ✅ Concluído! {enviadas} promoções enviadas.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
