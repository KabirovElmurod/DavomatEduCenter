# BotFather Setup - Test va Prod Botlar

## Maqsad

Test va prod uchun alohida 2 ta Telegram bot yaratish.

## Qadamlar

### 1. BotFather'ni Topish
- Telegram'da @BotFather'ni qidiring
- /start buyrug'ini yuboring

### 2. Test Bot Yaratish
```
/newbot
BotFather: Alright, a new bot. How are we going to call it? Please choose a name for your bot.
Siz: Education Center Test Bot
BotFather: Good. Now let's choose a username for your bot. It must end in `bot`. Like this, for example: TetrisBot or tetris_bot.
Siz: education_center_test_bot
BotFather: Done! Congratulations on your new bot.
```

**Test bot tokeni:** 123456789:ABCdefGHIjklMNOpqrSTUvwxYZ (misol)

### 3. Prod Bot Yaratish
```
/newbot
BotFather: Alright, a new bot. How are we going to call it? Please choose a name for your bot.
Siz: Education Center Bot
BotFather: Good. Now let's choose a username for your bot. It must end in `bot`. Like this, for example: TetrisBot or tetris_bot.
Siz: education_center_bot
BotFather: Done! Congratulations on your new bot.
```

**Prod bot tokeni:** 987654321:ZYXwvuTSRqponMLKjiHGfedCBA (misol)

### 4. Bot Sozlamari

#### Test Bot uchun:
```
/setprivacy
BotFather: Choose a bot to change group messages settings.
Siz: @education_center_test_bot
BotFather: 'Enable' - your bot will only receive messages that explicitly start with the '/' character or are mentions of the bot via @username. In group chats this is an essential feature, since bots usually don't need to process all messages. Would you like to enable privacy mode?
Siz: Disable
```

**Eslatma:** Disable - barcha xabarlarni olish kerak (deep link uchun).

#### Prod Bot uchun:
```
/setprivacy
BotFather: Choose a bot to change group messages settings.
Siz: @education_center_bot
BotFather: Would you like to enable privacy mode?
Siz: Disable
```

### 5. Domen Sozlamari (Prod uchun)

Prod bot uchun domen o'rnatish kerak (Telegram Login Widget uchun).

```
/setdomain
BotFather: Choose a bot to change domain settings.
Siz: @education_center_bot
BotFather: OK. Send me a domain name for your bot. Note that this can't be changed later.
Siz: yourdomain.com
BotFather: Success! Domain saved.
```

**Eslatma:** Agar hozircha domen yo'q bo'lsa, keyinroq o'rnatish mumkin.

### 6. Webhook Sozlamari (Keyinroq)

Deploy qilgandan keyin webhook o'rnatish kerak:

```
/setwebhook
BotFather: Choose a bot to change webhook settings.
Siz: @education_center_bot
BotFather: Please send me the new webhook URL.
Siz: https://yourdomain.com/bot/webhook
BotFather: OK!
```

**Eslatma:** Hozircha local development uchun polling ishlatish mumkin.

## Tokenlarni Saqlash

Tokenlarni `.env` faylida saqlang:

```env
# Test
TEST_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ

# Prod
BOT_TOKEN=987654321:ZYXwvuTSRqponMLKjiHGfedCBA
```

**Eslatma:** `.env` faylni git'ga qo'shmang (`.gitignore`'ga qo'shing).

## Bot Username'lari

- Test: @education_center_test_bot
- Prod: @education_center_bot

## Next Steps

1. Tokenlarni `.env.example` fayliga yozing (example tokenlar bilan)
2. Real tokenlarni `.env` fayliga yozing
3. `.env` faylni `.gitignore`'ga qo'shing
4. Bot username'larni hujjatda saqlang
