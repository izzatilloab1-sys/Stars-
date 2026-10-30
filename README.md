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
- 🎁 **Bonus Stars tizimi** — zadaniya (reklama kanallariga obuna) orqali Stars ishlash, majburiy obuna, qo'lda yechib olish va referal bonusi (pastga qarang)

---

## 🎁 Bonus Stars tizimi (yangi)

Pullik Stars sotuvidan **alohida**, foydalanuvchilar **bonus Stars** ham to'playdi.
Bonus **faqat Stars ko'rinishida** (`User.stars_balance`) — so'm emas. Pul va TON
orqali sotib olingan Stars esa avvalgidek Fragment orqali avtomatik yetkaziladi.

### 🌟 Stars ishlash (zadaniya)
- Admin `/admin` → **🌟 Stars ishlash (zadaniya)** orqali reklama kanallarini qo'shadi
  va har bir zadaniya uchun necha ⭐ berilishini belgilaydi.
- Bot kanalda **admin** bo'lishi shart — shunda obunani tekshira oladi (`getChatMember`)
  va obuna linkini yarata oladi.
- Foydalanuvchi **🌟 Stars ishlash** tugmasi orqali kanalga obuna bo'lib «✅ Tekshirish»
  bosadi; obuna tasdiqlansa, Stars balansiga mukofot bir marta qo'shiladi.

### 📢 Majburiy obuna (bot yaratgan unikal linklar)
- Admin `/admin` → **📢 Majburiy obuna** orqali majburiy kanallarni qo'shadi.
- Admin avval botni kanalga **admin** qiladi; keyin bot har bir kanal uchun **unikal
  invite link** yaratadi (`createChatInviteLink`). Obunachilar aynan shu link orqali
  qo'shilgani uchun bot orqali nechta odam kelganini hisoblash mumkin.
- Foydalanuvchi botdan foydalanishdan oldin shu kanallarga obuna bo'lishi shart.

### 💸 Stars yechib olish (qo'lda / ruchnoy)
- Foydalanuvchi **💸 Yechib olish** → **15 / 25 / 50 ⭐** paketini tanlaydi
  (minimal **15 ⭐**). Stars balansdan darhol ushlab qolinadi (hold).
- Zayafka (so'rov) admin ulagan **yechib olish kanaliga** tushadi, tagida
  **[✅ To'landi]** va **[❌ Bekor qilish]** tugmalari bo'ladi.
- Admin Stars'ni **qo'lda** tashlaydi va «✅ To'landi» bosadi. Noqonuniy multiakkaunt
  aniqlansa «❌ Bekor qilish» bosiladi — Stars foydalanuvchi balansiga qaytadi.

### 👥 Referal bonusi (zadaniya chegarasi bilan)
- Referal bonusi endi **Stars** ko'rinishida (`referral_stars`).
- Taklif qilingan foydalanuvchi **belgilangan sondagi zadaniya** (`referral_task_threshold`,
  default **3**) ni bajargach, uni taklif qilgan odamning Stars balansiga bir martalik
  bonus qo'shiladi (`User.ref_bonus_given` bilan ikki marta berilishdan himoyalangan).
- Admin `/admin` → **👥 Referallarni ko'rish** orqali istalgan foydalanuvchi ID sini
  kiritib, u kimlarni chaqirganini ko'radi: har bir referalning **ID si, @username (niki)**
  va bajargan zadaniyalari soni — multiakkauntni aniqlash uchun.

### ⚙️ Yangi sozlamalar (admin panel / DB `settings`)
| Kalit | Tavsif |
|-------|--------|
| `withdraw_channel_id` | Yechib olish zayafkalari tushadigan kanal (`-100...` yoki `@username`) |
| `referral_task_threshold` | Referal bonusi uchun bajariladigan zadaniyalar soni (default 3) |
| `ton_uzs_rate` | 1 TON = ? so'm (admin o'rnatsa, so'm→TON shunga tayanadi; 0/bo'sh = jonli API kursi) |
| `referral_stars` | Referal bonusi (endi **Stars**da; 0 = foizli rejim) |

> `/admin` → **⚙️ Narx va referal sozlamalari** dan: 1 Star narxi, referal Stars,
> referal zadaniya chegarasi, **💎 TON kursi** va yechib olish kanali sozlanadi.

### ⚠️ Mavjud bazani yangilash (MUHIM migratsiya eslatmasi)
`init_db` faqat `Base.metadata.create_all` ni ishga tushiradi — u **yangi jadvallarni**
(`tasks`, `task_completions`, `withdrawals`, `required_channels`) avtomatik yaratadi,
lekin **mavjud `users` jadvaliga yangi ustunlar QO'SHMAYDI** (ALTER yo'q).

Shu sababli **eski** `stars_bot.db` da `User` ning yangi ustunlari
(`stars_balance`, `ref_bonus_given`) bo'lmaydi. Ikki yo'ldan birini tanlang:

1. **Toza o'rnatish:** eski `stars_bot.db` faylini o'chiring — bot ishga tushganda
   barcha jadvallar yangidan yaratiladi.
2. **Qo'lda migratsiya:** bazani saqlab qolish uchun quyidagilarni bajaring:
   ```sql
   ALTER TABLE users ADD COLUMN stars_balance INTEGER DEFAULT 0;
   ALTER TABLE users ADD COLUMN ref_bonus_given BOOLEAN DEFAULT 0;
   ```
   (Yangi jadvallar — `tasks`, `task_completions`, `withdrawals`, `required_channels` —
   `create_all` tomonidan avtomatik yaratiladi, qo'lda yaratish shart emas.)

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

> **MUHIM — ikki xil Stars oqimi:**
> - 💰 **Pul/TON bilan SOTIB OLISH → AVTOMATIK** (Fragment orqali, `fragment` rejim). Bot o'zi sotib olib yuboradi.
> - 🎁 **Bonus/ishlangan Stars YECHIB OLISH → QO'LDA** (ruchnoy). Bu Fragment'ga ulanmaydi; admin kanalga zayafka tushadi, Stars'ni admin o'zi tashlaydi. (`💸 Yechib olish` bo'limiga qarang.)

### `fragment` — avtomatik sotib olish (DEFAULT) ⭐
Bu **default rejim**. Pullik buyurtma to'langach, bot **Fragment'dan avtomatik** Stars
sotib olib foydalanuvchiga yuboradi — admin aralashmaydi.

**Avtomatik ishlashi uchun 4 shart** (admin panel → 🔗 Akkaunt ulash da holat ko'rinadi):
1. ✅ Rejim = `fragment`
2. ✅ TON hamyon seed ulangan (hamyonda yetarli TON bo'lsin)
3. ✅ Fragment kutubxonasi o'rnatilgan (`pip install fragment-api-lib`)
4. 🍪 Fragment cookie — faqat **KYC rejimida** kerak (KYC'siz rejimda faqat faol TON hamyon yetarli)

Biror shart bajarilmasa, admin panelда 🔴 belgi bilan ko'rsatiladi va to'lov o'tgach
adminga aniq sabab bilan xabar keladi (buyurtma yo'qolmaydi).

### `manual` — qo'lda (avto o'chirilgan)
Agar avto rejimni o'chirsangiz: to'lovdan so'ng adminga xabar keladi, admin qo'lda
yuboradi va **«✅ Yetkazdim»** bosadi.

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

### 💳 Balans to'ldirish
Foydalanuvchi asosiy menyudan **💳 Balans to'ldirish** → summa (yoki tayyor summalar)
→ to'lov usuli (TON / Click / Payme) tanlaydi. To'lov tasdiqlangach, so'm balansga
qo'shiladi va keyin Stars sotib olishda ishlatiladi.

### 🎁 Hadya paketlari (15 / 25 / 50 ...)
Stars sotib olishda @username kiritilgach, tayyor paketlar chiqadi: **15, 25, 50, 100,
500, 1000 ⭐** yoki «✏️ Boshqa miqdor». Stars sizning **ulangan akkauntingizdan**
ko'rsatilgan @username ga yuboriladi.

### ⚙️ Narx va referal sozlamalari (admin panel)
`/admin` → **⚙️ Narx va referal sozlamalari**:
- 💰 **1 Star narxi** — bitta narx kiritiladi, barcha hisob shunga asoslanadi (DB'da saqlanadi, `.env` dan ustun)
- 👥 **Referal Stars** — referal zadaniya chegarasini bajargach, taklif qilgan odamning bonus Stars balansiga qo'shiladigan ⭐ soni. `0` = foizli rejim.
- 🎯 **Referal zadaniya chegarasi** — referal necha zadaniya bajarsa bonus beriladi (default 3).
- 💎 **TON kursi** — 1 TON = ? so'm (o'rnatilsa so'm→TON shunga tayanadi, 0 = jonli API kursi).
- 💸 **Yechib olish kanali** — qo'lda yechib olish zayafkalari tushadigan kanal.

### 👮 Adminlar va egalik (admin panel)
`/admin` → **👮 Adminlar**:
- ➕ **Admin qo'shish** / 🗑 **Adminlikdan olish** (faqat bot egasi)
- 👑 **Egalikni o'tkazish** — egalik huquqini boshqa foydalanuvchiga beradi (faqat ega ko'radi)

> **Admin panel tugmasi** faqat adminlarga ko'rinadi (asosiy menyuda 🛠 Admin panel).
> `.env` dagi `ADMIN_IDS`ning birinchisi — standart ega (owner), keyin egalikni o'tkazish mumkin.

### 🔗 Akkaunt ulash (admin panel orqali)
`.env` ni tahrirlamasdan, **bot ichidan** akkaunt ulashingiz mumkin:

`/admin` → **🔗 Akkaunt ulash**:
- 🔑 **Hamyon seed (Tonkeeper)** — 12/24 so'z (to'lov manbai; hamyonda TON bo'lsin)
- 📱 **Telegram akkaunt (raqam)** — telefon raqam orqali ulash (pastga qarang)
- 🍪 **Fragment cookie** — `stel_token`, `stel_ssid`, `stel_dt`, `stel_ton_token`
- ⚙️ **Rejim** — `manual` ↔ `fragment` almashtirish
- 💎 **Balansni tekshirish** — ulangan hamyonning TON balansi
- 🗑 **Akkauntni uzish** — barcha maxfiy ma'lumotni o'chiradi

### 📱 Telegram akkauntni telefon raqam orqali ulash (Telethon)

Fragment'da Stars sotib olish uchun Telegram akkauntingizni ulashning **ikki usuli**:

**Usul A — bot ichida (admin panel):**
`/admin` → 🔗 Akkaunt ulash → 📱 Telegram akkaunt:
1. 🔧 **api_id / api_hash** ni kiriting ([my.telegram.org](https://my.telegram.org) → API development tools, bepul)
2. 📞 **Raqam orqali ulash** → telefon raqamingizni yuboring
3. Telegramga kelgan **kodni** kiriting (xavfsizlik uchun `1 2 3 4 5` kabi bo'sh joy bilan)
4. Agar 2FA parolingiz bo'lsa — parolni kiriting
5. ✅ Session yaratilib, DB'ga saqlanadi

**Usul B — alohida skript (xavfsizroq):**
```bash
python -m bot.login
```
Terminalda raqam + kod + 2FA so'raydi, so'ngra **session string** chiqaradi.
Uni `.env` ga `TG_SESSION=...` deb yozing yoki admin panelda **📋 Session string joylash**
orqali kiriting.

- 🔍 **Ulanishni tekshirish** — session ishlayotganini va qaysi akkaunt ulanganini ko'rsatadi
- 🗑 **Akkauntni uzish** — session'ni o'chiradi

> ⚠️ Session string = akkauntingizga **to'liq kirish**. Hamyon seed kabi maxfiy saqlang.
> Kod/parol/session yuborilgan xabarlar chatdan avtomatik o'chiriladi.

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
   So'mdagi narx TON ga aylantiriladi. Agar admin panelda **TON kursi** (`ton_uzs_rate`)
   o'rnatilgan bo'lsa (`> 0`), aynan shu kurs ishlatiladi; aks holda TON/USD — CoinGecko,
   USD/UZS — `.env` dagi `USD_UZS_RATE`.
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
│   ├── login.py           # Telegram akkaunt session olish skripti (python -m bot.login)
│   ├── config.py          # .env sozlamalari
│   ├── middlewares.py     # ban middleware
│   ├── database/          # modellar + DB funksiyalari (SQLite)
│   ├── handlers/          # user, buy, payment, admin
│   ├── keyboards/         # tugmalar
│   ├── services/          # fragment, payment (Click/Payme), ton_payment, tg_account (Telethon)
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
