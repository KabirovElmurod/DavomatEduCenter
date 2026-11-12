# User Flows - Davomat Tizimi

## 1. Owner (Markaz Egasi) Oqimi

### 1.1 Ro'yxatdan o'tish
```
User yangi → Botni start qiladi (/start)
           → "Markaz yaratish" oqimi
           → Markaz nomi kiritadi
           → System: User yaratadi (role=owner)
           → System: Center yaratadi (user.owner)
           → System: Owner uchun Admin UI havolasi beradi
           → Owner: Admin UI'ga kiradi (Telegram Login Widget)
           → Dashboard
```

### 1.2 Admin UI'da ishlash
```
Dashboard → Guruhlar yaratish
         → Ustoz taklif havolasi yaratish (t_TOKEN)
         → O'quvchi qo'shish (bitta yoki ommaviy)
         → Ota-ona invite havolasi yaratish (p_TOKEN)
         → Guruh ochish, o'quvchi ko'chirish
         → Davomatni ko'rish va tuzatish
```

### 1.3 Ustoz qo'shish
```
Admin UI → "Ustozlar" sahifasi
        → "Taklif yaratish" tugmasi
        → System: t_TOKEN generatsiya qiladi (24 soat amal qiladi)
        → Admin: t_TOKEN'ni ustozga yuboradi (Telegram/WhatsApp)
        → Ustoz: /start t_TOKEN
        → System: Ustoz yaratadi (role=teacher)
        → Admin UI: Ustoz ro'yxatda ko'rinadi
```

---

## 2. Ustoz (Teacher) Oqimi

### 2.1 Onboarding
```
Ustoz → Invite havolani oladi (t_TOKEN)
      → Botni start qiladi: /start t_TOKEN
      → System: Token tekshiradi (mavjud, muddati, ishlatilmagan)
      → System: User yaratadi (role=teacher, center_id)
      → System: Token'ni ishlatilgan deb belgilaydi
      → Bot: "WebApp'ni ochish" tugmasi ko'rsatadi
      → Ustoz: WebApp'ni ochadi
      → System: initData validatsiya qiladi
      → System: JWT beradi
      → WebApp: Guruhlar ro'yxati
```

### 2.2 Kunlik ish (Davomat)
```
Ustoz → WebApp'ni ochadi
      → Guruhlar ro'yxati (bugungi darslar bilan)
      → Guruhni tanlaydi
      → Bugungi dars + o'quvchilar ro'yxati
      → Holatni belgilaydi (keldi/kelmadi/kech qoldi)
      → "Yuborish" tugmasi
      → System: Davomat + notifications bitta tranzaksiyada
      → System: Worker'ga enqueue
      → System: Natija ekran ("Yuborildi, N ta xabar navbatda")
```

### 2.3 O'tgan davomatni ko'rish
```
Ustoz → WebApp'ni ochadi
      → Guruhni tanlaydi
      → O'tgan darslar ro'yxati
      → Darsni tanlaydi
      → Davomatni ko'radi
```

---

## 3. Ota-ona (Parent) Oqimi

### 3.1 Onboarding (CRITICAL - deep link oqimi)
```
Owner → O'quvchi qo'shadi
      → Ota-ona invite havolasi yaratadi (p_TOKEN)
      → p_TOKEN'ni ota-onaga yuboradi (Telegram/WhatsApp)
      → Ota-ona: t.me/bot?start=p_TOKEN (deep link)
      → Bot: p_TOKEN tekshiradi
      → Bot: "O'quvchi: [ism]. Siz ota-onasi bo'lishni xohlaysizmi?"
      → Ota-ona: "Ha" yoki "Yo'q"
      → Agar "Ha":
          → System: User yaratadi (role=parent)
          → System: ParentLink yaratadi (parent_user_id, student_id)
          → System: Token'ni ishlatilgan deb belgilaydi
          → Bot: "Qo'shildi! Davomat xabarlari shu yerda keladi"
      → Agar "Yo'q":
          → Bot: "Ok, keyinroq qayta urinib ko'ring"
```

### 3.2 Xabarni olish
```
Dars tugadi → Ustoz davomat yuboradi
            → System: Notification yaratadi (status=pending)
            → Worker: Ota-onaga xabar yuboradi
            → Ota-ona: "Farzandingiz: KELDI / KELMADI / KECH QOLDI"
            → System: Notification status=sent
```

### 3.3 Bog'lanishni uzish
```
Ota-ona → Botni block qiladi
       → Worker: 403 error oladi
       → System: Notification status=blocked
       → Admin UI: "Blocked" belgisi ko'rinadi

Yoki

Admin UI → Ota-onani tanlaydi
        → "Bog'lanishni uzish" tugmasi
        → System: ParentLink'ni revoked_at qiladi
        → System: Ota-onaga xabar yubormaydi
```

---

## 4. O'quvchi (Student) Oqimi

### 4.1 Qo'shish
```
Admin UI → "O'quvchi qo'shish"
        → Ism, telefon, guruhni tanlaydi
        → System: Student yaratadi
        → System: StudentGroupHistory yaratadi (from_date=today)
        → Admin: Ota-ona invite havolasi yaratadi
```

### 4.2 Ommaviy qo'shish
```
Admin UI → "Ommaviy qo'shish"
        → Ro'yxatni nusxalab qo'yadi (Ism, Telefon - har qatorda bitta o'quvchi)
        → System: Qatorlarga ajratadi
        → System: Bo'sh va takroriy qatorlarni tozalaydi
        → System: Barcha o'quvchilarni yaratadi
        → System: Har biri uchun StudentGroupHistory yaratadi
        → Admin: Natija (N ta qo'shildi, M ta takroriy o'tkazildi)
```

### 4.3 Ko'chirish
```
Admin UI → O'quvchini tanlaydi
        → "Boshqa guruhga ko'chirish"
        → Yangi guruhni tanlaydi
        → System: StudentGroupHistory yopadi (eski guruh: to_date=today)
        → System: StudentGroupHistory ochadi (yangi guruh: from_date=today)
        → System: Student.group_id = yangi guruh
        → System: AuditLog yozadi
        → Eski davomat o'zgarmaydi
```

### 4.4 Ommaviy ko'chirish
```
Admin UI → Ko'p o'quvchini belgilaydi
        → "Belgilanganlarni ko'chirish"
        → Yangi guruhni tanlaydi
        → System: Barchasi uchun bitta tranzaksiya
        → System: Har biri uchun StudentGroupHistory yopish/ochish
        → System: Agar xato bo'lsa, hammasi rollback
```

---

## 5. Admin UI - Davomat Tuzatish

### 5.1 O'tgan davomatni ko'rish
```
Admin UI → "Darslar" sahifasi
        → Guruhni tanlaydi
        → O'tgan darslar ro'yxati
        → Darsni tanlaydi
        → Davomat jadvali (o'quvchi, holat, ota-ona xabari holati)
```

### 5.2 Davomatni tuzatish
```
Admin UI → O'quvchini tanlaydi
        → Holatni o'zgartiradi (keldi → kelmadi)
        → "Ota-onaga ham xabar yuborilsin" checkbox (default: yo'q)
        → "Saqlash" tugmasi
        → System: Attendance yangilaydi
        → System: AuditLog yozadi
        → Agar checkbox belgilangan bo'lsa:
            → System: Notification yaratadi/yangilaydi
            → Worker: Xabar yuboradi
```

---

## 6. Error Flows

### 6.1 Noto'g'ri Token
```
User → /start t_TOKEN (eski/ishlatilgan/yo'q)
    → System: Token tekshiradi
    → Bot: "Tasdiqlanmagan token. Iltimos, markaz egasidan yangi havola oling"
```

### 6.2 Bot Bloklangan
```
Worker → Ota-onaga xabar yuborish
       → 403 error (user blocked bot)
       → System: Notification status=blocked
       → Admin UI: "Blocked" belgisi
       → Worker: Boshqa notification'larni shu chatga yubormaydi
```

### 6.3 Network Error
```
Worker → Ota-onaga xabar yuborish
       → Network error
       → System: Notification attempts++
       → System: Exponential backoff (1s, 2s, 4s, 8s, 16s)
       → Agar 5 urinishdan keyin ham xato:
           → System: Notification status=failed
           → Admin UI: "Failed" belgisi
           → Reaper cron: Qayta navbatga qo'yadi (2 daqiqadan eski)
```

### 6.4 Rate Limit
```
Worker → 26/s xabar yuborish
       → 429 error (Too Many Requests)
       → System: RetryAfter kutadi
       → System: Token bucket'dan kutadi
       → Keyinroq qayta urinadi
```

---

## 7. Izolyatsiya Flows

### 7.1 Boshqa Markaz Guruhiga Kirish
```
Ustoz A (Markaz 1) → Markaz 2 guruh ID'sini kiritadi
                 → System: groups.teacher_id != current_user.id
                 → System: 403 Forbidden
                 → WebApp: "Siz bu guruhga kirish huquqiga ega emassiz"
```

### 7.2 Boshqa Markaz O'quvchisini Ko'rish
```
Admin A (Markaz 1) → Markaz 2 o'quvchi ID'sini kiritadi
                   → System: students.center_id != current_user.center_id
                   → System: 404 Not Found
                   → Admin UI: "O'quvchi topilmadi"
```

---

## 8. Tenant Switching (Future)

```
User → Bir nechta markazda admin/teacher
     → Admin UI: Markaz tanlash dropdown
     → System: center_id'ni sessiyada saqlaydi
     → System: Barcha query'lar center_id'ga filter qiladi
```

**MVPda:** Single tenant per user (user.center_id)
