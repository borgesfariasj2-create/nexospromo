"""
================================================================================
  NEXOS PROMO BOT v7
  - Headers que bypassam bloqueio 403
  - Session com cookies para simular navegador real
  - Mercado Livre API oficial (funciona no Railway)
  - Pelando com headers corretos
  - KaBuM com endpoint atualizado
  - Email (Pichau, Terabyte, etc)
================================================================================
"""

import os
import re
import time
import email
import imaplib
import random
import hashlib
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from email.header import decode_header

# ── Configurações ──────────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003723940229")
AMAZON_TAG       = os.getenv("AMAZON_TAG", "20070b1-20")
ML_TAG           = os.getenv("ML_TAG", "")
SUPABASE_URL     = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY     = os.getenv("SUPABASE_KEY", "")
GMAIL_USER       = os.getenv("GMAIL_USER", "codenexobr@gmail.com")
GMAIL_PASS       = os.getenv("GMAIL_PASS", "qmeffbqmakyljxhm")

# ── Headers realistas por site ─────────────────────────────────────────────────
def get_session(referer: str = "") -> requests.Session:
    """Cria sessão com headers que imitam Chrome real."""
    s = requests.Session()
    s.headers.update({
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection":      "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest":  "document",
        "Sec-Fetch-Mode":  "navigate",
        "Sec-Fetch-Site":  "none",
        "Sec-Fetch-User":  "?1",
        "Cache-Control":   "max-age=0",
    })
    if referer:
        s.headers.update({"Referer": referer})
    return s

REMETENTES_LOJAS = [
    "pichau", "terabyte", "kabum", "magazineluiza", "magalu",
    "casasbahia", "americanas", "submarino", "shoptime",
    "extra", "pontofrio", "fastshop", "amazon", "shopee",
]

# ══════════════════════════════════════════════════════════════════════════════
#  LEITOR DE EMAIL
# ══════════════════════════════════════════════════════════════════════════════

def decodificar_assunto(assunto_raw) -> str:
    partes  = decode_header(assunto_raw)
    assunto = ""
    for parte, enc in partes:
        if isinstance(parte, bytes):
            assunto += parte.decode(enc or "utf-8", errors="ignore")
        else:
            assunto += parte
    return assunto.strip()


def extrair_promos_do_email(html_body: str, remetente: str) -> list:
    promos = []
    try:
        soup = BeautifulSoup(html_body, "html.parser")
        loja = "Newsletter"
        for nome in REMETENTES_LOJAS:
            if nome in remetente.lower():
                loja = nome.title()
                break

        links = soup.find_all("a", href=True)
        ignorar = ["unsubscribe","descadastrar","cancelar","privacidade",
                   "clique aqui","ver mais","saiba mais","comprar","acesse",
                   "confira","newsletter","logo","banner","header","footer"]

        for link in links:
            href = link.get("href", "")
            if not href or len(href) < 20:
                continue
            if any(x in href.lower() for x in ["unsubscribe","descadastrar","mailto"]):
                continue

            img  = link.find("img")
            foto = ""
            if img:
                foto = img.get("src", img.get("data-src", "")) or ""
                try:
                    w = int(str(img.get("width","200")).replace("px",""))
                    if w < 80:
                        foto = ""
                except:
                    pass

            parent      = link.parent or link
            texto_bloco = parent.get_text(" ", strip=True)

            precos    = re.findall(r"R\$\s*[\d.,]+", texto_bloco)
            preco_val = None
            if precos:
                try:
                    num       = re.findall(r"[\d.,]+", precos[0])[0]
                    preco_val = float(num.replace(".", "").replace(",", "."))
                except:
                    pass

            titulo = ""
            if img:
                titulo = img.get("alt", "").strip()
            if not titulo or len(titulo) < 5:
                titulo = link.get_text(" ", strip=True)[:80]
            if not titulo or len(titulo) < 8:
                continue
            if any(x in titulo.lower() for x in ignorar):
                continue

            cupom = ""
            match = re.search(
                r"(?:cupom|código|code|coupon)[:\s]+([A-Z0-9]{4,20})",
                soup.get_text(), re.IGNORECASE
            )
            if match:
                cupom = match.group(1).upper()

            promos.append({
                "fonte":  f"Email ({loja})",
                "titulo": titulo[:80],
                "preco":  preco_val,
                "cupom":  cupom,
                "url":    href,
                "foto":   foto if foto.startswith("http") else "",
                "loja":   loja,
                "temp":   100,
            })

        urls_vistos = set()
        unicas      = []
        for p in promos:
            if p["url"] not in urls_vistos and p.get("titulo"):
                urls_vistos.add(p["url"])
                unicas.append(p)
        return unicas[:5]

    except Exception as e:
        print(f"  [EMAIL PARSER] Erro: {e}")
        return []


def scrape_email() -> list:
    promos = []
    try:
        print("[EMAIL] Conectando ao Gmail...")
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_PASS)
        mail.select("inbox")

        data_busca = (datetime.now() - timedelta(days=2)).strftime("%d-%b-%Y")
        _, ids     = mail.search(None, f'(UNSEEN SINCE "{data_busca}")')
        email_ids  = ids[0].split()
        print(f"[EMAIL] {len(email_ids)} emails não lidos")

        for eid in email_ids[-20:]:
            try:
                _, msg_data = mail.fetch(eid, "(RFC822)")
                msg         = email.message_from_bytes(msg_data[0][1])
                remetente   = msg.get("From", "")
                assunto     = decodificar_assunto(msg.get("Subject", ""))

                if not any(l in remetente.lower() for l in REMETENTES_LOJAS):
                    continue

                print(f"  [EMAIL] {assunto[:50]} | {remetente[:40]}")

                html_body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/html":
                            charset   = part.get_content_charset() or "utf-8"
                            html_body = part.get_payload(decode=True).decode(charset, errors="ignore")
                            break
                elif msg.get_content_type() == "text/html":
                    charset   = msg.get_content_charset() or "utf-8"
                    html_body = msg.get_payload(decode=True).decode(charset, errors="ignore")

                if not html_body:
                    continue

                promos_email = extrair_promos_do_email(html_body, remetente)
                print(f"  [EMAIL] {len(promos_email)} promos extraídas")
                promos += promos_email
                mail.store(eid, "+FLAGS", "\\Seen")

            except Exception as e:
                print(f"  [EMAIL] Erro: {e}")
                continue

        mail.logout()
        print(f"[EMAIL] ✓ {len(promos)} promos dos emails")

    except Exception as e:
        print(f"[EMAIL] Erro: {e}")
    return promos


# ══════════════════════════════════════════════════════════════════════════════
#  SCRAPER — MERCADO LIVRE (API oficial — funciona no Railway)
# ══════════════════════════════════════════════════════════════════════════════

def scrape_mercadolivre() -> list:
    promos = []
    try:
        print("[MERCADO LIVRE] Buscando ofertas...")
        s    = get_session("https://www.mercadolivre.com.br")
        cats = [
            "MLB1051",  # Celulares
            "MLB1648",  # Computadores
            "MLB1000",  # Eletrônicos
            "MLB5726",  # Eletrodomésticos
            "MLB1246",  # TV e Vídeo
            "MLB1168",  # Esportes
            "MLB1459",  # Beleza
            "MLB1144",  # Moda
            "MLB1276",  # Ferramentas
            "MLB1367",  # Casa e Jardim
        ]
        for cat_id in cats:
            try:
                url  = (f"https://api.mercadolibre.com/sites/MLB/search"
                        f"?category={cat_id}&sort=price_asc&limit=10"
                        f"&attributes=id,title,price,original_price,thumbnail,permalink")
                resp = s.get(url, timeout=10)
                if resp.status_code != 200:
                    continue
                for item in resp.json().get("results", []):
                    preco    = float(item.get("price", 0) or 0)
                    preco_de = item.get("original_price")
                    if not preco_de or float(preco_de) <= preco:
                        continue
                    desconto = round((1 - preco / float(preco_de)) * 100)
                    if desconto < 5:
                        continue
                    titulo = item.get("title", "")
                    href   = item.get("permalink", "")
                    foto   = item.get("thumbnail", "").replace("I.jpg", "O.jpg")
                    if ML_TAG and href:
                        sep  = "&" if "?" in href else "?"
                        href = f"{href}{sep}deal_print_id={ML_TAG}"
                    if not titulo or not href:
                        continue
                    promos.append({
                        "fonte":    "Mercado Livre",
                        "titulo":   titulo[:80],
                        "preco":    round(preco, 2),
                        "preco_de": round(float(preco_de), 2),
                        "desconto": desconto,
                        "cupom":    "",
                        "url":      href,
                        "foto":     foto,
                        "loja":     "Mercado Livre",
                        "temp":     92,
                    })
                time.sleep(0.3)
            except Exception:
                continue

        print(f"[MERCADO LIVRE] ✓ {len(promos)} ofertas")
    except Exception as e:
        print(f"[MERCADO LIVRE] Erro: {e}")
    return promos


# ══════════════════════════════════════════════════════════════════════════════
#  SCRAPER — PELANDO (GraphQL com headers corretos)
# ══════════════════════════════════════════════════════════════════════════════

def scrape_pelando() -> list:
    promos = []
    try:
        print("[PELANDO] Buscando promoções...")
        s = get_session("https://www.pelando.com.br/")
        s.headers.update({
            "content-type": "application/json",
            "origin":       "https://www.pelando.com.br",
            "x-requested-with": "XMLHttpRequest",
        })

        # Primeiro acessa a home para pegar cookies
        try:
            s.get("https://www.pelando.com.br/", timeout=8)
            time.sleep(1)
        except:
            pass

        query = {
            "operationName": "HotDeals",
            "query": """query HotDeals {
              hotDeals(page: 1, pageSize: 20) {
                edges { node {
                  title price nextBestPrice url coupon
                  temperature imageUrl
                  merchant { name }
                }}
              }
            }""",
            "variables": {}
        }
        resp = s.post(
            "https://www.pelando.com.br/api/graphql",
            json=query,
            timeout=15
        )
        print(f"  [PELANDO] Status: {resp.status_code}")
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


# ══════════════════════════════════════════════════════════════════════════════
#  SCRAPER — KABUM (endpoint atualizado)
# ══════════════════════════════════════════════════════════════════════════════

def scrape_kabum() -> list:
    promos = []
    try:
        print("[KABUM] Buscando ofertas...")
        s = get_session("https://www.kabum.com.br/")

        # Tenta diferentes endpoints
        endpoints = [
            "https://servicespub.prod.api.aws.grupokabum.com.br/catalog/v2/products-by-category/oferta-do-dia?page_number=1&page_size=12&is_off=true",
            "https://servicespub.prod.api.aws.grupokabum.com.br/catalog/v1/products-by-category/oferta-do-dia?page_number=1&page_size=12&is_off=true",
            "https://www.kabum.com.br/api/catalog/products?sort=discount&limit=20&page=1",
        ]

        for url in endpoints:
            try:
                resp = s.get(url, timeout=10)
                print(f"  [KABUM] {url[-40:]} → {resp.status_code}")
                if resp.status_code != 200:
                    continue
                data  = resp.json()
                items = data.get("data", data.get("products", data.get("items", [])))
                if not items:
                    continue
                for item in items[:15]:
                    nome     = item.get("name", item.get("title", ""))
                    preco    = float(item.get("vlr_final", item.get("price", item.get("sale_price", 0))) or 0)
                    preco_de = item.get("vlr_normal", item.get("original_price"))
                    slug     = item.get("path", item.get("slug", item.get("url_key", "")))
                    foto     = (item.get("img") or item.get("image") or
                                item.get("thumbnail") or item.get("photo") or "")
                    href     = f"https://www.kabum.com.br/produto/{slug}" if slug else ""
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
                if promos:
                    break
            except Exception as e:
                print(f"  [KABUM] Endpoint falhou: {e}")
                continue

        print(f"[KABUM] ✓ {len(promos)} ofertas")
    except Exception as e:
        print(f"[KABUM] Erro: {e}")
    return promos


# ══════════════════════════════════════════════════════════════════════════════
#  SCRAPER — SHOPEE flash sale
# ══════════════════════════════════════════════════════════════════════════════

def scrape_shopee() -> list:
    promos = []
    try:
        print("[SHOPEE] Buscando flash sales...")
        s = get_session("https://shopee.com.br/")
        s.headers.update({"referer": "https://shopee.com.br/"})

        # Visita home primeiro para pegar cookies
        try:
            s.get("https://shopee.com.br/", timeout=8)
            time.sleep(1)
        except:
            pass

        resp = s.get(
            "https://shopee.com.br/api/v4/flash_sale/get_all_sessions?need_main_image=true",
            timeout=15
        )
        print(f"  [SHOPEE] Status: {resp.status_code}")
        if resp.status_code == 200:
            for session in resp.json().get("data", {}).get("sessions", [])[:2]:
                for item in session.get("items", [])[:10]:
                    nome     = item.get("name", "")
                    preco    = item.get("price", 0) / 100000
                    preco_de = item.get("price_before_discount", 0) / 100000
                    itemid   = item.get("itemid", "")
                    shopid   = item.get("shopid", "")
                    img_id   = item.get("image", "")
                    foto     = f"https://cf.shopee.com.br/file/{img_id}" if img_id else ""
                    href     = f"https://shopee.com.br/product/{shopid}/{itemid}"
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
#  FORMATAÇÃO E ENVIO
# ══════════════════════════════════════════════════════════════════════════════

def adicionar_tag_amazon(url: str, tag: str) -> str:
    if "tag=" in url:
        return re.sub(r"tag=[^&]+", f"tag={tag}", url)
    return f"{url}&tag={tag}" if "?" in url else f"{url}?tag={tag}"


def gerar_link_afiliado(promo: dict) -> str:
    url   = promo.get("url", "")
    fonte = promo.get("fonte", "")
    if "amazon" in fonte.lower() and AMAZON_TAG:
        return adicionar_tag_amazon(url, AMAZON_TAG)
    if fonte == "Mercado Livre" and ML_TAG:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}deal_print_id={ML_TAG}"
    return url


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
        "Pelando": "🔥", "KaBuM": "💻", "Mercado Livre": "🛒",
        "Shopee": "🧡", "Amazon": "📦",
    }
    emoji = emojis.get(fonte, "📧" if "Email" in fonte else "🏷️")

    msg  = f"{emoji} *{titulo}*\n\n"
    if preco:
        pf   = f"R$ {preco:,.2f}".replace(",","X").replace(".",",").replace("X",".")
        msg += f"💰 *Por apenas {pf}*\n"
    if preco_de and desconto:
        df   = f"R$ {preco_de:,.2f}".replace(",","X").replace(".",",").replace("X",".")
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


def enviar_telegram(promo: dict) -> bool:
    if not TELEGRAM_TOKEN:
        return False
    mensagem = formatar_mensagem(promo)
    foto     = promo.get("foto", "")
    try:
        if foto and foto.startswith("http"):
            resp = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
                json={"chat_id": TELEGRAM_CHAT_ID, "photo": foto,
                      "caption": mensagem, "parse_mode": "Markdown"},
                timeout=15
            )
            if resp.status_code == 200:
                print("  [TELEGRAM] ✓ Enviado com foto!")
                return True
            print(f"  [TELEGRAM] Foto falhou ({resp.status_code}), tentando texto...")

        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": mensagem,
                  "parse_mode": "Markdown", "disable_web_page_preview": False},
            timeout=15
        )
        if resp.status_code == 200:
            print("  [TELEGRAM] ✓ Enviado!")
            return True
        print(f"  [TELEGRAM] Erro {resp.status_code}: {resp.text[:100]}")
        return False
    except Exception as e:
        print(f"  [TELEGRAM] Erro: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  SUPABASE
# ══════════════════════════════════════════════════════════════════════════════

def gerar_hash(promo: dict) -> str:
    chave = promo.get("titulo", "").lower().strip()[:50]
    return hashlib.md5(chave.encode()).hexdigest()


def ja_enviada(hash_promo: str) -> bool:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False
    try:
        hoje = datetime.now().strftime("%Y-%m-%d")
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/promos_enviadas",
            params={"hash": f"eq.{hash_promo}", "data": f"eq.{hoje}", "select": "id"},
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
            timeout=10
        )
        r = resp.json()
        return isinstance(r, list) and len(r) > 0
    except:
        return False


def marcar_enviada(promo: dict, hash_promo: str):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    try:
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/promos_enviadas",
            json={"hash": hash_promo, "titulo": promo.get("titulo","")[:100],
                  "fonte": promo.get("fonte",""), "preco": promo.get("preco"),
                  "data": datetime.now().strftime("%Y-%m-%d")},
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                     "Content-Type": "application/json", "Prefer": "return=minimal"},
            timeout=10
        )
        if resp.status_code in (200, 201):
            print("  [DB] ✓ Salvo")
        else:
            print(f"  [DB] Erro {resp.status_code}: {resp.text[:80]}")
    except Exception as e:
        print(f"  [DB] Erro: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  NEXOS PROMO BOT v7")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Gmail:    {GMAIL_USER}")
    print(f"  Supabase: {'✓' if SUPABASE_URL else '✗'}")
    print("=" * 60)

    todas  = []
    todas += scrape_email()
    todas += scrape_pelando()
    todas += scrape_kabum()
    todas += scrape_mercadolivre()
    todas += scrape_shopee()

    todas = [p for p in todas if p.get("titulo") and p.get("url")]

    # Dedup local
    vistos = set()
    unicas = []
    for p in todas:
        chave = p["titulo"].lower().strip()[:50]
        if chave not in vistos:
            vistos.add(chave)
            unicas.append(p)

    # Email primeiro, depois por temperatura
    unicas.sort(key=lambda x: (0 if "Email" in x.get("fonte","") else 1,
                                -x.get("temp", 0)))

    print(f"\n📦 Total único: {len(unicas)} promoções\n")

    if not unicas:
        print("⚠️ Nenhuma promoção encontrada.")
        return

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

        time.sleep(random.randint(30, 60))

        if enviadas >= 15:
            print("\n✅ Limite de 15 por rodada.")
            break

    print(f"\n{'='*60}")
    print(f"  ✅ Concluído! {enviadas} enviadas.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
