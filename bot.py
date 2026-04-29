"""
================================================================================
  NEXOS PROMO BOT v6
  - Lê emails de promoção automaticamente (Pichau, Terabyte, KaBuM, etc)
  - Extrai título, preço e foto dos emails
  - Envia no Telegram com foto
  - Fontes: Email + Pelando + KaBuM API + ML API + Shopee
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

# Email
GMAIL_USER = os.getenv("GMAIL_USER", "codenexobr@gmail.com")
GMAIL_PASS = os.getenv("GMAIL_PASS", "qmeffbqmakyljxhm")  # senha de app sem espaços

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Accept": "application/json, text/html, */*",
}

# Remetentes de lojas que você assinou newsletter
REMETENTES_LOJAS = [
    "pichau", "terabyte", "kabum", "magazineluiza", "magalu",
    "casasbahia", "americanas", "submarino", "shoptime",
    "extra", "pontofrio", "fastshop", "amazon",
]


# ══════════════════════════════════════════════════════════════════════════════
#  LEITOR DE EMAIL — MÓDULO PRINCIPAL NOVO
# ══════════════════════════════════════════════════════════════════════════════

def decodificar_assunto(assunto_raw) -> str:
    """Decodifica assunto do email."""
    partes = decode_header(assunto_raw)
    assunto = ""
    for parte, enc in partes:
        if isinstance(parte, bytes):
            assunto += parte.decode(enc or "utf-8", errors="ignore")
        else:
            assunto += parte
    return assunto.strip()


def extrair_promos_do_email(html_body: str, remetente: str) -> list:
    """
    Extrai promoções do corpo HTML do email.
    Retorna lista de promos no mesmo formato dos scrapers.
    """
    promos = []
    try:
        soup = BeautifulSoup(html_body, "html.parser")

        # Identifica a loja pelo remetente
        loja = "Newsletter"
        for nome in REMETENTES_LOJAS:
            if nome in remetente.lower():
                loja = nome.title()
                break

        # Estratégia 1: Procura por blocos de produto (padrão comum em newsletters)
        # Cada produto tem: imagem + nome + preço + link
        links = soup.find_all("a", href=True)

        for link in links:
            href = link.get("href", "")
            if not href or "unsubscribe" in href.lower() or "descadastrar" in href.lower():
                continue
            if len(href) < 20:
                continue

            # Procura imagem dentro ou perto do link
            img = link.find("img")
            foto = ""
            if img:
                foto = img.get("src", img.get("data-src", "")) or ""
                # Filtra imagens de logo/banner muito pequenas
                width  = img.get("width", "200")
                height = img.get("height", "200")
                try:
                    if int(str(width).replace("px","")) < 80:
                        foto = ""
                except:
                    pass

            # Procura texto de preço próximo ao link
            texto_bloco = link.get_text(" ", strip=True)
            parent      = link.parent
            if parent:
                texto_bloco = parent.get_text(" ", strip=True)

            # Extrai preço do texto
            precos = re.findall(r"R\$\s*[\d.,]+", texto_bloco)
            preco_val = None
            if precos:
                try:
                    num = re.findall(r"[\d.,]+", precos[0])[0]
                    preco_val = float(num.replace(".", "").replace(",", "."))
                except:
                    pass

            # Extrai título — tenta alt da imagem ou texto do link
            titulo = ""
            if img:
                titulo = img.get("alt", "").strip()
            if not titulo or len(titulo) < 5:
                titulo = link.get_text(" ", strip=True)[:80]
            if not titulo or len(titulo) < 5:
                continue

            # Filtra títulos genéricos
            titulo_lower = titulo.lower()
            ignorar = ["clique", "aqui", "ver mais", "saiba mais", "comprar",
                       "acesse", "confira", "oferta", "promoção", "desconto",
                       "newsletter", "logo", "banner", "header", "footer"]
            if any(x in titulo_lower for x in ignorar):
                continue

            # Só adiciona se tem título útil
            if len(titulo) < 8:
                continue

            # Cupom — procura no texto do email
            cupom = ""
            texto_cupom = soup.get_text()
            match_cupom = re.search(
                r"(?:cupom|código|code|coupon)[:\s]+([A-Z0-9]{4,20})",
                texto_cupom, re.IGNORECASE
            )
            if match_cupom:
                cupom = match_cupom.group(1).upper()

            promos.append({
                "fonte":  f"Email ({loja})",
                "titulo": titulo[:80],
                "preco":  preco_val,
                "cupom":  cupom,
                "url":    href,
                "foto":   foto if foto.startswith("http") else "",
                "loja":   loja,
                "temp":   100,  # Email tem prioridade alta
            })

        # Remove duplicatas por URL dentro do mesmo email
        urls_vistos = set()
        unicas = []
        for p in promos:
            if p["url"] not in urls_vistos and p.get("titulo"):
                urls_vistos.add(p["url"])
                unicas.append(p)

        return unicas[:5]  # Máximo 5 promos por email

    except Exception as e:
        print(f"  [EMAIL PARSER] Erro: {e}")
        return []


def scrape_email() -> list:
    """Conecta no Gmail via IMAP e lê emails de promoção não lidos."""
    promos = []
    try:
        print("[EMAIL] Conectando ao Gmail...")
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_PASS)
        mail.select("inbox")

        # Busca emails não lidos dos últimos 2 dias
        data_busca = (datetime.now() - timedelta(days=2)).strftime("%d-%b-%Y")
        _, ids = mail.search(None, f'(UNSEEN SINCE "{data_busca}")')

        email_ids = ids[0].split()
        print(f"[EMAIL] {len(email_ids)} emails não lidos encontrados")

        for eid in email_ids[-20:]:  # Últimos 20 emails
            try:
                _, msg_data = mail.fetch(eid, "(RFC822)")
                msg         = email.message_from_bytes(msg_data[0][1])
                remetente   = msg.get("From", "")
                assunto_raw = msg.get("Subject", "")
                assunto     = decodificar_assunto(assunto_raw)

                # Verifica se é de uma loja conhecida
                eh_loja = any(loja in remetente.lower() for loja in REMETENTES_LOJAS)
                if not eh_loja:
                    continue

                print(f"  [EMAIL] Processando: {assunto[:50]} | De: {remetente[:40]}")

                # Extrai corpo HTML
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

                # Extrai promoções do email
                promos_email = extrair_promos_do_email(html_body, remetente)
                print(f"  [EMAIL] {len(promos_email)} promos extraídas")
                promos += promos_email

                # Marca como lido
                mail.store(eid, "+FLAGS", "\\Seen")

            except Exception as e:
                print(f"  [EMAIL] Erro ao processar email: {e}")
                continue

        mail.logout()
        print(f"[EMAIL] ✓ {len(promos)} promos extraídas dos emails")

    except imaplib.IMAP4.error as e:
        print(f"[EMAIL] Erro de autenticação: {e}")
    except Exception as e:
        print(f"[EMAIL] Erro: {e}")

    return promos


# ══════════════════════════════════════════════════════════════════════════════
#  SCRAPERS VIA API (funcionam no Railway)
# ══════════════════════════════════════════════════════════════════════════════

def scrape_pelando() -> list:
    promos = []
    try:
        print("[PELANDO] Buscando promoções...")
        resp = requests.post(
            "https://www.pelando.com.br/api/graphql",
            json={
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
            },
            headers={**HEADERS, "content-type": "application/json",
                     "origin": "https://www.pelando.com.br",
                     "referer": "https://www.pelando.com.br/"},
            timeout=15
        )
        if resp.status_code == 200:
            for edge in resp.json().get("data", {}).get("hotDeals", {}).get("edges", []):
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
    promos = []
    try:
        print("[KABUM] Buscando ofertas...")
        cats = ["oferta-do-dia","computadores","hardware","perifericos",
                "smartphones-tablets","games","monitores-e-tvs","tv-e-video","eletrodomesticos"]
        for cat in cats:
            try:
                url  = (f"https://servicespub.prod.api.aws.grupokabum.com.br"
                        f"/catalog/v2/products-by-category/{cat}"
                        f"?page_number=1&page_size=12&is_off=true")
                resp = requests.get(url, headers=HEADERS, timeout=10)
                if resp.status_code != 200:
                    continue
                for item in resp.json().get("data", []):
                    nome     = item.get("name", "")
                    preco    = float(item.get("vlr_final") or item.get("price") or 0)
                    preco_de = item.get("vlr_normal")
                    slug     = item.get("path", "")
                    foto     = (item.get("img") or item.get("image") or
                                item.get("thumbnail") or "")
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
                time.sleep(0.3)
            except Exception:
                continue
        print(f"[KABUM] ✓ {len(promos)} ofertas")
    except Exception as e:
        print(f"[KABUM] Erro: {e}")
    return promos


def scrape_mercadolivre() -> list:
    promos = []
    try:
        print("[MERCADO LIVRE] Buscando ofertas com desconto...")
        cats = ["MLB1051","MLB1648","MLB1000","MLB5726","MLB1246","MLB1168","MLB1459","MLB1574"]
        for cat_id in cats[:6]:
            try:
                url  = (f"https://api.mercadolibre.com/sites/MLB/search"
                        f"?category={cat_id}&sort=price_asc&limit=10"
                        f"&attributes=id,title,price,original_price,thumbnail,permalink")
                resp = requests.get(url, headers=HEADERS, timeout=10)
                if resp.status_code != 200:
                    continue
                for item in resp.json().get("results", []):
                    preco    = float(item.get("price", 0) or 0)
                    preco_de = item.get("original_price")
                    if not preco_de or float(preco_de) <= preco:
                        continue
                    desconto = round((1 - preco / float(preco_de)) * 100)
                    titulo   = item.get("title", "")
                    href     = item.get("permalink", "")
                    foto     = item.get("thumbnail", "").replace("I.jpg", "O.jpg")
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
                time.sleep(0.5)
            except Exception:
                continue
        print(f"[MERCADO LIVRE] ✓ {len(promos)} ofertas")
    except Exception as e:
        print(f"[MERCADO LIVRE] Erro: {e}")
    return promos


def scrape_shopee() -> list:
    promos = []
    try:
        print("[SHOPEE] Buscando flash sales...")
        resp = requests.get(
            "https://shopee.com.br/api/v4/flash_sale/get_all_sessions?need_main_image=true",
            headers={**HEADERS, "referer": "https://shopee.com.br/"},
            timeout=15
        )
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
        "Pelando": "🔥", "KaBuM": "💻", "Pichau": "🖥️",
        "Mercado Livre": "🛒", "Shopee": "🧡", "Amazon": "📦",
    }
    emoji = emojis.get(fonte, "📧" if "Email" in fonte else "🏷️")

    msg = f"{emoji} *{titulo}*\n\n"
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
            print("  [TELEGRAM] Foto falhou, enviando texto...")

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
#  SUPABASE — DUPLICATAS
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
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                     "Accept": "application/json"},
            timeout=10
        )
        resultado = resp.json()
        return isinstance(resultado, list) and len(resultado) > 0
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
            print("  [DB] ✓ Salvo no Supabase")
        else:
            print(f"  [DB] Erro {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        print(f"  [DB] Erro: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  NEXOS PROMO BOT v6 — Email + APIs")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Gmail: {GMAIL_USER}")
    print(f"  Supabase: {'✓' if SUPABASE_URL else '✗ não configurado'}")
    print("=" * 60)

    todas = []

    # Emails têm prioridade — vêm primeiro
    todas += scrape_email()
    todas += scrape_pelando()
    todas += scrape_kabum()
    todas += scrape_mercadolivre()
    todas += scrape_shopee()

    # Filtra inválidos
    todas = [p for p in todas if p.get("titulo") and p.get("url")]

    # Remove duplicatas locais por título
    vistos = set()
    unicas = []
    for p in todas:
        chave = p["titulo"].lower().strip()[:50]
        if chave not in vistos:
            vistos.add(chave)
            unicas.append(p)

    # Ordena: email primeiro, depois por temperatura
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
