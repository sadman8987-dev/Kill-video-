# 🎬 Telegram Media Downloader Bot

بوت تيليجرام متكامل لتحميل الفيديو والصوت من يوتيوب وتيك توك وإنستغرام وفيسبوك وX وأكثر من 1000 موقع.
A full-featured Telegram bot that downloads video/audio from 1000+ sites. Built with **aiogram 3 · yt-dlp · ffmpeg · SQLite**.

## ✨ المميزات / Features

| | |
|---|---|
| 🔗 تحميل بالرابط | اختيار الجودة (360p–2160p) مع الحجم التقريبي، أو MP3 |
| 🔎 بحث بالاسم | اكتب اسم الأغنية/الفيديو أو `/search` ← اختر من النتائج |
| 🎵 `/mp3` | صوت مباشرة بالاسم أو الرابط |
| 📃 قوائم التشغيل | أول N عنصر كفيديو أو MP3 |
| ⚡ كاش الملفات | نفس الملف يُرسل فوراً بدون إعادة تحميل (file_id) |
| ✂️ تقسيم تلقائي | الملفات الأكبر من الحد تُقسَّم لأجزاء بدل الفشل |
| 📊 تقدم حي | نسبة + سرعة + وقت متبقٍ + زر إلغاء |
| 🖼 صورة مصغرة وبيانات | عنوان/فنان/مدة وثمبنيل صحيح للفيديو والصوت |
| ⚙️ `/settings` | لغة (عربي/English) وجودة افتراضية (تحميل فوري بدون أسئلة) |
| 🛡 حماية | حد يومي، منع الفلود، حد أقصى للمدة، قائمة سماح، اشتراك إجباري بقناة |
| 🛠 لوحة أدمن | `/stats` `/broadcast` `/ban` `/unban` `/user` `/cleancache` `/restart` |
| 🌐 Webhook | وضع Polling (افتراضي) أو Webhook مع `/health` |
| 🐳 Docker + CI | تحديث yt-dlp تلقائياً عند كل تشغيل، واختبارات وحدة |

## 🚀 التشغيل السريع / Quick start

1. أنشئ البوت من [@BotFather](https://t.me/BotFather) وخذ التوكن.
2. اعرف رقم حسابك من [@userinfobot](https://t.me/userinfobot) (للأدمن).
3. الإعداد:
   ```bash
   cp .env.example .env
   # عدّل BOT_TOKEN و ADMIN_IDS
   ```
4. **Docker (الموصى به):**
   ```bash
   docker compose up -d --build
   docker compose logs -f bot
   ```
   **أو بدون Docker** (يتطلب Python 3.11+ و **ffmpeg** و **deno**):
   ```bash
   python -m venv .venv && source .venv/bin/activate
   make install && make run
   ```

## 🤖 الأوامر / Commands

| الأمر | الوظيفة |
|---|---|
| `/start` `/help` | البداية والمساعدة |
| `/search اسم` | بحث في يوتيوب |
| `/mp3 اسم أو رابط` | تحميل صوت مباشرة |
| `/dl رابط` | تحميل برابط (يعمل في المجموعات) |
| `/settings` | اللغة والجودة الافتراضية |
| `/admin` | لوحة الأدمن (للأدمن فقط) |

## ⚙️ الإعدادات / Configuration
كل المتغيرات موثقة داخل [`.env.example`](.env.example). أهمها:
`BOT_TOKEN` · `ADMIN_IDS` · `ALLOWED_USERS` · `FORCE_SUB` · `DAILY_LIMIT` · `MAX_CONCURRENT` · `MAX_PLAYLIST_ITEMS` · `MAX_DURATION` · `LOCAL_API_URL` · `WEBHOOK_URL` · `COOKIES_FILE` · `PROXY`

## 📦 الملفات الكبيرة (حتى 2GB)
الحد الافتراضي 50MB (قيد تيليجرام) والأكبر يُقسَّم تلقائياً. للرفع حتى 2GB:
1. احصل على `api_id` و `api_hash` من https://my.telegram.org وضعهما في `.env`
2. ضع `LOCAL_API_URL=http://telegram-bot-api:8081`
3. **مرة واحدة فقط:** سجّل خروج البوت من السيرفر الرسمي: `https://api.telegram.org/bot<TOKEN>/logOut`
4. شغّل: `docker compose --profile local-api up -d --build`

## ☁️ النشر / Deployment
- **VPS:** Docker compose كما فوق (الأفضل للملفات الكبيرة).
- **Railway / Render / Fly.io (Docker):** انشر من المستودع، أضف المتغيرات، واضبط `WEBHOOK_URL` على رابط الخدمة العام. المنفذ `PORT`، ومسار الفحص `/health`. لا تنسَ Volume على `/app/data` لحفظ قاعدة البيانات.
- ⚠️ بعض مزودي الاستضافة المشتركة تحظر مواقع مثل يوتيوب على عناوين IP الخاصة بهم؛ استخدم `COOKIES_FILE` أو `PROXY` أو VPS.

## 🍪 الكوكيز (للمحتوى المقيّد)
صدّر `cookies.txt` (صيغة Netscape) من متصفحك، ضعه بجانب `docker-compose.yml`، فعّل سطر الـ volume في الـ compose، واضبط `COOKIES_FILE=/app/cookies.txt`.

## 🛠️ الصيانة وحل المشاكل
- موقع توقف عن العمل؟ أرسل `/restart` للأدمن أو أعد تشغيل الحاوية (يتم تحديث yt-dlp تلقائياً)، أو `pip install -U yt-dlp`.
- رسالة "المحتوى خاص/تسجيل دخول": استخدم الكوكيز.
- لا يدعم: Spotify/Netflix وكل ما هو محمي بـ DRM، ولا البث المباشر.

## 🗂 هيكل المشروع
```
bot/
  main.py          تشغيل (polling/webhook) وربط المكونات
  config.py        قراءة الإعدادات من البيئة
  db.py            SQLite: مستخدمون، سجل تحميلات، كاش file_id
  downloader.py    yt-dlp: فحص رابط، بحث، تحميل
  jobs.py          تنفيذ المهمة: كاش ← تحميل ← تقسيم ← رفع
  media.py         ffmpeg: ثمبنيل، مدة، تقسيم
  formats.py       دوال نقية: الجودات، الأحجام، تصنيف الأخطاء
  middlewares.py   صلاحيات، حظر، فلود، اشتراك إجباري
  keyboards.py · i18n.py · state.py · utils.py
  handlers/        user.py · admin.py
tests/             اختبارات unittest (python -m unittest)
```

## ⚖️ تنبيه قانوني
استخدم البوت فقط لتحميل محتوى تملكه أو مسموح لك بتحميله، والتزم بشروط المنصات وحقوق النشر. أنت المسؤول عن طريقة استخدامه.

## 📄 الرخصة
MIT