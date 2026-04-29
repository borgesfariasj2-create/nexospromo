"""
================================================================================
  NEXOS PROMO BOT v5
  - Fontes que funcionam no Railway (sem bloqueio de DNS)
  - Supabase corrigido para bloquear duplicatas
  - Foto nas mensagens
  - Mercado Livre, KaBuM API, Pichau API, Pelando API (GraphQL direto)
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
    "Accept": "application/json, text/html, */*",
}


# ══════════════════════════════════════════════════════════════════════════════
#  SCRAPERS — Apenas APIs JSON que funcionam no Railway
# ══════════════════════════════════════════════════════════════════════════════

def scrape_kabum() -> list:
    """KaBuM via API REST pública — funciona no Railway."""
    promos = []
    try:
        print("[KABUM] Buscando ofertas...")
        cats = [
            "oferta-do-dia", "computadores", "hardware",
            "perifericos", "smartphones-tablets", "games",
            "monitores-e-tvs", "tv-e-video", "eletrodomesticos",
        ]
        for cat in cats:
            url  = (
                f"https://servicespub.prod.api.aws.grupokabum.com.br"
                f"/catalog/v2/products-by-category/{cat}"
                f"?page_number=1&page_size=12&is_off=true"
            )
            try:
                resp = requests.get(url, headers=HEADERS, timeout=10)
                if resp.status_code != 200:
                    continue
                data = resp.json()
            except Exception:
                continue

            for item in data.get("data", []):
                nome     = item.get("name", "")
                preco    = float(item.get("vlr_final") or item.get("price") or 0)
                preco_de = item.get("vlr_normal")
                slug     = item.get("path", "")
                # Foto — tenta diferentes campos da API
                foto = (item.get("img") or item.get("image") or
                        item.get("thumbnail") or item.get("foto") or "")
                href = f"https://www.kabum.com.br/produto/{slug}" if slug else ""
                desconto = None
                if preco_de and float(preco_de) > preco > 0:
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
            time.sleep(0.3)

        print(f"[KABUM] ✓ {len(promos)} ofertas")
    except Exception as e:
        print(f"[KABUM] Erro geral: {e}")
    return promos


def scrape_pichau() -> list:
    """Pichau via API REST — funciona no Railway."""
    promos = []
    try:
        print("[PICHAU] Buscando ofertas...")
        # Tenta endpoint de ofertas via API REST
        endpoints = [
            "https://www.pichau.com.br/api/pichau/getOffers",
            "https://www.pichau.com.br/api/catalog/category/ofertas?page=1&limit=20",
        ]
        for url in endpoints:
            try:
                resp = requests.get(url, headers=HEADERS, timeout=10)
                if resp.status_code != 200:
                    continue
                data  = resp.json()
                items = (data.get("data", {}).get("products", {}).get("items", [])
                         or data.get("products", [])
                         or data.get("items", []))
                for item in items[:20]:
                    nome     = item.get("name", "")
                    preco    = float(
                        item.get("price_range", {}).get("minimum_price", {})
                            .get("final_price", {}).get("value", 0) or
                        item.get("price", 0) or 0
                    )
                    preco_de_raw = (
                        item.get("price_range", {}).get("minimum_price", {})
                            .get("regular_price", {}).get("value") or
                        item.get("original_price")
                    )
                    url_key  = item.get("url_key", item.get("slug", ""))
                    href     = f"https://www.pichau.com.br/{url_key}" if url_key else ""
                    media    = item.get("media_gallery", [])
                    foto     = media[0].get("url", "") if media else item.get("image", "") or ""
                    desconto = None
                    if preco_de_raw and float(preco_de_raw) > preco > 0:
                        desconto = round((1 - preco / float(preco_de_raw)) * 100)
                    if not nome or not href:
                        continue
                    promos.append({
                        "fonte":    "Pichau",
                        "titulo":   nome[:80],
                        "preco":    round(preco, 2),
                        "preco_de": round(float(preco_de_raw), 2) if preco_de_raw else None,
                        "desconto": desconto,
                        "cupom":    "",
                        "url":      href,
                        "foto":     foto,
                        "loja":     "Pichau",
                        "temp":     90,
                    })
                if promos:
                    break
            except Exception:
                continue

        print(f"[PICHAU] ✓ {len(promos)} ofertas")
    except Exception as e:
        print(f"[PICHAU] Erro: {e}")
    return promos


def scrape_mercadolivre() -> list:
    """Mercado Livre — funciona no Railway."""
    promos = []
    try:
        print("[MERCADO LIVRE] Buscando ofertas...")
        # Usa API de busca do ML que funciona sem bloqueio
        categorias_ids = [
            ("MLB1051", "Celulares"),
            ("MLB1648", "Computadores"),
            ("MLB1000", "Eletrônicos"),
            ("MLB5726", "Eletrodomésticos"),
            ("MLB1246", "TV e Vídeo"),
            ("MLB1168", "Esportes"),
            ("MLB1459", "Beleza"),
            ("MLB1574", "Ferramentas"),
        ]
        for cat_id, cat_nome in categorias_ids[:5]:
            url = (
                f"https://api.mercadolibre.com/sites/MLB/search"
                f"?category={cat_id}&sort=price_asc&limit=10&offset=0"
                f"&attributes=id,title,price,original_price,thumbnail,permalink,seller"
            )
            try:
                resp = requests.get(url, headers=HEADERS, timeout=10)
                if resp.status_code != 200:
                    continue
                results = resp.json().get("results", [])
            except Exception:
                continue

            for item in results:
                preco    = float(item.get("price", 0) or 0)
                preco_de = item.get("original_price")
                titulo   = item.get("title", "")
                href     = item.get("permalink", "")
                foto     = item.get("thumbnail", "").replace("I.jpg", "O.jpg")  # imagem maior
                desconto = None
                if preco_de and float(preco_de) > preco > 0:
                    desconto = round((1 - preco / float(preco_de)) * 100)
                # Só manda se tiver desconto real
                if not desconto:
                    continue
                if ML_TAG and href:
                    sep  = "&" if "?" in href else "?"
                    href = f"{href}{sep}deal_print_id={ML_TAG}"
                if not titulo or not href:
                    continue
                promos.append({
                    "fonte":    "Mercado Livre",
                    "titulo":   titulo[:80],
                    "preco":    round(preco, 2),
                    "preco_de": round(float(preco_de), 2) if preco_de else None,
                    "desconto": desconto,
                    "cupom":    "",
                    "url":      href,
                    "foto":     foto,
                    "loja":     "Mercado Livre",
                    "temp":     92,
                })
            time.sleep(0.5)

        print(f"[MERCADO LIVRE] ✓ {len(promos)} ofertas com desconto")
    except Exception as e:
        print(f"[MERCADO LIVRE] Erro: {e}")
    return promos


def scrape_pelando() -> list:
    """Pelando via GraphQL — API que funciona no Railway."""
    promos = []
    try:
        print("[PELANDO] Buscando promoções...")
        url   = "https://www.pelando.com.br/api/graphql"
        query = {
            "operationName": "HotDeals",
            "query": """
            query HotDeals {
              hotDeals(page: 1, pageSize: 20) {
                edges {
                  node {
                    title price nextBestPrice url coupon
                    temperature imageUrl
                    merchant { name }
                  }
                }
              }
            }
            """,
            "variables": {}
        }
        resp = requests.post(
            url,
            json=query,
            headers={**HEADERS, "content-type": "application/json",
                     "origin": "https://www.pelando.com.br",
                     "referer": "https://www.pelando.com.br/"},
            timeout=15
        )
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


def scrape_shopee() -> list:
    """Shopee via API pública de flash sale."""
    promos = []
    try:
        print("[SHOPEE] Buscando flash sales...")
        url  = "https://shopee.com.br/api/v4/flash_sale/get_all_sessions?need_main_image=true"
        resp = requests.get(
            url,
            headers={**HEADERS, "referer": "https://shopee.com.br/"},
            timeout=15
        )
        if resp.status_code == 200:
            sessions = resp.json().get("data", {}).get("sessions", [])
            for session in sessions[:2]:
                for item in session.get("items", [])[:10]:
                    nome     = item.get("name", "")
                    preco    = item.get("price", 0) / 100000
                    preco_de = item.get("price_before_discount", 0) / 100000
                    itemid   = item.get("itemid", "")
                    shopid   = item.get("shopid", "")
                    href     = f"https://shopee.com.br/product/{shopid}/{itemid}"
                    # Foto
                    img_id   = item.get("image", "")
                    foto     = f"https://cf.shopee.com.br/file/{img_id}" if img_id else ""
                    desconto = None
                    if preco_de > preco > 0:
                        desconto = round((1 - preco / preco_de) * 100)
                    if not nome:
                        continue
                    promos.append({
                        "fonte":    "Shopee",
                        "titulo":   nome[:80],
                        "preco":    round(preco, 2),
                        "preco_de": round(preco_de, 2) if preco_de else None,
                        "desconto": desconto,
                        "cupom":    "",
                        "url":      href,
                        "foto":     foto,
                        "loja":     "Shopee",
                        "temp":     88,
                    })
        print(f"[SHOPEE] ✓ {len(promos)} flash sales")
    except Exception as e:
        print(f"[SHOPEE] Erro: {e}")
    return promos


# ══════════════════════════════════════════════════════════════════════════════
#  AFILIADO
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
#  FORMATAÇÃO
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
        "Pelando":       "🔥",
        "KaBuM":         "💻",
        "Pichau":        "🖥️",
        "Mercado Livre": "🛒",
        "Shopee":        "🧡",
        "Amazon":        "📦",
    }
    emoji = emojis.get(fonte, "🏷️")

    msg = f"{emoji} *{titulo}*\n\n"

    if preco:
        pf   = f"R$ {preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        msg += f"💰 *Por apenas {pf}*\n"

    if preco_de and desconto:
        df   = f"R$ {preco_de:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
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
#  ENVIO TELEGRAM COM FOTO
# ══════════════════════════════════════════════════════════════════════════════

def enviar_telegram(promo: dict) -> bool:
    if not TELEGRAM_TOKEN:
        return False

    mensagem = formatar_mensagem(promo)
    foto     = promo.get("foto", "")

    try:
        if foto and foto.startswith("http"):
            resp = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
                json={
                    "chat_id":    TELEGRAM_CHAT_ID,
                    "photo":      foto,
                    "caption":    mensagem,
                    "parse_mode": "Markdown",
                },
                timeout=15
            )
            if resp.status_code == 200:
                print("  [TELEGRAM] ✓ Enviado com foto!")
                return True
            print(f"  [TELEGRAM] Foto falhou, enviando texto...")

        # Fallback: só texto
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id":                  TELEGRAM_CHAT_ID,
                "text":                     mensagem,
                "parse_mode":               "Markdown",
                "disable_web_page_preview": False,
            },
            timeout=15
        )
        if resp.status_code == 200:
            print("  [TELEGRAM] ✓ Enviado!")
            return True

        print(f"  [TELEGRAM] Erro {resp.status_code}: {resp.text[:200]}")
        return False

    except Exception as e:
        print(f"  [TELEGRAM] Erro: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  SUPABASE — CONTROLE DE DUPLICATAS CORRIGIDO
# ══════════════════════════════════════════════════════════════════════════════

def gerar_hash(promo: dict) -> str:
    chave = f"{promo.get('titulo','').lower().strip()[:50]}"
    return hashlib.md5(chave.encode()).hexdigest()


def ja_enviada(hash_promo: str) -> bool:
    """Verifica no Supabase se já enviou hoje."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False
    try:
        hoje = datetime.now().strftime("%Y-%m-%d")
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/promos_enviadas",
            params={
                "hash": f"eq.{hash_promo}",
                "data": f"eq.{hoje}",
                "select": "id",
            },
            headers={
                "apikey":        SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Accept":        "application/json",
            },
            timeout=10
        )
        resultado = resp.json()
        return isinstance(resultado, list) and len(resultado) > 0
    except Exception as e:
        print(f"  [DB] Erro ao verificar: {e}")
        return False  # Se der erro, tenta enviar mesmo assim


def marcar_enviada(promo: dict, hash_promo: str):
    """Salva no Supabase para não mandar duplicata."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    try:
        hoje = datetime.now().strftime("%Y-%m-%d")
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/promos_enviadas",
            json={
                "hash":   hash_promo,
                "titulo": promo.get("titulo", "")[:100],
                "fonte":  promo.get("fonte", ""),
                "preco":  promo.get("preco"),
                "data":   hoje,
            },
            headers={
                "apikey":        SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type":  "application/json",
                "Prefer":        "return=minimal",
            },
            timeout=10
        )
        if resp.status_code in (200, 201):
            print(f"  [DB] ✓ Salvo no Supabase")
        else:
            print(f"  [DB] Erro {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        print(f"  [DB] Erro ao salvar: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  NEXOS PROMO BOT v5")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Supabase: {'✓ conectado' if SUPABASE_URL else '✗ não configurado'}")
    print("=" * 60)

    # Coleta todas as fontes
    todas = []
    todas += scrape_pelando()
    todas += scrape_kabum()
    todas += scrape_pichau()
    todas += scrape_mercadolivre()
    todas += scrape_shopee()

    # Filtra inválidos
    todas = [p for p in todas if p.get("titulo") and p.get("url")]

    # Remove duplicatas por título (local, antes de checar Supabase)
    vistos = set()
    unicas = []
    for p in todas:
        chave = p["titulo"].lower().strip()[:50]
        if chave not in vistos:
            vistos.add(chave)
            unicas.append(p)

    # Ordena por temperatura
    unicas.sort(key=lambda x: x.get("temp", 0), reverse=True)

    print(f"\n📦 Total único encontrado: {len(unicas)} promoções\n")

    if not unicas:
        print("⚠️ Nenhuma promoção encontrada. Encerrando.")
        return

    enviadas = 0
    for promo in unicas:
        hash_p = gerar_hash(promo)

        # Checa Supabase
        if ja_enviada(hash_p):
            print(f"  ⏭ Já enviada hoje: {promo['titulo'][:50]}")
            continue

        tem_foto = "📸" if promo.get("foto") else "📝"
        print(f"\n{tem_foto} [{promo['fonte']}] {promo['titulo'][:55]}")

        ok = enviar_telegram(promo)

        if ok:
            marcar_enviada(promo, hash_p)
            enviadas += 1

        intervalo = random.randint(30, 60)
        print(f"  ⏳ Aguardando {intervalo}s...")
        time.sleep(intervalo)

        if enviadas >= 15:
            print("\n✅ Limite de 15 por rodada atingido.")
            break

    print(f"\n{'='*60}")
    print(f"  ✅ Concluído! {enviadas} promoções enviadas.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
