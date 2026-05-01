"""
================================================================================
  NEXOS PROMO BOT v10 (FULL FIXED)
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
import json
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from email.header import decode_header

# ================= ENV =================
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003723940229")

SUPABASE_URL     = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY     = os.getenv("SUPABASE_KEY", "")

GMAIL_USER       = os.getenv("GMAIL_USER", "")
GMAIL_PASS       = os.getenv("GMAIL_PASS", "")

SHOPEE_APP_ID    = os.getenv("SHOPEE_APP_ID", "")
SHOPEE_SECRET    = os.getenv("SHOPEE_SECRET", "")

# ================= SHOPEE =================

def gerar_assinatura_shopee(payload_dict):
    timestamp = str(int(datetime.utcnow().timestamp()))
    payload_str = json.dumps(payload_dict, separators=(",", ":"))

    base = f"{SHOPEE_APP_ID}{timestamp}{payload_str}{SHOPEE_SECRET}"
    sign = hashlib.sha256(base.encode()).hexdigest()

    return {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={SHOPEE_APP_ID},Timestamp={timestamp},Signature={sign}",
        "User-Agent": "Mozilla/5.0"
    }

def scrape_shopee():
    print("[SHOPEE] buscando...")
    url = "https://open-api.affiliate.shopee.com.br/graphql"

    payload = {
        "query": """
        query {
          shopeeOfferV2(sortType:2,page:1,limit:20){
            nodes{
              offerName
              imageUrl
              offerLink
              commissionRate
            }
          }
        }
        """
    }

    headers = gerar_assinatura_shopee(payload)

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)

        if r.status_code != 200:
            print("[SHOPEE ERRO]", r.text[:200])
            return []

        data = r.json()
        nodes = data.get("data", {}).get("shopeeOfferV2", {}).get("nodes", [])

        promos = []
        for n in nodes:
            if not n.get("offerLink"):
                continue

            promos.append({
                "fonte": "Shopee",
                "titulo": n.get("offerName"),
                "url": n.get("offerLink"),
                "foto": n.get("imageUrl"),
                "temp": 95
            })

        print("[SHOPEE OK]", len(promos))
        return promos

    except Exception as e:
        print("[SHOPEE FAIL]", e)
        return []

# ================= KABUM =================

def scrape_kabum():
    print("[KABUM] buscando...")
    try:
        r = requests.get("https://servicespub.prod.api.aws.grupokabum.com.br/catalog/v2/products-by-category/oferta-do-dia?page_number=1&page_size=10&sort=0")
        data = r.json()

        promos = []
        for item in data.get("data", []):
            promos.append({
                "fonte": "Kabum",
                "titulo": item.get("name"),
                "url": f"https://www.kabum.com.br/produto/{item.get('path')}",
                "foto": item.get("img"),
                "temp": 90
            })
        return promos
    except:
        return []

# ================= MERCADO LIVRE =================

def scrape_ml():
    print("[ML] buscando...")
    try:
        r = requests.get("https://api.mercadolibre.com/sites/MLB/search?q=oferta&limit=10")
        data = r.json()

        promos = []
        for item in data.get("results", []):
            promos.append({
                "fonte": "ML",
                "titulo": item.get("title"),
                "url": item.get("permalink"),
                "foto": item.get("thumbnail"),
                "temp": 85
            })
        return promos
    except:
        return []

# ================= EMAIL =================

def scrape_email():
    print("[EMAIL] buscando...")
    promos = []
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_PASS)
        mail.select("inbox")

        _, ids = mail.search(None, 'UNSEEN')
        for eid in ids[0].split()[-10:]:
            _, msg_data = mail.fetch(eid, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])

            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/html":
                        html = part.get_payload(decode=True).decode(errors="ignore")
                        soup = BeautifulSoup(html, "html.parser")

                        for a in soup.find_all("a", href=True):
                            if "http" in a["href"]:
                                promos.append({
                                    "fonte": "Email",
                                    "titulo": a.get_text()[:80],
                                    "url": a["href"],
                                    "foto": "",
                                    "temp": 100
                                })
                                break
            mail.store(eid, "+FLAGS", "\\Seen")

        mail.logout()
    except:
        pass

    return promos

# ================= TELEGRAM =================

def enviar(p):
    try:
        msg = f"🔥 {p['titulo']}\n{p['url']}"
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}
        )
        print("[ENVIADO]")
    except:
        print("[ERRO TELEGRAM]")

# ================= MAIN =================

def main():
    print("==== BOT RODANDO ====")

    todas = []
    todas += scrape_email()
    todas += scrape_shopee()
    todas += scrape_kabum()
    todas += scrape_ml()

    vistos = set()
    unicas = []

    for p in todas:
        chave = (p.get("titulo") or "")[:50]
        if chave not in vistos:
            vistos.add(chave)
            unicas.append(p)

    print("TOTAL:", len(unicas))

    for p in unicas[:15]:
        enviar(p)
        time.sleep(random.randint(20, 40))

if __name__ == "__main__":
    main()
