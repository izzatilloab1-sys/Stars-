# ⭐ Stars Bot — Telegram Stars sotuvchi bot

Fragment orqali istalgan Telegram foydalanuvchisiga **Telegram Stars** sotadigan bot.
Avtomatik to'lov (Click / Payme / bonus balans), referal tizimi, promokod va admin panel bilan.

> **Halol reselling boti.** Bu bot Stars'ni qayta sotish uchun. U *nakrutka* (sun'iy
> obunachi/layk ko'paytirish) qilmaydi.

---

## 🧩 Imkoniyatlar

- ⭐ **Stars sotib olish** — @username + miqdor → to'lov → yetkazish
- 💳 **Avtomatik to'lov** — Click, Payme, yoki ichki bonus balans
- 👥 **Referal tizimi** — do'st taklif qilib, har buyurtmadan `%` bonus olish (firibgarlikdan himoyalangan: o'ziga referal bo'lmaydi)
- 🎁 **Promokod** — admin yaratadi, foydalanuvchi bir marta ishlatadi
- 🚚 **Fragment integratsiyasi** — `manual` (admin qo'lda) yoki `ton` (avtomatik) rejim
- 🛠 **Admin panel** — statistika, promokod yaratish, balans qo'shish, broadcast, yetkazishni tasdiqlash
- 🚫 **Ban tizimi** — middleware orqali

---

## 📦 O'rnatish

```bash
# 1. Virtual muhit
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Kutubxonalar
pip install -r requirements.txt

# 3. Sozlamalar
cp .env.example .env
# .env ni to'ldiring (pastga qarang)

# 4. Ishga tushirish
python -m bot.main          # bot (polling)

# 5. (Click/Payme uchun) webhook serverini alohida ishga tushiring
python -m bot.webhook       # callback server (0.0.0.0:8080)
```

> TON va bonus balans bilan ishlash uchun faqat `bot.main` kifoya.
> Click/Payme (so'm) avtomatik tasdiqlash uchun `bot.webhook` ham kerak.

---

## ⚙️ Sozlash (.env)

| O'zgaruvchi | Tavsif |
|-------------|--------|
| `BOT_TOKEN` | @BotFather'dan olingan token |
| `ADMIN_IDS` | Admin Telegram ID'lari, vergul bilan: `111,222` |
| `PRICE_PER_STAR` | 1 Star narxi (so'm) |
| `MIN_STARS` / `MAX_STARS` | Buyurtma chegaralari |
| `REFERRAL_BONUS_PERCENT` | Referal bonusi (%) |
| `CLICK_*` | Click merchant ma'lumotlari |
| `PAYME_*` | Payme merchant ma'lumotlari |
| `FRAGMENT_MODE` | `manual` yoki `ton` |
| `TON_WALLET_MNEMONIC` | TON hamyon 24 so'zi (`ton` rejimi uchun) |
| `TON_API_KEY` | toncenter.com API kaliti |

> Telegram ID'ingizni bilish uchun [@userinfobot](https://t.me/userinfobot) ga yozing.

---

## 🚚 Stars yetkazish rejimlari

### `manual` — qo'lda (kalit kerak emas)
To'lovdan so'ng adminga xabar keladi. Admin Fragment'da qo'lda yuboradi va botda
**«✅ Yetkazdim»** tugmasini bosadi.

### `fragment` — avtomatik (Fragment'dan o'zi sotib oladi) ⭐
Bot sizning **Fragment cookie'laringiz** va **TON hamyon seed'ingiz** orqali
Fragment.com'dan Stars'ni avtomatik sotib olib, foydalanuvchiga yetkazadi.

**Qanday ishlaydi (hamyondan TON/USDT qanday yechiladi):**
1. Bot Fragment'ga «@user'ga N Stars» buyurtmasini beradi (cookie bilan login holatida).
2. Fragment to'lov so'raydi (TON summasi + maxsus payload).
3. Bot **seed bilan tranzaksiyani imzolab**, hamyondan TON'ni Fragment'ga yuboradi.
   `FRAGMENT_PAY_CURRENCY=usdt` bo'lsa, to'lov USDT-jetton transferi sifatida yuboriladi
   (hamyonda USDT balansi bo'lishi kerak).
4. Fragment Stars'ni username'ga yetkazadi.

**Kerak bo'ladigan Fragment kutubxonasi** (biri):
```bash
pip install fragment-api      # yoki
pip install pyfragment
```
`fragment.py` ikkala kutubxona interfeysiga adapter bilan moslashgan. Kutubxona
versiyasi o'zgarsa, `_try_fragment_api` / `_try_pyfragment` dagi chaqiruvni moslang.

### 🔗 Akkaunt ulash (admin panel orqali)
`.env` ni tahrirlamasdan, **bot ichidan** akkaunt ulashingiz mumkin:

`/admin` → **🔗 Akkaunt ulash**:
- 🔑 **Hamyon seed** — 12/24 so'z (to'lov manbai; hamyonda TON bo'lsin)
- 🍪 **Fragment cookie** — `stel_token`, `stel_ssid`, `stel_dt`, `stel_ton_token`
- ⚙️ **Rejim** — `manual` ↔ `fragment` almashtirish
- 💎 **Balansni tekshirish** — ulangan hamyonning TON balansi
- 🗑 **Akkauntni uzish** — barcha maxfiy ma'lumotni o'chiradi

> Admin paneldan kiritilgan qiymat `.env` dan **ustun** turadi (DB'da `settings`
> jadvalida saqlanadi). Seed/cookie yuborilgan xabar avtomatik o'chiriladi.

**Cookie qanday olinadi:**
1. Brauzerda [fragment.com](https://fragment.com) ga Telegram orqali login qiling
2. TON hamyoningizni ulang (*Connect TON*)
3. `F12` → **Application → Cookies → fragment.com** dan 4 ta qiymatni ko'chiring

> ⚠️ **Xavfsizlik:** seed = hamyoningizga to'liq kirish. Uni va cookie'larni faqat
> o'zingiz boshqaradigan ishonchli serverda saqlang, hech kimga bermang, git'ga
> qo'ymang. Bu sizning shaxsiy (biznes) akkauntingiz bo'lsin.

---

## 💳 To'lov tizimi

Bot **to'rt** usulni qo'llab-quvvatlaydi:

| Usul | Valyuta | Tasdiqlash |
|------|---------|-----------|
| **TON** 💎 | TON (kripto) | Avtomatik — blokcheyndan (toncenter) |
| **Click** 💳 | so'm | Avtomatik — webhook |
| **Payme** 💳 | so'm | Avtomatik — webhook |
| **Bonus balans** 💰 | ichki | Darhol |

### 💎 TON orqali to'lov (avtomatik)

1. Foydalanuvchi «TON orqali» ni tanlaydi.
2. Bot **hamyon manzili + aniq TON summasi + unikal izoh (memo)** beradi.
   So'mdagi narx TON ga aylantiriladi (TON/USD — CoinGecko, USD/UZS — `.env` dagi `USD_UZS_RATE`).
3. Foydalanuvchi o'z hamyonidan (Tonkeeper va h.k.) to'laydi.
4. «Tekshirish» bosilganda bot `toncenter` API orqali kelgan tranzaksiyani
   izoh + summa bo'yicha topadi va buyurtmani avtomatik tasdiqlaydi.

`.env` da `TON_WALLET_ADDRESS` ni to'ldiring (to'lovlar keladigan manzil).
Kurs tebranishi uchun 3% bardoshlilik bor.

### 💳 Click / Payme (webhook orqali avtomatik)

So'mdagi to'lovlar **webhook server** orqali avtomatik tasdiqlanadi:

```bash
python -m bot.webhook      # alohida terminal/process (bot bilan birga ishlaydi)
```

Serverni domenga (HTTPS) ulang va provayder kabinetida callback URL ko'rsating:
- **Payme:** `https://sizning-domen.uz/payme` (Basic auth: login `Paycom`, parol = `PAYME_KEY`)
- **Click:** `https://sizning-domen.uz/click`

Webhook to'lovni qabul qilganda buyurtmani `PAID` qiladi va Stars yetkazishni ishga tushiradi.
`verify_payment()` esa «Tekshirish» tugmasi bosilganda buyurtma webhook orqali
to'langanmi — shuni tekshiradi. Imzolar (`_click_sign`, Payme Basic auth) tekshiriladi.

> Ikki marta yetkazishdan himoya: `mark_paid_if_pending()` atomik ravishda faqat
> birinchi `PENDING → PAID` o'tishida yetkazishni ishga tushiradi.

---

## 📂 Tuzilma

```
stars_bot/
├── bot/
│   ├── main.py            # bot kirish nuqtasi (polling)
│   ├── webhook.py         # Click/Payme callback serveri (aiohttp)
│   ├── config.py          # .env sozlamalari
│   ├── middlewares.py     # ban middleware
│   ├── database/          # modellar + DB funksiyalari (SQLite)
│   ├── handlers/          # user, buy, payment, admin
│   ├── keyboards/         # tugmalar
│   ├── services/          # fragment (yetkazish), payment (Click/Payme), ton_payment (TON)
│   └── utils/             # FSM holatlar
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🔐 Xavfsizlik eslatmalari

- `.env` ni **hech qachon** git'ga qo'shmang (token, kalitlar sir).
- TON hamyon seed'ini faqat ishonchli serverda saqlang.
- To'lovni avtomatik tasdiqlashni ulamaguningizcha, `verify_payment` `False` qoldiring —
  bu pul kelmasdan Stars yetkazilib ketishining oldini oladi.
