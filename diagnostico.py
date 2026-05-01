"""
Script de diagnóstico — rode no Railway para ver quais APIs funcionam
"""
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

testes = [
    ("Telegram API",       "https://api.telegram.org"),
    ("Mercado Livre API",  "https://api.mercadolibre.com/sites/MLB/search?q=notebook&limit=1"),
    ("KaBuM API",          "https://servicespub.prod.api.aws.grupokabum.com.br/catalog/v2/products-by-category/oferta-do-dia?page_number=1&page_size=1&is_off=true"),
    ("Pelando GraphQL",    "https://www.pelando.com.br/api/graphql"),
    ("Shopee API",         "https://shopee.com.br/api/v4/flash_sale/get_all_sessions"),
    ("Pichau API",         "https://www.pichau.com.br/api/pichau/getOffers"),
    ("Promobit API",       "https://api.promobit.com.br/offers?limit=5"),
    ("OFX API",            "https://www.offerxpert.com.br/api/offers"),
    ("Google",             "https://www.google.com"),
    ("HTTPBin",            "https://httpbin.org/get"),
]

print("=" * 50)
print("TESTE DE CONECTIVIDADE — RAILWAY")
print("=" * 50)

for nome, url in testes:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        print(f"✓ {nome}: {resp.status_code} — {len(resp.content)} bytes")
    except Exception as e:
        print(f"✗ {nome}: BLOQUEADO — {str(e)[:60]}")

print("=" * 50)
