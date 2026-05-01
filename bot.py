"""
================================================================================
  NEXOS PROMO BOT v9
  - Shopee API Oficial de Afiliados (GraphQL)
  - KaBuM API
  - Mercado Livre API
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
import hmac
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from email.header import decode_header

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003723940229")
AMAZON_TAG       = os.getenv("AMAZON_TAG", "20070b1-20")
ML_TAG           = os.getenv("ML_TAG", "")
SUPABASE_URL     = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY     = os.getenv("SUPABASE_KEY", "")
GMAIL_USER       = os.getenv("GMAIL_USER", "codenexobr@gmail.com")
GMAIL_PASS       = os.getenv("GMAIL_PASS", "qmeffbqmakyljxhm")
SHOPEE_APP_ID    = os.getenv("SHOPEE_APP_ID", "18309950529")
SHOPEE_SECRET    = os.getenv("SHOPEE_SECRET", "R7UZKOUQQPY4WRXOPC2LZWLP6RBABLYP")

REMETENTES_LOJAS = [
    "pichau","terabyte","kabum","magazineluiza","magalu",
    "casasbahia","americanas","submarino","shoptime",
    "extra","pontofrio","fastshop","amazon","shopee",
]


# ══════════════════════════════════════════════════════════════════════════════
#  SHOPEE API OFICIAL — GraphQL com autenticação HMAC
# ══════════════════════════════════════════════════════════════════════════════

def gerar_assinatura_shopee(app_id: str, secret: str, payload: str) -> dict:
    """
    Gera headers de autenticação para a API da Shopee Afiliados.
    Usa HMAC-SHA256 conforme documentação oficial.
    """
    timestamp = str(int(datetime.now().timestamp()))
    nonce     = str(random.randint(100000, 999999))

    # String para assinar: appId + timestamp + nonce + payload
    msg_to_sign = f"{app_id}{timestamp}{nonce}{payload}"

    signature = hmac.new(
        secret.encode("utf-8"),
        msg_to_sign.encode("utf-8"),
        digestmod="sha256"
    ).hexdigest()

    return {
        "Content-Type":          "application/json",
        "Authorization":         f"SHA256 Credential={app_id}, Timestamp={timestamp}, Nonce={nonce}, Signature={signature}",
        "User-Agent":            "Mozilla/5.0",
    }


def scrape_shopee() -> list:
    """
    Busca ofertas via API GraphQL oficial da Shopee Afiliados.
    Retorna lista de promoções com link de afiliado já embutido.
    """
    promos = []
    try:
        print("[SHOPEE] Buscando ofertas via API oficial...")

        url = "https://open-api.affiliate.shopee.com.br/graphql"

        # Query GraphQL conforme documentação
        query = """
        query {
          shopeeOfferV2(
            sortType: 2
            page: 1
            limit: 20
          ) {
            nodes {
              offerName
              imageUrl
              offerLink
              originalLink
              commissionRate
              offerType
              periodStartTime
              periodEndTime
            }
            pageInfo {
              page
              limit
              hasNextPage
            }
          }
        }
        """

        payload = query.strip()
        headers = gerar_assinatura_shopee(SHOPEE_APP_ID, SHOPEE_SECRET, payload)

        resp = requests.post(
            url,
            json={"query": query},
            headers=headers,
            timeout=15
        )

        print(f"  [SHOPEE] Status: {resp.status_code}")

        if resp.status_code == 200:
            data  = resp.json()
            erros = data.get("errors")
            if erros:
                print(f"  [SHOPEE] Erros GraphQL: {erros}")

            nodes = (data.get("data", {})
                        .get("shopeeOfferV2", {})
                        .get("nodes", []))

            print(f"  [SHOPEE] {len(nodes)} ofertas recebidas")

            for node in nodes:
                nome     = node.get("offerName", "")
                foto     = node.get("imageUrl", "") or ""
                href     = node.get("offerLink", "") or ""   # link JÁ com afiliado
                comissao = node.get("commissionRate", "")
                if not nome or not href:
                    continue

                # Converte comissão para % legível
                desc_txt = ""
                try:
                    pct      = round(float(comissao) * 100, 1)
                    desc_txt = f"Comissão: {pct}%"
                except:
                    pass

                promos.append({
                    "fonte":    "Shopee",
                    "titulo":   nome[:80],
                    "preco":    None,
                    "preco_de": None,
                    "desconto": None,
                    "cupom":    "",
                    "url":      href,
                    "foto":     foto if foto.startswith("http") else "",
                    "loja":     "Shopee",
                    "temp":     95,
                    "extra":    desc_txt,
                })

        else:
            print(f"  [SHOPEE] Resposta: {resp.text[:200]}")

        print(f"[SHOPEE] ✓ {len(promos)} ofertas")
    except Exception as e:
        print(f"[SHOPEE] Erro: {e}")
    return promos


def scrape_shopee_produtos() -> list:
    """Busca produtos específicos via GetProductOfferList."""
    promos = []
    try:
        print("[SHOPEE PRODUTOS] Buscando produtos em promoção...")
        url   = "https://open-api.affiliate.shopee.com.br/graphql"
        query = """
        query {
          productOfferV2(
            sortType: 2
            page: 1
            limit: 20
          ) {
            nodes {
              productName
              imageUrl
              offerLink
              originalLink
              priceMin
              priceMax
              commissionRate
              sales
              ratingStar
            }
            pageInfo {
              hasNextPage
            }
          }
        }
        """
        payload = query.strip()
        headers = gerar_assinatura_shopee(SHOPEE_APP_ID, SHOPEE_SECRET, payload)
        resp    = requests.post(url, json={"query": query}, headers=headers, timeout=15)

        print(f"  [SHOPEE PRODUTOS] Status: {resp.status_code}")

        if resp.status_code == 200:
            data  = resp.json()
            nodes = (data.get("data", {})
                        .get("productOfferV2", {})
                        .get("nodes", []))

            for node in nodes:
                nome     = node.get("productName","")
                foto     = node.get("imageUrl","") or ""
                href     = node.get("offerLink","") or ""
                preco    = node.get("priceMin")
                comissao = node.get("commissionRate","")
                if not nome or not href: continue

                preco_val = None
                try:
                    preco_val = round(float(preco), 2) if preco else None
                except: pass

                promos.append({
                    "fonte":    "Shopee",
                    "titulo":   nome[:80],
                    "preco":    preco_val,
                    "preco_de": None,
                    "desconto": None,
                    "cupom":    "",
                    "url":      href,
                    "foto":     foto if foto.startswith("http") else "",
                    "loja":     "Shopee",
                    "temp":     90,
                    "extra":    "",
                })

        print(f"[SHOPEE PRODUTOS] ✓ {len(promos)} produtos")
    except Exception as e:
        print(f"[SHOPEE PRODUTOS] Erro: {e}")
    return promos


# ══════════════════════════════════════════════════════════════════════════════
#  EMAIL
# ══════════════════════════════════════════════════════════════════════════════

def decodificar_assunto(raw) -> str:
    partes  = decode_header(raw)
    assunto = ""
    for parte, enc in partes:
        if isinstance(parte, bytes):
            assunto += parte.decode(enc or "utf-8", errors="ignore")
        else:
            assunto += parte
    return assunto.strip()


def extrair_promos_do_email(html_body: str, remetente: str) -> list:
    promos  = []
    ignorar = ["unsubscribe","descadastrar","cancelar","privacidade",
               "ver mais","saiba mais","acesse","newsletter","logo","banner"]
    try:
        soup = BeautifulSoup(html_body, "html.parser")
        loja = "Newsletter"
        for nome in REMETENTES_LOJAS:
            if nome in remetente.lower():
                loja = nome.title()
                break

        urls_vistos = set()
        for link in soup.find_all("a", href=True):
            href = link.get("href","")
            if not href or len(href) < 20 or href in urls_vistos: continue
            if any(x in href.lower() for x in ["unsubscribe","descadastrar","mailto"]): continue
            urls_vistos.add(href)

            img  = link.find("img")
            foto = ""
            if img:
                foto = img.get("src", img.get("data-src","")) or ""
                try:
                    if int(str(img.get("width","200")).replace("px","")) < 80: foto = ""
                except: pass

            parent      = link.parent or link
            texto_bloco = parent.get_text(" ", strip=True)
            precos      = re.findall(r"R\$\s*[\d.,]+", texto_bloco)
            preco_val   = None
            if precos:
                try:
                    num       = re.findall(r"[\d.,]+", precos[0])[0]
                    preco_val = float(num.replace(".","").replace(",","."))
                except: pass

            titulo = ""
            if img: titulo = img.get("alt","").strip()
            if not titulo or len(titulo) < 5:
                titulo = link.get_text(" ", strip=True)[:80]
            if not titulo or len(titulo) < 8: continue
            if any(x in titulo.lower() for x in ignorar): continue

            cupom = ""
            match = re.search(r"(?:cupom|código|code|coupon)[:\s]+([A-Z0-9]{4,20})",
                               soup.get_text(), re.IGNORECASE)
            if match: cupom = match.group(1).upper()

            promos.append({
                "fonte": f"Email ({loja})", "titulo": titulo[:80],
                "preco": preco_val, "cupom": cupom, "url": href,
                "foto": foto if foto.startswith("http") else "",
                "loja": loja, "temp": 100, "extra": "",
            })
            if len(promos) >= 5: break
    except Exception as e:
        print(f"  [EMAIL PARSER] Erro: {e}")
    return promos


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
                remetente   = msg.get("From","")
                if not any(l in remetente.lower() for l in REMETENTES_LOJAS): continue
                assunto     = decodificar_assunto(msg.get("Subject",""))
                print(f"  [EMAIL] {assunto[:50]}")
                html_body   = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/html":
                            charset   = part.get_content_charset() or "utf-8"
                            html_body = part.get_payload(decode=True).decode(charset, errors="ignore")
                            break
                elif msg.get_content_type() == "text/html":
                    charset   = msg.get_content_charset() or "utf-8"
                    html_body = msg.get_payload(decode=True).decode(charset, errors="ignore")
                if html_body:
                    pe     = extrair_promos_do_email(html_body, remetente)
                    promos += pe
                    print(f"  [EMAIL] {len(pe)} promos extraídas")
                mail.store(eid, "+FLAGS", "\\Seen")
            except Exception as e:
                print(f"  [EMAIL] Erro: {e}")
        mail.logout()
        print(f"[EMAIL] ✓ {len(promos)} promos")
    except Exception as e:
        print(f"[EMAIL] Erro: {e}")
    return promos


# ══════════════════════════════════════════════════════════════════════════════
#  KABUM
# ══════════════════════════════════════════════════════════════════════════════

def scrape_kabum() -> list:
    promos = []
    try:
        print("[KABUM] Buscando ofertas...")
        s = requests.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            "Accept":     "application/json, text/plain, */*",
            "Origin":     "https://www.kabum.com.br",
            "Referer":    "https://www.kabum.com.br/",
        })
        cats = ["oferta-do-dia","computadores","hardware","perifericos",
                "smartphones-tablets","games","monitores-e-tvs"]
        for cat in cats:
            url = (f"https://servicespub.prod.api.aws.grupokabum.com.br"
                   f"/catalog/v2/products-by-category/{cat}"
                   f"?page_number=1&page_size=12&is_off=true&sort=0")
            try:
                resp = s.get(url, timeout=10)
                if resp.status_code != 200 or not resp.text.strip(): continue
                for item in resp.json().get("data",[]):
                    nome     = item.get("name","")
                    preco    = float(item.get("vlr_final") or item.get("price") or 0)
                    preco_de = item.get("vlr_normal")
                    slug     = item.get("path","")
                    foto     = item.get("img") or item.get("image") or item.get("thumbnail") or ""
                    href     = f"https://www.kabum.com.br/produto/{slug}" if slug else ""
                    desconto = None
                    if preco_de and float(preco_de) > preco > 0:
                        desconto = round((1 - preco/float(preco_de))*100)
                    if not nome or not href: continue
                    promos.append({
                        "fonte":"KaBuM","titulo":nome[:80],"preco":round(preco,2),
                        "preco_de":round(float(preco_de),2) if preco_de else None,
                        "desconto":desconto,"cupom":"","url":href,"foto":foto,
                        "loja":"KaBuM","temp":95,"extra":"",
                    })
                time.sleep(0.5)
            except: continue
        print(f"[KABUM] ✓ {len(promos)} ofertas")
    except Exception as e:
        print(f"[KABUM] Erro: {e}")
    return promos


# ══════════════════════════════════════════════════════════════════════════════
#  MERCADO LIVRE
# ══════════════════════════════════════════════════════════════════════════════

def scrape_mercadolivre() -> list:
    promos = []
    try:
        print("[MERCADO LIVRE] Buscando ofertas...")
        s = requests.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json",
        })
        urls = [
            "https://api.mercadolibre.com/sites/MLB/search?q=oferta&sort=relevance&limit=20&promotions=deal",
            "https://api.mercadolibre.com/sites/MLB/search?category=MLB1051&sort=relevance&limit=10&promotions=deal",
            "https://api.mercadolibre.com/sites/MLB/search?category=MLB1648&sort=relevance&limit=10&promotions=deal",
            "https://api.mercadolibre.com/sites/MLB/search?category=MLB1000&sort=relevance&limit=10&promotions=deal",
            "https://api.mercadolibre.com/sites/MLB/search?category=MLB5726&sort=relevance&limit=10&promotions=deal",
        ]
        for url in urls:
            try:
                resp = s.get(url, timeout=10)
                if resp.status_code != 200: continue
                for item in resp.json().get("results",[]):
                    preco    = float(item.get("price",0) or 0)
                    preco_de = item.get("original_price")
                    titulo   = item.get("title","")
                    href     = item.get("permalink","")
                    foto     = item.get("thumbnail","").replace("I.jpg","O.jpg")
                    if not titulo or not href or preco <= 0: continue
                    desconto = None
                    if preco_de and float(preco_de) > preco:
                        desconto = round((1-preco/float(preco_de))*100)
                    if ML_TAG and href:
                        sep  = "&" if "?" in href else "?"
                        href = f"{href}{sep}deal_print_id={ML_TAG}"
                    promos.append({
                        "fonte":"Mercado Livre","titulo":titulo[:80],"preco":round(preco,2),
                        "preco_de":round(float(preco_de),2) if preco_de else None,
                        "desconto":desconto,"cupom":"","url":href,"foto":foto,
                        "loja":"Mercado Livre","temp":92,"extra":"",
                    })
                time.sleep(0.3)
            except: continue
        print(f"[MERCADO LIVRE] ✓ {len(promos)} ofertas")
    except Exception as e:
        print(f"[MERCADO LIVRE] Erro: {e}")
    return promos


# ══════════════════════════════════════════════════════════════════════════════
#  FORMATAÇÃO E ENVIO
# ══════════════════════════════════════════════════════════════════════════════

def adicionar_tag_amazon(url: str, tag: str) -> str:
    if "tag=" in url: return re.sub(r"tag=[^&]+", f"tag={tag}", url)
    return f"{url}&tag={tag}" if "?" in url else f"{url}?tag={tag}"

def gerar_link_afiliado(promo: dict) -> str:
    url   = promo.get("url","")
    fonte = promo.get("fonte","")
    if "amazon" in fonte.lower() and AMAZON_TAG:
        return adicionar_tag_amazon(url, AMAZON_TAG)
    if fonte == "Mercado Livre" and ML_TAG:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}deal_print_id={ML_TAG}"
    return url  # Shopee já vem com link de afiliado da API


def formatar_mensagem(promo: dict) -> str:
    titulo   = promo.get("titulo","Promoção")[:80]
    preco    = promo.get("preco")
    preco_de = promo.get("preco_de")
    desconto = promo.get("desconto")
    loja     = promo.get("loja", promo.get("fonte",""))
    cupom    = promo.get("cupom","")
    extra    = promo.get("extra","")
    url      = gerar_link_afiliado(promo)
    fonte    = promo.get("fonte","")

    emojis = {"Mercado Livre":"🛒","KaBuM":"💻","Shopee":"🧡","Amazon":"📦","Promobit":"🔥"}
    emoji  = emojis.get(fonte, "📧" if "Email" in fonte else "🏷️")

    msg  = f"{emoji} *{titulo}*\n\n"
    if preco:
        pf   = f"R$ {preco:,.2f}".replace(",","X").replace(".",",").replace("X",".")
        msg += f"💰 *Por apenas {pf}*\n"
    if preco_de and desconto:
        df   = f"R$ {preco_de:,.2f}".replace(",","X").replace(".",",").replace("X",".")
        msg += f"~~De {df}~~ → *{desconto}% OFF* 🔥\n"
    elif desconto:
        msg += f"*{desconto}% OFF* 🔥\n"
    if extra:
        msg += f"💸 {extra}\n"
    if loja:
        msg += f"🏪 Loja: {loja}\n"
    if cupom:
        msg += f"\n🎟️ *CUPOM:* `{cupom}`\n"
    msg += f"\n🔗 [PEGAR OFERTA AGORA]({url})\n"
    msg += f"\n_📢 @NexosPromoBot • {fonte}_"
    return msg


def enviar_telegram(promo: dict) -> bool:
    if not TELEGRAM_TOKEN: return False
    mensagem = formatar_mensagem(promo)
    foto     = promo.get("foto","")
    try:
        if foto and foto.startswith("http"):
            resp = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
                json={"chat_id":TELEGRAM_CHAT_ID,"photo":foto,
                      "caption":mensagem,"parse_mode":"Markdown"},
                timeout=15)
            if resp.status_code == 200:
                print("  [TELEGRAM] ✓ Com foto!")
                return True
            print(f"  [TELEGRAM] Foto falhou ({resp.status_code})")
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id":TELEGRAM_CHAT_ID,"text":mensagem,
                  "parse_mode":"Markdown","disable_web_page_preview":False},
            timeout=15)
        if resp.status_code == 200:
            print("  [TELEGRAM] ✓ Enviado!")
            return True
        print(f"  [TELEGRAM] Erro {resp.status_code}: {resp.text[:80]}")
        return False
    except Exception as e:
        print(f"  [TELEGRAM] Erro: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  SUPABASE
# ══════════════════════════════════════════════════════════════════════════════

def gerar_hash(promo: dict) -> str:
    return hashlib.md5(promo.get("titulo","").lower().strip()[:50].encode()).hexdigest()

def ja_enviada(h: str) -> bool:
    if not SUPABASE_URL or not SUPABASE_KEY: return False
    try:
        hoje = datetime.now().strftime("%Y-%m-%d")
        r    = requests.get(f"{SUPABASE_URL}/rest/v1/promos_enviadas",
            params={"hash":f"eq.{h}","data":f"eq.{hoje}","select":"id"},
            headers={"apikey":SUPABASE_KEY,"Authorization":f"Bearer {SUPABASE_KEY}"},
            timeout=10)
        res = r.json()
        return isinstance(res,list) and len(res) > 0
    except: return False

def marcar_enviada(promo: dict, h: str):
    if not SUPABASE_URL or not SUPABASE_KEY: return
    try:
        r = requests.post(f"{SUPABASE_URL}/rest/v1/promos_enviadas",
            json={"hash":h,"titulo":promo.get("titulo","")[:100],
                  "fonte":promo.get("fonte",""),"preco":promo.get("preco"),
                  "data":datetime.now().strftime("%Y-%m-%d")},
            headers={"apikey":SUPABASE_KEY,"Authorization":f"Bearer {SUPABASE_KEY}",
                     "Content-Type":"application/json","Prefer":"return=minimal"},
            timeout=10)
        if r.status_code in (200,201): print("  [DB] ✓ Salvo")
        else: print(f"  [DB] Erro {r.status_code}: {r.text[:60]}")
    except Exception as e:
        print(f"  [DB] Erro: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("="*60)
    print("  NEXOS PROMO BOT v9")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Shopee AppID: {SHOPEE_APP_ID}")
    print(f"  Supabase: {'✓' if SUPABASE_URL else '✗'}")
    print("="*60)

    todas  = []
    todas += scrape_email()
    todas += scrape_shopee()
    todas += scrape_shopee_produtos()
    todas += scrape_kabum()
    todas += scrape_mercadolivre()

    todas = [p for p in todas if p.get("titulo") and p.get("url")]

    vistos = set()
    unicas = []
    for p in todas:
        chave = p["titulo"].lower().strip()[:50]
        if chave not in vistos:
            vistos.add(chave)
            unicas.append(p)

    unicas.sort(key=lambda x: (0 if "Email" in x.get("fonte","") else 1, -x.get("temp",0)))

    print(f"\n📦 Total único: {len(unicas)} promoções\n")

    if not unicas:
        print("⚠️ Nenhuma promoção encontrada.")
        return

    enviadas = 0
    for promo in unicas:
        h = gerar_hash(promo)
        if ja_enviada(h):
            print(f"  ⏭ Já enviada: {promo['titulo'][:50]}")
            continue

        tem_foto = "📸" if promo.get("foto") else "📝"
        print(f"\n{tem_foto} [{promo['fonte']}] {promo['titulo'][:55]}")

        ok = enviar_telegram(promo)
        if ok:
            marcar_enviada(promo, h)
            enviadas += 1

        time.sleep(random.randint(30, 60))

        if enviadas >= 15:
            print("\n✅ Limite de 15 atingido.")
            break

    print(f"\n{'='*60}")
    print(f"  ✅ {enviadas} promoções enviadas.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
