# MVP Scope - Davomat Tizimi

## Maqsad
O'quv markazlari uchun avtomatik davomat tizimi - ustozlarning ishini yengillashtirish va ota-onalarni real vaqtda xabardor qilish.

## MVP ga KIRADIGAN NARSA

### 1. Owner/Admin Panel (brauzer)
- Markaz yaratish (owner o'zi ro'yxatdan o'tadi)
- Guruhlarni boshqarish (yaratish, tahrirlash, arxivlash)
- O'quvchilarni boshqarish:
  - Bitta qo'shish
  - Ommaviy qo'shish (ro'yxatdan)
  - Guruhlar o'rtasida ko'chirish
  - Guruhlarni birlashtirish
  - Arxivlash/tiklash (o'chirish yo'q)
- Ustozlarni boshqarish:
  - Taklif havolasi yaratish
  - Ro'yxat
  - Faol/nofaol qilish
- Ota-onalar bilan ishlash:
  - Invite havolasi yaratish
  - Qayta generatsiya
  - Bog'lanishni uzish
  - "Ulanmagan ota-onalar" ro'yxati
- Davomatni ko'rish va tuzatish (ota-onaga xabarni tanlash shart)

### 2. Ustoz WebApp (Telegram ichida)
- O'z guruhlarini ko'rish (bugungi darslar bilan)
- Bugungi darsni ko'rish (o'quvchilar ro'yxati)
- Davomat belgilash (keldi/kelmadi/kech qoldi)
- Davomat yuborish (Idempotency-Key bilan)
- Natija ekran (nechta xabar navbatda)

### 3. Telegram Bot
- Owner onboarding: /start -> markaz yaratish
- Ustoz onboarding: /start t_TOKEN -> taklifni qabul qilish
- Ota-ona onboarding: /start p_TOKEN -> o'quvchiga bog'lanish
- WebApp tugmasi (rolga qarab)

### 4. Xabar yuborish (Worker)
- Ota-onalarga avtomatik xabar (keldi/kelmadi/kech qoldi)
- Rate limit (global 25/s, chatga 1/s)
- Retry logic (429, network error)
- Failed va blocked holatlarni qayd etish

### 5. Tenant Izolyatsiya
- Har markaz ma'lumotlari alohida
- Ustoz o'z guruhlarini ko'radi
- Admin o'z markazini ko'radi

### 6. Audit Log
- Har yozuvchi amal yoziladi (old/new qiymat)
- Kim, nima qildi, qachon

## MVP ga KIRMAYDIGAN NARSA

### 1. To'lov
- O'quvchi to'lovi
- Hisob-faktura
- Qarzlar
- Oylik to'lov hisoboti

### 2. Hisobotlar
- Davomat statistikasi (oylik, yillik)
- O'quvchi tushishi statistikasi
- Ustoz ish samaradorligi
- Excel eksport
- PDF hisobotlar

### 3. Ovozli/Foydalanuvchi Input
- Ovozli matn yozish
- Voice parsing
- Audio rekordlar

### 4. Murakkab Xususiyatlar
- Kamera orqali yuz aniqlash
- GPS joylashuv tekshiruvi
- Biometrik autentikatsiya
- Multi-language support (faqat o'zbekcha)
- Dark mode (Telegram theme orqali keladi)

### 5. Integratsiyalar
- CRM integratsiyasi
- SMS gateway (faqat Telegram)
- Email xabarlar
- Push notifications (faqat Telegram)

### 6. Avans Xususiyatlar
- Dars jadvali tizimi
- Homework tracking
- Baholash tizimi
- Parent portal (faqat bot)
- Teacher calendar
- Subject/Course boshqaruvi

## MVPdan Keyin (Post-MVP)

Birinchi navbatda:
1. To'lov tizimi
2. Asosiy hisobotlar (davomat foizi, o'quvchi statistikasi)
3. Excel/PDF eksport
4. Kamera/Face ID (agar talab bo'lsa)

## Qaror Qoidasi

Agar quyidagilardan biri bo'lsa:
- Ustoz davomat belgilashda **15 daqiqa** dan ko'proq vaqt sarflaydi → MVP ga kiradi
- Ota-ona **kun oxirida** ham bilmasa → MVP ga kiradi
- Admin **qo'lda** ko'p ish qilishi kerak bo'lsa → MVP ga kiradi
- Pilot davomida **shikoyat** bo'lsa → MVP ga kiradi
- Pilot davomida **sudrab yursa** → MVP ga kirmaydi
