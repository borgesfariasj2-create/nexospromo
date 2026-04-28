"""
================================================================================
  NEXOS PROMO BOT v3 — Foco em Eletrônicos
  Amazon TAG: 20070b1-20
  Hospede no Railway (railway.app) — grátis
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
EVOLUTION_URL    = os.getenv("EVOLUTION_URL", "")
EVOLUTION_KEY    = os.getenv("EVOLUTION_KEY", "")
WHATSAPP_NUMBER  = os.getenv("WHATSAPP_NUMBER", "")
SUPABASE_URL     = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY     = os.getenv("SUPABASE_KEY", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

PALAVRAS_ELETRONICOS = [
    "notebook","laptop","celular","smartphone","iphone","samsung","xiaomi",
    "tablet","ipad","monitor","tv","televisão","smart tv","led","oled",
    "placa de vídeo","gpu","processador","cpu","memória ram","ssd","hd",
    "headset","fone","headphone","mouse","teclado","webcam","câmera",
    "impressora","roteador","carregador","cabo","adaptador","videogame",
    "playstation","xbox","nintendo","controle","joystick","rtx","gtx",
    "ryzen","intel","amd","asus","lenovo","dell","hp","acer","lg","sony",
    "jbl","airpods","redmi","poco","realme","gabinete","fonte","cooler",
    "placa mãe","pendrive","power bank","smartwatch","drone","gopro",
    "ps5","ps4","series x","series s","kindle","echo","alexa","chromecast",
    "apple tv","fire stick","steam","epic","kabum","pichau","terabyte",
]

def eh_eletronico(titulo: str) -> bool:
    t = titulo.lower()
    return any(p in t for p in PALAVRAS_ELETRONICOS)

# ══════════════════════════════════════════════════════════════════════════════
#  SCRAPERS
# ══════════════════════════════════════════════════════════════════════════════

def scrape_kabum() -> list:
    promos = []
    try:
        print("[KABUM] Buscando ofertas...")
        endpoints = ["oferta-do-dia","computadores","hardware","perifericos","smartphones-tablets","games","monitores-e-tvs"]
        for cat in endpoints[:5]:
            url = (f"https://servicespub.prod.api.aws.grupokabum.com.br/catalog/v2/"
                   f"products-by-category/{cat}?page_number=1&page_size=8&is_off=true")
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue
            for item in resp.json().get("data", [])[:8]:
                nome     = item.get("name", "")
                preco    = float(item.get("vlr_final", item.get("price", 0)))
                preco_de = item.get("vlr_normal")
                slug     = item.get("path", "")
                href     = f"https://www.kabum.com.br/produto/{slug}" if slug else ""
                desconto = None
                if preco_de and float(preco_de) > preco:
                    desconto = round((1 - preco / float(preco_de)) * 100)
                promos.append({"fonte":"KaBuM","titulo":nome[:80],"preco":round(preco,2),
                    "preco_de":round(float(preco_de),2) if preco_de else None,
                    "desconto":desconto,"cupom":"","url":href,"loja":"KaBuM","temp":95})
            time.sleep(1)
        print(f"[KABUM] ✓ {len(promos)} ofertas")
    except Exception as e:
        print(f"[KABUM] Erro: {e}")
    return promos


def scrape_pichau() -> list:
    promos = []
    try:
        print("[PICHAU] Buscando ofertas...")
        url  = "https://www.pichau.com.br/api/pichau/getOffers"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            for item in resp.json().get("data",{}).get("products",{}).get("items",[])[:10]:
                nome     = item.get("name","")
                preco    = item.get("price_range",{}).get("minimum_price",{}).get("final_price",{}).get("value",0)
                preco_de = item.get("price_range",{}).get("minimum_price",{}).get("regular_price",{}).get("value")
                url_key  = item.get("url_key","")
                href     = f"https://www.pichau.com.br/{url_key}" if url_key else ""
                desconto = None
                if preco_de and float(preco_de) > float(preco):
                    desconto = round((1 - float(preco)/float(preco_de))*100)
                promos.append({"fonte":"Pichau","titulo":nome[:80],"preco":round(float(preco),2),
                    "preco_de":round(float(preco_de),2) if preco_de else None,
                    "desconto":desconto,"cupom":"","url":href,"loja":"Pichau","temp":90})
        print(f"[PICHAU] ✓ {len(promos)} ofertas")
    except Exception as e:
        print(f"[PICHAU] Erro: {e}")
    return promos


def scrape_amazon() -> list:
    promos = []
    try:
        print("[AMAZON] Buscando ofertas de eletrônicos...")
        urls = [
            f"https://www.amazon.com.br/b?node=16243814011&tag={AMAZON_TAG}",  # Eletrônicos
            f"https://www.amazon.com.br/b?node=16209062011&tag={AMAZON_TAG}",  # Informática
            f"https://www.amazon.com.br/b?node=3413748011&tag={AMAZON_TAG}",   # Games
        ]
        for url in urls:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.select("[data-component-type='s-search-result']")[:8]
            for item in items:
                titulo = item.select_one("h2 .a-text-normal, h2 a span")
                preco  = item.select_one(".a-price .a-offscreen")
                link   = item.select_one("h2 a")
                if not titulo or not link:
                    continue
                titulo_txt = titulo.text.strip()
                if not eh_eletronico(titulo_txt):
                    continue
                href = "https://www.amazon.com.br" + link.get("href","")
                href = adicionar_tag_amazon(href, AMAZON_TAG)
                preco_val = None
                if preco:
                    nums = re.findall(r"[\d.,]+", preco.text)
                    if nums:
                        try: preco_val = float(nums[0].replace(".","").replace(",","."))
                        except: pass
                promos.append({"fonte":"Amazon","titulo":titulo_txt[:80],"preco":preco_val,
                    "cupom":"","url":href,"loja":"Amazon","temp":100})
            time.sleep(2)
        print(f"[AMAZON] ✓ {len(promos)} ofertas")
    except Exception as e:
        print(f"[AMAZON] Erro: {e}")
    return promos


def scrape_mercadolivre() -> list:
    promos = []
    try:
        print("[MERCADO LIVRE] Buscando eletrônicos...")
        cats = ["eletronicos","informatica","celulares-smartphones","games-consoles","televisores"]
        for cat in cats[:3]:
            url  = f"https://www.mercadolivre.com.br/ofertas/categoria/{cat}"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(resp.text, "html.parser")
            for item in soup.select(".promotion-item, .poly-card")[:8]:
                titulo = item.select_one(".promotion-item__title, .poly-component__title, h2")
                preco  = item.select_one(".promotion-item__price, .andes-money-amount__fraction")
                link   = item.select_one("a")
                if not titulo or not link: continue
                href = link.get("href","")
                if ML_TAG and href:
                    sep = "&" if "?" in href else "?"
                    href = f"{href}{sep}deal_print_id={ML_TAG}"
                preco_val = None
                if preco:
                    nums = re.findall(r"[\d.,]+", preco.text)
                    if nums:
                        try: preco_val = float(nums[0].replace(".","").replace(",","."))
                        except: pass
                promos.append({"fonte":"Mercado Livre","titulo":titulo.text.strip()[:80],
                    "preco":preco_val,"cupom":"","url":href,"loja":"Mercado Livre","temp":92})
            time.sleep(1)
        print(f"[MERCADO LIVRE] ✓ {len(promos)} ofertas")
    except Exception as e:
        print(f"[MERCADO LIVRE] Erro: {e}")
    return promos


def scrape_terabyte() -> list:
    promos = []
    try:
        print("[TERABYTE] Buscando ofertas...")
        url  = "https://www.terabyteshop.com.br/promocoes"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        for item in soup.select(".prd-bloco, .product-item")[:10]:
            titulo = item.select_one("h2, h3, .prd-nome")
            preco  = item.select_one(".prd-preco, [class*='price']")
            link   = item.select_one("a")
            if not titulo or not link: continue
            href = link.get("href","")
            if not href.startswith("http"): href = "https://www.terabyteshop.com.br" + href
            preco_val = None
            if preco:
                nums = re.findall(r"[\d.,]+", preco.text)
                if nums:
                    try: preco_val = float(nums[0].replace(".","").replace(",","."))
                    except: pass
            promos.append({"fonte":"Terabyte","titulo":titulo.text.strip()[:80],
                "preco":preco_val,"cupom":"","url":href,"loja":"Terabyte","temp":85})
        print(f"[TERABYTE] ✓ {len(promos)} ofertas")
    except Exception as e:
        print(f"[TERABYTE] Erro: {e}")
    return promos


def scrape_nuuvem() -> list:
    promos = []
    try:
        print("[NUUVEM] Buscando jogos em promoção...")
        url  = "https://www.nuuvem.com/br-pt/catalog/page/1/filter/discounted/sort/discount"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        for item in soup.select(".product-card, [class*='product-item']")[:10]:
            titulo   = item.select_one("h3, h2, .product-title")
            preco    = item.select_one(".product-price--final, [class*='price']")
            desconto = item.select_one(".discount-tag, [class*='discount']")
            link     = item.select_one("a")
            if not titulo or not link: continue
            href = link.get("href","")
            if not href.startswith("http"): href = "https://www.nuuvem.com" + href
            preco_val = None
            if preco:
                nums = re.findall(r"[\d.,]+", preco.text)
                if nums:
                    try: preco_val = float(nums[0].replace(".","").replace(",","."))
                    except: pass
            desc_val = None
            if desconto:
                nums = re.findall(r"\d+", desconto.text)
                if nums: desc_val = int(nums[0])
            promos.append({"fonte":"Nuuvem","titulo":titulo.text.strip()[:80],
                "preco":preco_val,"desconto":desc_val,"cupom":"","url":href,"loja":"Nuuvem","temp":82})
        print(f"[NUUVEM] ✓ {len(promos)} jogos")
    except Exception as e:
        print(f"[NUUVEM] Erro: {e}")
    return promos


def scrape_pelando_eletronicos() -> list:
    promos = []
    try:
        print("[PELANDO] Buscando eletrônicos...")
        url = "https://www.pelando.com.br/api/graphql"
        for cat in ["eletronicos","informatica","games","smartphones"]:
            query = {"query": f"""query {{
              hotDeals(page:1,pageSize:8,category:"{cat}") {{
                edges {{ node {{
                  title price nextBestPrice url coupon temperature
                  merchant {{ name }}
                }} }}
              }}
            }}"""}
            resp = requests.post(url, json=query, headers=HEADERS, timeout=15)
            if resp.status_code != 200: continue
            for edge in resp.json().get("data",{}).get("hotDeals",{}).get("edges",[]):
                node     = edge.get("node",{})
                preco    = node.get("price")
                preco_de = node.get("nextBestPrice")
                if not preco: continue
                desconto = None
                if preco_de and preco_de > preco:
                    desconto = round((1 - preco/preco_de)*100)
                promos.append({"fonte":"Pelando","titulo":node.get("title","")[:80],
                    "preco":preco,"preco_de":preco_de,"desconto":desconto,
                    "loja":node.get("merchant",{}).get("name",""),
                    "cupom":node.get("coupon",""),"url":node.get("url",""),
                    "temp":node.get("temperature",0)})
            time.sleep(1)
        print(f"[PELANDO] ✓ {len(promos)} eletrônicos")
    except Exception as e:
        print(f"[PELANDO] Erro: {e}")
    return promos


def scrape_shopee_eletronicos() -> list:
    promos = []
    try:
        print("[SHOPEE] Buscando eletrônicos...")
        url  = ("https://shopee.com.br/api/v4/search/search_items"
                "?by=sales&limit=10&newest=0&order=desc&page_type=search"
                "&version=2&keyword=eletronicos")
        resp = requests.get(url, headers={**HEADERS,"referer":"https://shopee.com.br"}, timeout=15)
        if resp.status_code == 200:
            for item in resp.json().get("items",[])[:10]:
                info     = item.get("item_basic", item)
                nome     = info.get("name","")
                if not eh_eletronico(nome): continue
                preco    = info.get("price",0)/100000
                preco_de = info.get("price_before_discount",0)/100000
                itemid   = info.get("itemid","")
                shopid   = info.get("shopid","")
                href     = f"https://shopee.com.br/product/{shopid}/{itemid}"
                desconto = None
                if preco_de > preco > 0:
                    desconto = round((1-preco/preco_de)*100)
                promos.append({"fonte":"Shopee","titulo":nome[:80],"preco":round(preco,2),
                    "preco_de":round(preco_de,2) if preco_de else None,
                    "desconto":desconto,"cupom":"","url":href,"loja":"Shopee","temp":88})
        print(f"[SHOPEE] ✓ {len(promos)} eletrônicos")
    except Exception as e:
        print(f"[SHOPEE] Erro: {e}")
    return promos


# ══════════════════════════════════════════════════════════════════════════════
#  AFILIADOS
# ══════════════════════════════════════════════════════════════════════════════

def adicionar_tag_amazon(url: str, tag: str) -> str:
    if "tag=" in url:
        return re.sub(r"tag=[^&]+", f"tag={tag}", url)
    return f"{url}&tag={tag}" if "?" in url else f"{url}?tag={tag}"


def gerar_link_afiliado(promo: dict) -> str:
    url   = promo.get("url","")
    fonte = promo.get("fonte","")
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
    titulo   = promo.get("titulo","Promoção")[:80]
    preco    = promo.get("preco")
    preco_de = promo.get("preco_de")
    desconto = promo.get("desconto")
    loja     = promo.get("loja", promo.get("fonte",""))
    cupom    = promo.get("cupom","")
    url      = gerar_link_afiliado(promo)
    fonte    = promo.get("fonte","")

    emojis = {"Amazon":"📦","Mercado Livre":"🛒","Pelando":"🔥","Shopee":"🧡",
               "KaBuM":"💻","Pichau":"🖥️","Terabyte":"⚡","Nuuvem":"🎮"}
    emoji = emojis.get(fonte,"🏷️")

    msg = f"{emoji} *{titulo}*\n\n"
    if preco:
        pf = f"R$ {preco:,.2f}".replace(",","X").replace(".",",").replace("X",".")
        msg += f"💰 *Por apenas {pf}*\n"
    if preco_de and desconto:
        df = f"R$ {preco_de:,.2f}".replace(",","X").replace(".",",").replace("X",".")
        msg += f"~~De {df}~~ → *{desconto}% OFF* 🔥\n"
    if loja:
        msg += f"🏪 Loja: {loja}\n"
    if cupom:
        msg += f"\n🎟️ *CUPOM:* `{cupom}`\n"
    msg += f"\n🔗 [PEGAR OFERTA AGORA]({url})\n"
    msg += f"\n_📢 @NexosPromoBot • {fonte}_"
    return msg


# ══════════════════════════════════════════════════════════════════════════════
#  ENVIO
# ══════════════════════════════════════════════════════════════════════════════

def enviar_telegram(mensagem: str) -> bool:
    if not TELEGRAM_TOKEN:
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id":TELEGRAM_CHAT_ID,"text":mensagem,
                  "parse_mode":"Markdown","disable_web_page_preview":False},
            timeout=15)
        if resp.status_code == 200:
            print("  [TELEGRAM] ✓ Enviado!")
            return True
        print(f"  [TELEGRAM] Erro {resp.status_code}: {resp.text}")
        return False
    except Exception as e:
        print(f"  [TELEGRAM] Erro: {e}")
        return False


def enviar_whatsapp(mensagem: str) -> bool:
    if not EVOLUTION_URL or not EVOLUTION_KEY or not WHATSAPP_NUMBER:
        return False
    try:
        msg_wp = mensagem.replace("*","").replace("~~","").replace("`","")
        resp   = requests.post(f"{EVOLUTION_URL}/message/sendText/nexos",
            json={"number":WHATSAPP_NUMBER,"text":msg_wp,"delay":1000},
            headers={"apikey":EVOLUTION_KEY,"Content-Type":"application/json"},
            timeout=15)
        if resp.status_code in (200,201):
            print("  [WHATSAPP] ✓ Enviado!")
            return True
        return False
    except Exception as e:
        print(f"  [WHATSAPP] Erro: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  DUPLICATAS
# ══════════════════════════════════════════════════════════════════════════════

def gerar_hash(promo: dict) -> str:
    chave = f"{promo.get('titulo','')}{promo.get('preco','')}{promo.get('url','')}"
    return hashlib.md5(chave.encode()).hexdigest()

def ja_enviada(hash_promo: str) -> bool:
    if not SUPABASE_URL or not SUPABASE_KEY: return False
    try:
        hoje = datetime.now().strftime("%Y-%m-%d")
        resp = requests.get(f"{SUPABASE_URL}/rest/v1/promos_enviadas",
            params={"hash":f"eq.{hash_promo}","data":f"eq.{hoje}"},
            headers={"apikey":SUPABASE_KEY,"Authorization":f"Bearer {SUPABASE_KEY}"},
            timeout=10)
        return len(resp.json()) > 0
    except: return False

def marcar_enviada(promo: dict, hash_promo: str):
    if not SUPABASE_URL or not SUPABASE_KEY: return
    try:
        requests.post(f"{SUPABASE_URL}/rest/v1/promos_enviadas",
            json={"hash":hash_promo,"titulo":promo.get("titulo","")[:100],
                  "fonte":promo.get("fonte",""),"preco":promo.get("preco"),
                  "data":datetime.now().strftime("%Y-%m-%d")},
            headers={"apikey":SUPABASE_KEY,"Authorization":f"Bearer {SUPABASE_KEY}",
                     "Content-Type":"application/json","Prefer":"return=minimal"},
            timeout=10)
    except Exception as e:
        print(f"  [DB] Erro: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("="*60)
    print("  NEXOS PROMO BOT v3 — Eletrônicos")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Amazon TAG: {AMAZON_TAG}")
    print("="*60)

    todas = []
    todas += scrape_pelando_eletronicos()
    todas += scrape_kabum()
    todas += scrape_pichau()
    todas += scrape_amazon()
    todas += scrape_mercadolivre()
    todas += scrape_shopee_eletronicos()
    todas += scrape_terabyte()
    todas += scrape_nuuvem()

    todas = [p for p in todas if p.get("titulo") and p.get("url")]
    todas.sort(key=lambda x: x.get("temp",0), reverse=True)

    print(f"\n📦 Total encontrado: {len(todas)} promoções\n")

    enviadas = 0
    for promo in todas:
        hash_p = gerar_hash(promo)
        if ja_enviada(hash_p):
            print(f"  ⏭ Já enviada: {promo['titulo'][:50]}")
            continue

        print(f"\n📢 [{promo['fonte']}] {promo['titulo'][:55]}")
        mensagem = formatar_mensagem(promo)

        ok_tg = enviar_telegram(mensagem)
        time.sleep(3)
        ok_wp = enviar_whatsapp(mensagem)

        if ok_tg or ok_wp:
            marcar_enviada(promo, hash_p)
            enviadas += 1

        intervalo = random.randint(45, 90)
        print(f"  ⏳ Aguardando {intervalo}s...")
        time.sleep(intervalo)

        if enviadas >= 10:
            print("\n✅ Limite de 10 promoções por rodada atingido.")
            break

    print(f"\n{'='*60}")
    print(f"  ✅ Concluído! {enviadas} promoções enviadas.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
