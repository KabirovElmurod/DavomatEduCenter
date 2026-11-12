# Ota-ona Onboarding - Critical Flow

## Muammo

Agar ota-ona botni **manual** start qilmasa, bot hech qachon yubora olmaydi.

**Yomon UX:**
- Admin: "Botni qidir: @education_bot, start qiling"
- Ota-ona: Nima? Qayerda? Nima qilish kerak?
- Natija: 70% ota-ona botni start qilmaydi

**Yaxshi UX:**
- Admin: "Bu havolani bosing: t.me/education_bot?start=p_TOKEN"
- Ota-ona: Havolani bosadi → Bot avtomatik ochiladi
- Natija: 95%+ ota-ona botni start qiladi

## Yechim: Deep Link Onboarding

### 1. Admin UI'da Invite Yaratish

```
Admin UI → O'quvchi sahifasi
        → "Ota-ona invite" tugmasi
        → System: p_TOKEN generatsiya qiladi (random string, 36 chars)
        → System: ParentInvite yaratadi:
            - student_id
            - token: p_TOKEN
            - expires_at: 7 kun keyin
            - used_at: null
        → Admin UI: "Havolani nusxalash" tugmasi
        → Admin UI: QR code (ixtiyoriy)
```

### 2. Havola Format

```
t.me/YOUR_BOT?start=p_TOKEN

Misol:
t.me/education_center_bot?start=p_abc123def456...
```

**Eslatma:** BotFather'dan `/setdomain` buyrug'i orqali domen o'rnatish kerak (Telegram Login Widget uchun ham).

### 3. Ota-ona Tashrif Qiladi

#### Scenario A: Yangi User (botda yo'q)
```
Ota-ona → t.me/bot?start=p_TOKEN
        → Telegram: Botni ochadi (start parametri bilan)
        → Bot: start parametrini oladi
        → Bot: p_TOKEN tekshiradi
            - Token mavjudmi?
            - Token muddati tugamaganmi?
            - Token ishlatilmaganmi?
        → Bot: Token valid → O'quvchi ma'lumotlarini oladi
        → Bot: "Farzandingiz: [Ism]. Siz ota-onasi bo'lishni xohlaysizmi?"
        → Ota-ona: "Ha" yoki "Yo'q"
```

**Agar "Ha":**
```
Bot → System: User yaratadi (role=parent)
Bot → System: ParentLink yaratadi (parent_user_id, student_id)
Bot → System: ParentInvite.used_at = now
Bot → "Qo'shildi! Davomat xabarlari shu yerda keladi"
Bot → Menyuga WebApp tugmasi qo'yadi (agar kerak bo'lsa)
```

**Agar "Yo'q":**
```
Bot → "Ok, keyinroq qayta urinib ko'ring"
Bot → Token ishlatilmagan qoladi
```

#### Scenario B: Mavjud User (botda bor)
```
Ota-ona → t.me/bot?start=p_TOKEN
        → Bot: start parametrini oladi
        → Bot: p_TOKEN tekshiradi
        → Bot: Token valid
        → Bot: "Farzandingiz: [Ism]. Siz ota-onasi bo'lishni xohlaysizmi?"
        → Ota-ona: "Ha"
        → Bot: User role'ni parent qiladi (agar boshqa role bo'lsa, error)
        → Bot: ParentLink yaratadi
        → Bot: ParentInvite.used_at = now
```

#### Scenario C: Noto'g'ri Token
```
Ota-ona → t.me/bot?start=p_INVALID_TOKEN
        → Bot: Token tekshiradi
        → Bot: Token invalid (yo'q, muddati tugagan, ishlatilgan)
        → Bot: "Tasdiqlanmagan token. Iltimos, markaz egasidan yangi havola oling"
```

### 4. Token Xavfsizligi

**Token format:** `p_<random_36_chars>`

**Muddat:** 7 kun (configurable)

**Bir martalik:** `used_at` belgilangandan keyin ishlatilmaydi

**Example:**
```python
token = f"p_{secrets.token_urlsafe(27)}"  # 36 chars total
```

### 5. Admin UI'da Invite Qayta Generatsiya

```
Admin UI → O'quvchi sahifasi
        → "Ota-ona invite" tugmasi
        → Agar mavjud bo'lsa:
            → "Qayta generatsiya" tugmasi
            → System: Eski ParentInvite.revoked_at = now
            → System: Yangi ParentInvite yaratadi
            → System: Yangi token
        → Agar mavjud bo'lmasa:
            → "Invite yaratish" tugmasi
            → System: ParentInvite yaratadi
```

### 6. Admin UI'da Bog'lanishni Uzish

```
Admin UI → O'quvchi sahifasi
        → "Ota-onalar" ro'yxati
        → Ota-onani tanlaydi
        → "Bog'lanishni uzish" tugmasi
        → System: ParentLink.active = false
        → System: AuditLog yozadi
        → Bot: Shu chatga xabar yubormaydi
```

### 7. Botda Menyu Tugmasi

**Parentlar uchun:**
- Agar admin panel kerak bo'lsa: MenuButtonWebApp
- Agar kerak bo'lmasa: Oddiy menu ("Mening farzandlarim", "Yordam")

**Ustozlar uchun:**
- WebApp tugmasi (davomat uchun)

**Owner uchun:**
- Admin UI tugmasi

## Implementation Checklist

### Backend
- [ ] ParentInvite model (token, expires_at, used_at, revoked_at)
- [ ] ParentLink model (parent_user_id, student_id, active)
- [ ] Invite servisi (token yaratish, qayta generatsiya)
- [ ] Bot handler: /start p_TOKEN
- [ ] Token validatsiya (mavjud, muddat, ishlatilmagan)
- [ ] Parent onboarding confirm dialog
- [ ] User role update (agar kerak bo'lsa)

### Admin UI
- [ ] "Ota-ona invite" tugmasi
- [ ] Havola nusxalash (clipboard)
- [ ] QR code generation (ixtiyoriy)
- [ ] "Qayta generatsiya" tugmasi
- [ ] "Bog'lanishni uzish" tugmasi
- [ ] Ota-onalar ro'yxati (ulangan/ulanmagan)

### Bot
- [ ] /start handler (deep link parametri)
- [ ] Token validatsiya
- [ ] Confirm dialog (inline keyboard)
- [ ] Error messages (noto'g'ri token)
- [ ] Menu button (rolga qarab)

## Success Metrics

- **Invite click rate:** 90%+ (ota-onalar havolani bosadi)
- **Bot start rate:** 95%+ (havola bosganlar botni start qiladi)
- **Confirmation rate:** 80%+ (start qilganlar "Ha" deydi)
- **Overall conversion:** 70%+ (admin invite beradi → ota-ona ulanadi)

## Edge Cases

### 1. Token eskirgan
```
Ota-ona → t.me/bot?start=p_OLD_TOKEN
        → Bot: Token expired
        → Bot: "Havola eskirgan. Iltimos, markaz egasidan yangi havola oling"
```

### 2. Token ishlatilgan
```
Ota-ona → t.me/bot?start=p_USED_TOKEN
        → Bot: Token already used
        → Bot: "Siz allaqachon ulangansiz. Davomat xabarlari shu yerda keladi"
```

### 3. Boshqa ota-ona ulanmoqchi
```
Ota-ona A → t.me/bot?start=p_TOKEN (student 1)
          → System: ParentLink topildi (parent B)
          → Bot: "Bu o'quvchiga boshqa ota-ona ulangan. Iltimos, markaz egasiga murojaat qiling"
```

### 4. Ota-ona boshqa markazda parent
```
Ota-ona A (Markaz 1) → t.me/bot?start=p_TOKEN (Markaz 2)
                      → System: User.center_id != token.center_id
                      → Bot: "Siz boshqa markazda ota-onasiz. Bitta markazda bo'lish mumkin"
```

**MVP qarori:** Single tenant per parent (ota-ona bitta markazda parent bo'lishi mumkin)

## Alternative Solutions (Rejected)

### 1. Manual Bot Search
- ❌ Yomon UX
- ❌ 70%+ ota-ona start qilmaydi

### 2. WhatsApp Link
- ❌ WhatsApp API qimmat
- ❌ Bot integration murakkab

### 3. SMS Link
- ❌ SMS gateway qimmat
- ❌ International SMS muammolari

### 4. Email Link
- ❌ Email check frequency past
- ❌ Spam folder risk

**Chosen:** Telegram Deep Link (bepul, native, 95%+ conversion)
