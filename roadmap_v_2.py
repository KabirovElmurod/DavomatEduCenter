#!/usr/bin/env python3
"""
roadmap.py - Davomat tizimi MVP roadmap boshqaruvchisi (v2: admin panel bilan).

Holat `roadmap_state.json` faylida saqlanadi (skript yonida).

Buyruqlar:
  python roadmap.py init [--force] [--done-upto N]
                                        roadmap hosil qiladi. Default: 1-2 bosqich bajarilgan deb belgilanadi
  python roadmap.py status              umumiy progress + bosqichlar jadvali
  python roadmap.py next [N]            keyingi N ta qadam (default 3) + bosqich mezoni
  python roadmap.py done 3.2 3.3        qadam(lar)ni bajarilgan deb belgilaydi
  python roadmap.py done 3              3-bosqichning hamma qadamini belgilaydi
  python roadmap.py undo 3.2            belgini qaytaradi
  python roadmap.py list [bosqich]      to'liq roadmap (yoki bitta bosqich)
  python roadmap.py completed           bajarilganlar ro'yxati (sana bilan)
  python roadmap.py export              roadmap.md fayliga chiqaradi
  python roadmap.py scaffold [--path D] loyiha papkalari va bo'sh fayllarni yaratadi

Oldingi bosqich tugamay turib keyingisiga o'tishga ruxsat yo'q (--force bilan o'tadi).

ESLATMA: v1 dan o'tayotgan bo'lsangiz, bosqich raqamlari o'zgargan.
Eski roadmap_state.json ishlamaydi: `python roadmap.py init --force` qiling.
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Windows UTF-8 output
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

STATE_FILE = Path(__file__).with_name("roadmap_state.json")
STATE_VERSION = 2

# --------------------------------------------------------------------------
# ROADMAP MA'LUMOTI
# Arxitektura: ustoz = Telegram WebApp (Alpine.js), admin = brauzer (Jinja2 + HTMX)
# --------------------------------------------------------------------------
STAGES = [
    {
        "title": "Mahsulot va scope",
        "days": "1-2",
        "criteria": "Scope yozib qo'yilgan, oqimlar chizilgan, kamida 1 ta pilot markaz bilan kelishilgan",
        "tasks": [
            "MVP scope hujjati: nima kiradi (owner/admin panel, davomat, ota-ona xabari), nima kirmaydi (to'lov, hisobot, ovozli parsing, Excel)",
            "Oqimlar qog'ozda: owner (o'zi ro'yxatdan o'tadi), ustoz (taklif -> davomat), ota-ona (havola -> xabar)",
            "Ota-ona onboarding qotirilgan: ota-ona botni start qilmasa bot yoza olmaydi (deep link oqimi)",
            "3-5 ta o'quv markaz bilan suhbat, 1 ta pilot markaz bilan kelishuv",
        ],
    },
    {
        "title": "Poydevor",
        "days": "1-2",
        "criteria": "`docker compose up` -> /health 200 qaytaradi; HTTPS tunnel/domen orqali tashqaridan ochiladi",
        "tasks": [
            "BotFather: test va prod uchun alohida 2 ta bot",
            "Git repo, pyproject.toml (uv yoki poetry), ruff + mypy + pre-commit",
            "GitHub Actions: lint + test workflow",
            "docker-compose.yml: postgres, redis, api, worker",
            "Dockerfile: Python base image + uv/poetry",
            "core/config.py: pydantic-settings orqali .env",
            "JSON logging + request_id middleware",
            "/health endpoint (DB + Redis tekshiradi)",
            "Domen yoki doimiy cloudflared tunnel (HTTPS; Telegram Login Widget uchun BotFather /setdomain)",
        ],
    },
    {
        "title": "Ma'lumotlar bazasi",
        "days": "3-4",
        "criteria": "Bo'sh DB'da `alembic upgrade head` o'tadi, downgrade ishlaydi, seed ishlaydi, UNIQUE cheklovlar testda tekshirilgan",
        "tasks": [
            "Base, enum'lar (role: owner/admin/teacher/parent; attendance status), timestamptz UTC, created_at mixin",
            "Modellar: centers, users (telegram_id UNIQUE, role, is_active), teachers",
            "Modellar: groups (teacher_id nullable, is_active), students (group_id joriy, is_active)",
            "Modellar: student_group_history (student_id, group_id, from_date, to_date, changed_by)",
            "Modellar: parent_links (invite_token UNIQUE, revoked_at), invites (token UNIQUE, role, expires_at, used_at)",
            "Modellar: lessons (UNIQUE group_id+lesson_date), attendance (UNIQUE lesson_id+student_id)",
            "Modellar: attendance_submissions (idempotency_key UNIQUE)",
            "Modellar: notifications (UNIQUE attendance_id+parent_user_id, status, attempts)",
            "Modellar: audit_log (center_id, actor_id, action, entity, entity_id, old jsonb, new jsonb)",
            "Indekslar: students(group_id), students(center_id,is_active), groups(teacher_id), groups(center_id), parent_links(student_id), notifications(status), audit_log(center_id,created_at), users(telegram_id)",
            "Alembic: birinchi migratsiya (barcha cheklov DB darajasida)",
            "Seed skript: 1 markaz, 1 owner, 2 ustoz, 3 guruh, 30 o'quvchi",
            "Testlar: migratsiya upgrade/downgrade, UNIQUE cheklovlar (takroriy davomat INSERT xato beradi)",
        ],
    },
    {
        "title": "Autentifikatsiya va tenant izolyatsiya",
        "days": "3-4",
        "criteria": "Izolyatsiya testlari yashil (ustoz va admin uchun alohida). Bu bosqichsiz keyingisiga o'tilmaydi",
        "tasks": [
            "Ustoz: initData HMAC-SHA256 validatsiya (WebAppData kaliti) + auth_date 1 soatdan eski bo'lsa rad",
            "POST /api/v1/auth/telegram -> JWT (user_id, role, center_id); ro'yxatda yo'q user -> 403",
            "Admin: Telegram Login Widget hash tekshiruvi",
            "Admin: HttpOnly + SameSite=Lax cookie sessiya + CSRF token",
            "Dependency: get_current_user, require_role('teacher'|'admin'|'owner')",
            "owner/admin ajratish: adminlarni faqat owner qo'sha oladi",
            "Tenant izolyatsiya: repository funksiyalari center_id'ni majburiy oladi (faqat sessiya/JWT'dan); routerda to'g'ridan select yozish taqiqlangan",
            "Ustoz izolyatsiyasi: groups.teacher_id == current teacher",
            "Test: boshqa markaz guruhi/o'quvchisi -> 404/403 (ustoz ham, admin ham)",
            "Test: boshqa ustoz guruhi -> 403",
            "Test: eskirgan/soxta initData -> 401; soxta Login Widget hash -> 401",
        ],
    },
    {
        "title": "Servis qatlami (admin biznes logikasi)",
        "days": "4-5",
        "criteria": "Hamma servis UI'siz testlarda ishlaydi, har yozuvchi amal audit_log'ga tushadi, ko'chirish tarixni buzmaydi",
        "tasks": [
            "audit servisi: har yozuvchi amal old/new qiymat bilan log yozadi",
            "Markaz yaratish (yaratuvchi avtomatik owner)",
            "Invite servisi: ustoz/admin uchun token yaratish va ishlatish (bir martalik, muddatli)",
            "Guruh servisi: yaratish, tahrirlash, arxivlash",
            "Guruh ustozini almashtirish (eski darslar eski ustoz nomida qoladi)",
            "O'quvchi servisi: yaratish, tahrirlash, arxivlash/tiklash (o'chirish yo'q)",
            "Ommaviy qo'shish: matnni qatorlarga ajratish, bo'sh va takroriy qatorlarni tozalash",
            "Ko'chirish: bitta tranzaksiyada student_group_history yopish/ochish + students.group_id yangilash",
            "Ommaviy ko'chirish va guruhlarni birlashtirish (bitta tranzaksiya)",
            "Ota-ona havolasi: yaratish, qayta generatsiya (eskisi revoked_at), bog'lanishni uzish",
            "Ustozni nofaol qilish: guruhlari 'ustozsiz' holatga o'tadi",
            "Test: ko'chirishdan keyin eski davomat o'zgarmaydi",
            "Test: ommaviy ko'chirish yarim yo'lda xato bersa hech narsa o'zgarmaydi (rollback)",
            "Test: har amalda audit yozuvi bor; boshqa markaz ma'lumotiga tegib bo'lmaydi",
        ],
    },
    {
        "title": "Bot va onboarding",
        "days": "3-4",
        "criteria": "Real Telegram akkauntlarda: owner markaz yaratadi, ustoz taklif bilan qo'shiladi, ota-ona ulanadi. Staging serverda ishlaydi",
        "tasks": [
            "aiogram 3 webhook: POST /bot/webhook (secret token bilan)",
            "/start (yangi user): 'Markaz yaratish' oqimi -> owner",
            "/start t_TOKEN: ustoz taklifi (token tekshiruvi: mavjud, muddati, ishlatilmagan)",
            "/start p_TOKEN: ota-ona bog'lash (o'quvchi ismini ko'rsatib tasdiqlatish, tokenni yopish)",
            "Mavjud foydalanuvchi: rolga qarab WebApp tugmasi (MenuButtonWebApp / WebAppInfo)",
            "Webhook idempotent: update_id Redis'da 24 soat",
            "Noto'g'ri/eskirgan/ishlatilgan token uchun tushunarli xabarlar",
            "Bot 403 (bloklangan) ushlash -> parent_links/notification holatiga yozish",
        ],
    },
    {
        "title": "Admin UI (brauzer)",
        "days": "8-10",
        "criteria": "Markaz egasi yordamsiz: ustoz taklif qiladi, guruh ochadi, o'quvchi qo'shadi/ko'chiradi, ota-ona havolasini beradi",
        "tasks": [
            "Jinja2 + HTMX + Pico CSS: layout, navigatsiya, Telegram Login kirish sahifasi",
            "Guruhlar: ro'yxat, yaratish, tahrirlash, arxivlash",
            "Guruh sahifasi: o'quvchilar, ustoz almashtirish, oxirgi 10 dars va davomat foizi",
            "O'quvchilar jadvali: jonli qidiruv (HTMX), filtrlar (guruh, ota-ona ulangan/ulanmagan, faol/arxiv)",
            "O'quvchi qo'shish (bitta) va ommaviy qo'shish (ro'yxatni nusxalab qo'yish)",
            "O'quvchini tahrirlash, arxivlash/tiklash, bitta guruhga biriktirish/almashtirish",
            "Belgilab ommaviy ko'chirish va guruhlarni birlashtirish",
            "Ustozlar: taklif havolasi, ro'yxat, faol/nofaol, 'ustozsiz guruh' belgisi",
            "Ota-onalar: havolani nusxalash/ulashish, qayta generatsiya, bog'lanishni uzish",
            "'Ulanmagan ota-onalar' ko'rinishi + ommaviy havola ro'yxati (o'quvchi - havola)",
            "Xavfli amallar uchun tasdiqlash oynasi; xato va bo'sh holat (empty state) matnlari",
            "Telefonda ochilishi (moslashuvchan jadval)",
            "Admin UI testlari: asosiy oqim smoke test + tenant izolyatsiya",
        ],
    },
    {
        "title": "Ustoz API va WebApp",
        "days": "5-7",
        "criteria": "Bir xil Idempotency-Key bilan 5 ta so'rov -> bazada 1 ta yozuv, 1 to'plam notification; Lighthouse mobil > 90; 4G'da ochilish < 1 s",
        "tasks": [
            "GET /api/v1/me",
            "GET /api/v1/teacher/groups (faqat o'ziniki, bugungi darslar bilan)",
            "GET /api/v1/groups/{id}/lesson/today (dars + o'quvchilar bitta so'rovda)",
            "POST /api/v1/groups/{id}/attendance: Idempotency-Key bilan",
            "Davomat + attendance_submissions + notifications bitta tranzaksiyada (outbox)",
            "Tranzaksiyadan keyin ARQ'ga enqueue (request ichida Telegram chaqiruvi yo'q)",
            "GET davomatni ko'rish endpointi",
            "'Bugun' doim Asia/Tashkent bo'yicha (DB'da UTC)",
            "Idempotentlik testi (5 ta bir xil so'rov, parallel ham)",
            "Vite + Alpine.js loyiha, Telegram theme CSS o'zgaruvchilari",
            "Telegram.WebApp.ready()/expand(), initData -> /auth/telegram -> JWT",
            "Ekran 1: guruhlar ro'yxati (bugungi darslar) + skeleton loader",
            "Ekran 2: davomat (default present, 1 tap holat, 'Hammasi keldi')",
            "MainButton 'Yuborish': darhol disabled, Idempotency-Key bir marta, xatoda o'sha key bilan retry",
            "Ekran 3: natija ('Yuborildi, N ta xabar navbatda')",
            "Bundle < 50KB gzip: CI'da tekshiruv",
            "Haqiqiy telefonda sinov (arzon Android + iPhone)",
        ],
    },
    {
        "title": "Worker va xabar yuborish",
        "days": "3-4",
        "criteria": "500 notification rate limitdan oshmay yetkaziladi; worker o'chib-yoqilsa yo'qolmaydi va ikki marta ketmaydi",
        "tasks": [
            "ARQ worker: send_attendance_notification(notification_id)",
            "FOR UPDATE SKIP LOCKED + atomik UPDATE ... WHERE status='pending' (ikki marta yuborilmasligi)",
            "Xabar matni shakllantirish (keldi/kelmadi/kech qoldi)",
            "Redis token bucket: global <= 25/s, chatga <= 1/s",
            "429 RetryAfter -> kutib qayta navbatga",
            "403 -> blocked, qayta urinmaydi",
            "Tarmoq xatosi -> exponential backoff, max 5 urinish, so'ng failed",
            "Reaper cron (har daqiqa): 2 daqiqadan eski pending'larni qayta navbatga qo'yish",
            "Test: 500 notification drain + worker kill",
        ],
    },
    {
        "title": "Admin: davomatni ko'rish va tuzatish",
        "days": "2-3",
        "criteria": "Admin o'tgan davomatni tuzata oladi, audit yozilgan, ota-onaga xabar faqat tanlansa ketadi",
        "tasks": [
            "O'tgan darslar ro'yxati, guruh bo'yicha davomat foizi",
            "Davomatni tuzatish (audit_log bilan)",
            "Checkbox 'ota-onaga ham xabar yuborilsin' (default: yo'q)",
            "Ota-ona xabarlari holati: yuborildi / xato / bot bloklangan",
            "Test: tuzatish dublikat xabar yaratmaydi, tenant izolyatsiya saqlanadi",
        ],
    },
    {
        "title": "Sinov, xavfsizlik va deploy",
        "days": "4-5",
        "criteria": "p95 maqsadlari bajarilgan, dublikat 0, yo'qolgan xabar 0, backup tiklash sinalgan, prod'da HTTPS ishlaydi",
        "tasks": [
            "Integration testlar to'plami: auth, izolyatsiya, idempotentlik, worker retry, token ishlatish",
            "Locust/k6: 200 ustoz bir vaqtda (~3000 notification)",
            "Metrika: POST attendance p95 < 300 ms, GET today p95 < 200 ms, queue drain ~2 daqiqa, xato 0%",
            "Chaos: worker kill, Redis restart, bir xil so'rov 10x parallel",
            "VPS (Ubuntu), Docker, Compose, ufw (80/443/22), SSH kalit, parol kirish o'chiq",
            "Domen + SSL (Caddy), Telegram webhook va Login domeni prod'ga",
            ".env sirlari faqat serverda; docker restart: unless-stopped",
            "Kunlik pg_dump -> tashqi saqlash",
            "Backup'ni tiklashni bir marta sinab ko'rish",
            "Sentry + UptimeRobot (/health) + log rotation",
            "GitHub Actions deploy: test -> build -> ssh + compose up + alembic upgrade head",
            "SQLAdmin (faqat dasturchi uchun, avariya tuzatishlari)",
        ],
    },
    {
        "title": "Platforma admin (markazlarni boshqarish)",
        "days": "1-2",
        "criteria": "SUPER_ADMIN barcha markazlarni ko'radi va markaz + owner yarata oladi; oddiy admin bu sahifaga kira olmaydi",
        "tasks": [
            "SUPER_ADMIN roli: UserRole enum + users.center_id nullable migratsiya",
            "get_current_admin super_admin'ni ham o'tkazadi; /admin/centers faqat super_admin",
            "Markazlar sahifasi: ro'yxat (nom, owner, guruh/o'quvchi soni), yaratish formasi",
            "Markaz yaratish: Center + owner User birga (CenterService yoki alohida)",
            "Test: super_admin markaz yaratadi; admin/owner /admin/centers -> 403",
        ],
    },
    {
        "title": "Pilot",
        "days": "14",
        "criteria": "Markazlar siz eslatmasangiz ham o'zlari ishlatadi; siz qo'lda hech narsa kiritmagansiz",
        "tasks": [
            "1-2 ta markaz o'zi ro'yxatdan o'tadi (siz qo'lda kiritmaysiz: bu testning o'zi)",
            "Onboarding yordamsiz tugatildimi: kuzatish va to'siqlarni yozib borish",
            "Kunlik monitoring: ota-onalarning necha foizi botni start qildi, failed nisbati, davomat har kun belgilanyaptimi",
            "Haftada 15 daqiqa fikr so'rash (owner va ustozlardan)",
            "Pilot oxiri qarori: nima yetishmaydi (to'lov, hisobot, narx) - faqat pilot ma'lumotiga qarab",
        ],
    },
]

TEXTS = {}
for _si, _st in enumerate(STAGES, 1):
    for _ti, _t in enumerate(_st["tasks"], 1):
        TEXTS[f"{_si}.{_ti}"] = _t

# --------------------------------------------------------------------------
# Yordamchi
# --------------------------------------------------------------------------
os.system("")  # Windows terminalida ANSI ranglarni yoqadi
G, Y, C, D, B, R, X = ("\033[92m", "\033[93m", "\033[96m", "\033[90m", "\033[1m", "\033[91m", "\033[0m")


def iter_tasks():
    for si, st in enumerate(STAGES, 1):
        for ti, text in enumerate(st["tasks"], 1):
            yield f"{si}.{ti}", si, text


def all_ids():
    return [tid for tid, *_ in iter_tasks()]


def load():
    if not STATE_FILE.exists():
        sys.exit(f"{R}Holat fayli yo'q. Avval: python roadmap.py init{X}")
    data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    if data.get("version") != STATE_VERSION:
        sys.exit(
            f"{R}Holat fayli eski roadmap versiyasidan (bosqich raqamlari o'zgargan).{X}\n"
            f"Yangilash: python roadmap.py init --force"
        )
    valid = set(all_ids())
    data["done"] = {k: v for k, v in data.get("done", {}).items() if k in valid}
    return data


def save(data):
    STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def stage_tasks(si):
    return [tid for tid, s, _ in iter_tasks() if s == si]


def stage_done_count(data, si):
    return sum(1 for t in stage_tasks(si) if t in data["done"])


def stage_complete(data, si):
    return stage_done_count(data, si) == len(stage_tasks(si))


def current_stage(data):
    for si in range(1, len(STAGES) + 1):
        if not stage_complete(data, si):
            return si
    return None


def bar(done, total, width=24):
    filled = int(width * done / total) if total else 0
    return "█" * filled + "░" * (width - filled)


def parse_ids(tokens):
    ids, valid = [], set(all_ids())
    for tok in tokens:
        if tok in valid:
            ids.append(tok)
        elif tok.isdigit() and 1 <= int(tok) <= len(STAGES):
            ids.extend(stage_tasks(int(tok)))
        else:
            sys.exit(f"{R}Noma'lum id: {tok}{X} (masalan: 3.2 yoki 3)")
    return ids


# --------------------------------------------------------------------------
# Buyruqlar
# --------------------------------------------------------------------------
def cmd_init(args):
    if STATE_FILE.exists() and not args.force:
        sys.exit(f"{Y}Holat allaqachon bor. Noldan boshlash uchun: init --force{X}")
    now = datetime.now().isoformat(timespec="seconds")
    upto = max(0, min(args.done_upto, len(STAGES)))
    done = {}
    for si in range(1, upto + 1):
        for tid in stage_tasks(si):
            done[tid] = now
    save({"version": STATE_VERSION, "created": now, "done": done})
    total = len(all_ids())
    print(f"{G}Roadmap hosil qilindi:{X} {len(STAGES)} bosqich, {total} qadam.")
    if upto:
        print(f"{G}1-{upto} bosqichlar bajarilgan deb belgilandi.{X}")
    print("Keyingi qadamni ko'rish: python roadmap.py next")


def cmd_status(args):
    data = load()
    total, done = len(all_ids()), len(data["done"])
    print(f"\n{B}UMUMIY:{X} {bar(done, total)} {done}/{total} ({done * 100 // total}%)\n")
    cur = current_stage(data)
    for si, st in enumerate(STAGES, 1):
        d, t = stage_done_count(data, si), len(stage_tasks(si))
        if d == t:
            mark, col = "✔", G
        elif si == cur:
            mark, col = "▶", Y
        else:
            mark, col = " ", D
        print(f"{col}{mark} {si:>2}. {st['title']:<40} {bar(d, t, 12)} {d:>2}/{t:<2} ({st['days']} kun){X}")
    print()
    if cur is None:
        print(f"{G}{B}Hammasi tugadi. MVP tayyor.{X}")
    else:
        print(f"Hozirgi bosqich: {Y}{cur}. {STAGES[cur - 1]['title']}{X}")


def cmd_next(args):
    data = load()
    cur = current_stage(data)
    if cur is None:
        return print(f"{G}{B}Hammasi tugadi.{X}")
    st = STAGES[cur - 1]
    print(f"\n{B}BOSQICH {cur}: {st['title']}{X}  {D}({stage_done_count(data, cur)}/{len(stage_tasks(cur))}){X}")
    pending = [(tid, txt) for tid, s, txt in iter_tasks() if s == cur and tid not in data["done"]]
    for i, (tid, txt) in enumerate(pending[: args.count]):
        arrow = f"{Y}▶ KEYINGISI{X}" if i == 0 else "  keyin     "
        print(f"  {arrow} {C}{tid}{X}  {txt}")
    if len(pending) > args.count:
        print(f"  {D}... yana {len(pending) - args.count} ta qadam{X}")
    print(f"\n{B}Tayyor mezoni:{X} {st['criteria']}")
    print(f"{D}Belgilash: python roadmap.py done {pending[0][0]}{X}\n")


def cmd_done(args):
    data = load()
    ids = parse_ids(args.ids)
    cur = current_stage(data)
    for tid in ids:
        si = int(tid.split(".")[0])
        if cur is not None and si > cur and not args.force:
            print(f"{R}✘ {tid}: {cur}-bosqich tugamagan. Keyingisiga o'tib bo'lmaydi (--force bilan mumkin).{X}")
            continue
        if tid in data["done"]:
            print(f"{D}• {tid} allaqachon bajarilgan{X}")
            continue
        data["done"][tid] = datetime.now().isoformat(timespec="seconds")
        print(f"{G}✔ {tid}{X}  {TEXTS[tid]}")
        cur = current_stage(data)
    save(data)
    for si in range(1, len(STAGES) + 1):
        if stage_complete(data, si) and any(t.startswith(f"{si}.") for t in ids):
            print(f"\n{G}{B}★ {si}-bosqich tugadi: {STAGES[si - 1]['title']}{X}")
            print(f"  Mezonni tekshiring: {STAGES[si - 1]['criteria']}")
    print()
    cmd_next(argparse.Namespace(count=3))


def cmd_undo(args):
    data = load()
    for tid in parse_ids(args.ids):
        if data["done"].pop(tid, None):
            print(f"{Y}↩ {tid} qaytarildi{X}")
        else:
            print(f"{D}• {tid} bajarilmagan edi{X}")
    save(data)


def cmd_list(args):
    data = load()
    stages = [args.stage] if args.stage else range(1, len(STAGES) + 1)
    for si in stages:
        if not 1 <= si <= len(STAGES):
            sys.exit(f"{R}Bosqich 1..{len(STAGES)} oralig'ida bo'lsin{X}")
        st = STAGES[si - 1]
        print(f"\n{B}{si}. {st['title']}{X}  {D}({st['days']} kun){X}")
        for tid in stage_tasks(si):
            if tid in data["done"]:
                print(f"  {G}[x] {tid:<5} {TEXTS[tid]}{X}")
            else:
                print(f"  [ ] {C}{tid:<5}{X} {TEXTS[tid]}")
        print(f"  {D}Mezon: {st['criteria']}{X}")
    print()


def cmd_completed(args):
    data = load()
    if not data["done"]:
        return print(f"{D}Hali hech narsa bajarilmagan.{X}")
    items = sorted(data["done"].items(), key=lambda kv: kv[1])
    print(f"\n{B}BAJARILGANLAR ({len(items)}):{X}")
    for tid, ts in items:
        print(f"  {G}✔{X} {ts.replace('T', ' ')}  {C}{tid:<5}{X} {TEXTS[tid]}")
    print()


def cmd_export(args):
    data = load()
    lines = ["# MVP Roadmap\n"]
    for si, st in enumerate(STAGES, 1):
        lines.append(f"## {si}. {st['title']} ({st['days']} kun)\n")
        for tid in stage_tasks(si):
            lines.append(f"- [{'x' if tid in data['done'] else ' '}] **{tid}** {TEXTS[tid]}")
        lines.append(f"\n**Tayyor mezoni:** {st['criteria']}\n")
    out = Path(__file__).with_name("roadmap.md")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"{G}Yozildi:{X} {out}")


# --------------------------------------------------------------------------
# Scaffold: loyiha papkalari va bo'sh fayllar
# --------------------------------------------------------------------------
MODELS = [
    "center", "user", "group", "student", "student_group_history",
    "parent_link", "invite", "lesson", "attendance", "attendance_submission",
    "notification", "audit_log",
]
SERVICES = [
    "audit", "center", "invite", "group", "student", "transfer",
    "parent_link", "teacher", "attendance", "notification",
]

SCAFFOLD = {
    "app/__init__.py": "",
    "app/main.py": "# FastAPI ilova kirish nuqtasi (2-bosqich)\n",
    "app/core/__init__.py": "",
    "app/core/config.py": "# pydantic-settings (2-bosqich)\n",
    "app/core/logging.py": "# JSON logging + request_id (2-bosqich)\n",
    "app/core/db.py": "# async engine + session (3-bosqich)\n",
    "app/core/security.py": "# initData HMAC, JWT, Login Widget hash, CSRF (4-bosqich)\n",
    "app/core/deps.py": "# get_current_user, require_role (4-bosqich)\n",
    "app/core/timezone.py": "# 'bugun' = Asia/Tashkent, DB = UTC (8-bosqich)\n",
    "app/models/__init__.py": "",
    "app/models/base.py": "# Base, enum'lar, mixin'lar (3-bosqich)\n",
    "app/repositories/__init__.py": "# center_id majburiy query'lar (4-bosqich)\n",
    "app/services/__init__.py": "",
    "app/schemas/__init__.py": "",
    "app/api/__init__.py": "",
    "app/api/v1/__init__.py": "",
    "app/api/v1/health.py": "# /health (2-bosqich)\n",
    "app/api/v1/auth.py": "# POST /auth/telegram (4-bosqich)\n",
    "app/api/v1/teacher.py": "# me, teacher/groups, lesson/today (8-bosqich)\n",
    "app/api/v1/attendance.py": "# POST/GET attendance, idempotent (8-bosqich)\n",
    "app/admin/__init__.py": "",
    "app/admin/router_auth.py": "# Telegram Login, cookie sessiya (4, 7-bosqich)\n",
    "app/admin/router_groups.py": "# guruhlar (7-bosqich)\n",
    "app/admin/router_students.py": "# o'quvchilar, ommaviy qo'shish/ko'chirish (7-bosqich)\n",
    "app/admin/router_teachers.py": "# ustozlar, takliflar (7-bosqich)\n",
    "app/admin/router_parents.py": "# ota-ona havolalari (7-bosqich)\n",
    "app/admin/router_lessons.py": "# davomat ko'rish/tuzatish (10-bosqich)\n",
    "app/admin/templates/base.html": "<!-- Pico CSS + HTMX layout (7-bosqich) -->\n",
    "app/admin/static/.gitkeep": "",
    "app/bot/__init__.py": "",
    "app/bot/webhook.py": "# aiogram webhook (6-bosqich)\n",
    "app/bot/handlers.py": "# /start, t_TOKEN, p_TOKEN (6-bosqich)\n",
    "app/worker/__init__.py": "",
    "app/worker/settings.py": "# ARQ WorkerSettings (9-bosqich)\n",
    "app/worker/tasks.py": "# send_attendance_notification, reaper (9-bosqich)\n",
    "scripts/seed.py": "# seed: 1 markaz, 1 owner, 2 ustoz, 3 guruh, 30 o'quvchi (3-bosqich)\n",
    "webapp/src/.gitkeep": "",
    "migrations/.gitkeep": "",
    "tests/__init__.py": "",
    "tests/test_health.py": "# 2-bosqich\n",
    "tests/test_models.py": "# UNIQUE cheklovlar, migratsiya (3-bosqich)\n",
    "tests/test_auth.py": "# initData, Login Widget (4-bosqich)\n",
    "tests/test_isolation.py": "# tenant va ustoz izolyatsiyasi (4-bosqich)\n",
    "tests/test_services.py": "# ko'chirish, ommaviy, audit (5-bosqich)\n",
    "tests/test_idempotency.py": "# 8-bosqich\n",
    "tests/test_worker.py": "# 429/403/retry (9-bosqich)\n",
    "docker-compose.yml": "# postgres, redis, api, worker (2-bosqich)\n",
    "Dockerfile": "# 2-bosqich\n",
    ".env.example": "# DATABASE_URL=\n# REDIS_URL=\n# BOT_TOKEN=\n# BOT_WEBHOOK_SECRET=\n# JWT_SECRET=\n# SESSION_SECRET=\n# PUBLIC_URL=\n",
    ".gitignore": ".env\n__pycache__/\n.venv/\nnode_modules/\ndist/\nroadmap_state.json.bak\n",
    "README.md": "# Davomat tizimi\n\nRoadmap: `python roadmap.py status`\n",
    "pyproject.toml": "# Python dependency management (2-bosqich)\n",
    ".github/workflows/ci.yml": "# GitHub Actions: lint + test (2-bosqich)\n",
}
for _m in MODELS:
    SCAFFOLD[f"app/models/{_m}.py"] = ""
for _s in SERVICES:
    SCAFFOLD[f"app/services/{_s}.py"] = ""
    SCAFFOLD[f"app/repositories/{_s}.py"] = ""


def cmd_scaffold(args):
    root = Path(args.path) if args.path else Path(__file__).parent
    created = skipped = 0
    for rel, content in SCAFFOLD.items():
        f = root / rel
        if f.exists():
            skipped += 1
            continue
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content, encoding="utf-8")
        created += 1
    print(f"{G}Papkalar hosil qilindi:{X} {root.resolve()}")
    print(f"  yangi fayl: {created}, mavjud (tegilmadi): {skipped}\n")
    dirs = sorted({str(Path(r).parent).replace("\\", "/") for r in SCAFFOLD if "/" in r})
    top = sorted({d.split("/")[0] for d in dirs})
    for t in top:
        print(f"  {C}{t}/{X}")
        for d in dirs:
            if d.startswith(t + "/"):
                print(f"    {d[len(t) + 1:]}/")


def main():
    p = argparse.ArgumentParser(description="MVP roadmap boshqaruvchisi")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init")
    s.add_argument("--force", action="store_true")
    s.add_argument("--done-upto", type=int, default=2, help="shu bosqichgacha bajarilgan deb belgilash (default 2)")
    s.set_defaults(fn=cmd_init)
    s = sub.add_parser("status"); s.set_defaults(fn=cmd_status)
    s = sub.add_parser("next"); s.add_argument("count", nargs="?", type=int, default=3); s.set_defaults(fn=cmd_next)
    s = sub.add_parser("done"); s.add_argument("ids", nargs="+"); s.add_argument("--force", action="store_true"); s.set_defaults(fn=cmd_done)
    s = sub.add_parser("undo"); s.add_argument("ids", nargs="+"); s.set_defaults(fn=cmd_undo)
    s = sub.add_parser("list"); s.add_argument("stage", nargs="?", type=int); s.set_defaults(fn=cmd_list)
    s = sub.add_parser("completed"); s.set_defaults(fn=cmd_completed)
    s = sub.add_parser("export"); s.set_defaults(fn=cmd_export)
    s = sub.add_parser("scaffold"); s.add_argument("--path"); s.set_defaults(fn=cmd_scaffold)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()