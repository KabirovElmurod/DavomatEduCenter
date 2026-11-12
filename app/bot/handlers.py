"""
Bot handlers (roadmap 6.2-6.5)

/start komandasi:
- Yangi user: markaz yaratish oqimi
- t_TOKEN: ustoz taklifi
- p_TOKEN: ota-ona bog'lash
- Mavjud user: rolga qarab WebApp tugmasi
"""

from aiogram import Bot, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.core.logging import get_logger
from app.core.urls import center_url
from app.models.base import UserRole
from app.models.user import User
from app.services.invite import InviteService
from app.services.login_token import create_login_token
from app.services.parent_link import ParentLinkService

logger = get_logger(__name__)

router = Router()


async def set_webapp_button(bot: Bot, user: User) -> None:
    """
    WebApp tugmasini o'rnatish (MenuButtonWebApp).

    Owner/Teacher/Admin uchun davomat WebApp'ga ochadi.
    """
    base = settings.PUBLIC_URL.rstrip("/")
    if user.center_id:
        from app.models.center import Center

        async with AsyncSessionLocal() as s:
            center = await s.get(Center, user.center_id)
        if center and center.subdomain:
            base = center_url(center.subdomain)
    webapp_url = f"{base}/webapp?token={user.telegram_id}"
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="📊 Davomat",
            web_app=WebAppInfo(url=webapp_url),
        )
    )
    logger.info("WebApp tugmasi o'rnatildi", user_id=user.id, telegram_id=user.telegram_id)


async def get_db_session() -> AsyncSession:
    """Async session yaratish"""
    async with AsyncSessionLocal() as session:
        yield session


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """
    /start komandasi

    1. Argument yo'q: yangi user - markaz yaratish oqimi
    2. t_TOKEN: ustoz taklifi
    3. p_TOKEN: ota-ona bog'lash
    4. Mavjud user: rolga qarab WebApp tugmasi
    """
    arg = message.text.split()[1] if len(message.text.split()) > 1 else None
    telegram_id = message.from_user.id
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    username = message.from_user.username

    async with AsyncSessionLocal() as session:
        # Check if user exists globally (not tenant-isolated)
        from sqlalchemy import select

        from app.models.user import User

        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        # Handler based on argument
        if arg is None:
            # No argument - check if user exists
            if user:
                await handle_existing_user(message, user, session)
            else:
                await handle_new_user(
                    message, telegram_id, first_name, last_name, username, session
                )
        elif arg.startswith("t_"):
            # Teacher invite
            await handle_teacher_invite(
                message, arg, telegram_id, first_name, last_name, username, session
            )
        elif arg.startswith("p_"):
            # Parent link
            await handle_parent_link(message, arg, telegram_id, session)
        else:
            await message.answer("❌ Noto'g'ri havola. Iltimos, administrator bilan bog'laning.")


async def handle_new_user(
    message: Message,
    telegram_id: int,
    first_name: str,
    last_name: str | None,
    username: str | None,
    session: AsyncSession,
) -> None:
    """
    Yangi foydalanuvchi - markaz yaratish oqimi.

    MVPda oddiy: "Iltimos, administrator bilan bog'laning"
    Keyinchalik: onboarding flow
    """
    await message.answer(
        "👋 Assalomu alaykum!\n\n"
        "Davomat tizimiga xush kelibsiz.\n\n"
        f"Sizning Telegram ID: <code>{telegram_id}</code>\n\n"
        "Tizimdan foydalanish uchun o'quv markazingiz administratori "
        "bilan bog'laning va taklif havolasini oling.\n\n"
        "Agar siz markaz egasi bo'lsangiz, ushbu ID'ni administratorga yuboring."
    )


async def _center_name(session: AsyncSession, center_id: int | None) -> str | None:
    """Markaz nomini olish"""
    if center_id is None:
        return None
    from app.models.center import Center

    center = await session.get(Center, center_id)
    return center.name if center else None


async def _teacher_groups(session: AsyncSession, user: User) -> list[str]:
    """Ustozning faol guruh nomlari"""
    from sqlalchemy import select

    from app.models.group import Group
    from app.models.teacher import Teacher

    t = (
        await session.execute(select(Teacher).where(Teacher.user_id == user.id))
    ).scalar_one_or_none()
    if t is None:
        return []
    rows = (
        await session.execute(
            select(Group.name)
            .where(Group.teacher_id == t.id, Group.is_active.is_(True))
            .order_by(Group.name)
        )
    ).all()
    return [r[0] for r in rows]


async def _parent_children(session: AsyncSession, user: User) -> list[dict]:
    """Ota-onaning bolalari: ism, markaz, guruh, ustoz"""
    from sqlalchemy import select

    from app.models.center import Center
    from app.models.group import Group
    from app.models.parent_link import ParentLink
    from app.models.student import Student
    from app.models.teacher import Teacher

    stmt = (
        select(
            Student.name,
            Center.name.label("center_name"),
            Group.name.label("group_name"),
            User.first_name.label("teacher_first"),
            User.last_name.label("teacher_last"),
        )
        .join(ParentLink, ParentLink.student_id == Student.id)
        .outerjoin(Center, Student.center_id == Center.id)
        .outerjoin(Group, Student.group_id == Group.id)
        .outerjoin(Teacher, Group.teacher_id == Teacher.id)
        .outerjoin(User, Teacher.user_id == User.id)
        .where(ParentLink.user_id == user.id, ParentLink.revoked_at.is_(None))
        .order_by(Student.name)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "name": r.name,
            "center_name": r.center_name,
            "group_name": r.group_name,
            "teacher_name": " ".join(
                x for x in [r.teacher_first, r.teacher_last] if x
            )
            or None,
        }
        for r in rows
    ]


async def handle_existing_user(message: Message, user: User, session: AsyncSession) -> None:
    """
    Mavjud foydalanuvchi - rolga qarab mos ma'lumot + WebApp tugmasi.

    Owner/Admin: markaz nomi + admin login linki
    SuperAdmin: platforma administratori + login linki
    Teacher: markaz + guruhlar + WebApp tugmasi
    Parent: bolalar (markaz, guruh, ustoz bilan)
    """
    center_name = await _center_name(session, user.center_id)

    if user.role in (UserRole.OWNER, UserRole.ADMIN):
        text = (
            f"👋 Assalomu alaykum, {user.first_name}!\n\n"
            f"Sizning rolingiz: {user.role.value}"
        )
        if center_name:
            text += f"\nO'quv markaz: {center_name}"
        text += "\n\nDavomatni belgilash uchun quyidagi tugmani bosing."
        await message.answer(text)
        await set_webapp_button(message.bot, user)
        await _send_admin_login_link(message, user, session)

    elif user.role == UserRole.SUPER_ADMIN:
        await message.answer(
            f"👋 Assalomu alaykum, {user.first_name}!\n\n"
            "Sizning rolingiz: super_admin (platforma administratori)\n\n"
            "Barcha o'quv markazlarni admin panel orqali boshqarasiz."
        )
        await _send_admin_login_link(message, user, session)

    elif user.role == UserRole.TEACHER:
        parts = [
            f"👋 Assalomu alaykum, {user.first_name}!\n\n",
            "Sizning rolingiz: teacher",
        ]
        if center_name:
            parts.append(f"\nO'quv markaz: {center_name}")
        groups = await _teacher_groups(session, user)
        if groups:
            parts.append(f"\nSizning guruhlaringiz: {', '.join(groups)}")
        else:
            parts.append("\nHali sizga birorta guruh biriktirilmagan.")
        parts.append("\n\nDavomatni belgilash uchun quyidagi tugmani bosing.")
        await message.answer("".join(parts))
        await set_webapp_button(message.bot, user)
    elif user.role == UserRole.PARENT:
        children = await _parent_children(session, user)
        if children:
            lines = [
                f"👋 Assalomu alaykum, {user.first_name}!\n\n",
                f"Sizda {len(children)} ta bola ulangan:\n",
            ]
            for c in children:
                detail = c["center_name"] or "-"
                if c["group_name"]:
                    detail += f", guruh: {c['group_name']}"
                if c["teacher_name"]:
                    detail += f", ustoz: {c['teacher_name']}"
                lines.append(f"• {c['name']} — {detail}\n")
            lines.append(
                "\nDavomat ma'lumotlari bot orqali yuboriladi.\n"
                "Yana bola ulash uchun yangi havolani bosing."
            )
            await message.answer("".join(lines))
        else:
            await message.answer(
                f"👋 Assalomu alaykum, {user.first_name}!\n\n"
                "Siz ota-ona sifatida ulangansiz, lekin hali birorta "
                "bola ulanmagan. Administratordan havola oling."
            )
    else:
        await message.answer("❌ Noma'lum rol. Iltimos, administrator bilan bog'laning.")


async def _send_admin_login_link(
    message: Message, user: User, session: AsyncSession
) -> None:
    """
    Owner/admin/super_admin uchun bir martalik admin panel login linki.

    Token Redis'da 10 daqiqa saqlanadi va bir marta ishlatiladi.
    Link markazning o'z subdomain'iga yo'naltiriladi.
    """
    try:
        token = await create_login_token(user.id)
    except Exception as e:
        logger.warning("Login token yaratilmadi", error=str(e), user_id=user.id)
        return
    center = None
    if user.center_id:
        from app.models.center import Center

        center = await session.get(Center, user.center_id)
    url = f"{center_url(center.subdomain if center else None)}/admin/login-link?token={token}"
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔑 Admin panelga kirish", url=url)]
        ]
    )
    await message.answer(
        "Admin panelga kirish uchun quyidagi tugmani bosing "
        "(havola 10 daqiqa amal qiladi, bir martalik):",
        reply_markup=keyboard,
    )


async def handle_teacher_invite(
    message: Message,
    token: str,
    telegram_id: int,
    first_name: str,
    last_name: str | None,
    username: str | None,
    session: AsyncSession,
) -> None:
    """
    Ustoz taklifi (t_TOKEN).

    Token tekshiruvi: mavjud, muddati, ishlatilmagan.
    User yaratish va WebApp tugmasi o'rnatish.
    """
    invite_service = InviteService(session)
    result = await invite_service.use(token, telegram_id, first_name, last_name, username)

    if result is None:
        await message.answer(
            "❌ Taklif havolasi noto'g'ri yoki muddati tugagan.\n\n"
            "Iltimos, administrator bilan bog'laning va yangi havola oling."
        )
        return

    invite, user_data = result

    # User allaqachon ro'yxatda bo'lsa — taklifni qayta ishlatib bo'lmaydi
    from sqlalchemy import select

    from app.models.user import User

    stmt = select(User).where(User.telegram_id == user_data["telegram_id"])
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        invite.used_at = None  # tokenni qaytarish
        await session.commit()
        await message.answer(
            "❌ Bu Telegram akkaunt allaqachon ro'yxatda.\n\n"
            "Agar siz ustoz bo'lsangiz, administrator bilan bog'laning."
        )
        return

    # Create user
    user = User(
        telegram_id=user_data["telegram_id"],
        first_name=user_data["first_name"],
        last_name=user_data["last_name"],
        username=user_data["username"],
        role=user_data["role"],
        center_id=user_data["center_id"],
        is_active=True,
    )
    session.add(user)
    await session.flush()

    # Teacher roli uchun Teacher profili ham yaratiladi
    # (aks holda WebApp/API teacher konteksti topilmaydi)
    if user_data["role"] == UserRole.TEACHER:
        from app.models.teacher import Teacher

        session.add(Teacher(user_id=user.id, is_active=True))

    await session.commit()

    logger.info(
        "Ustoz qo'shildi",
        telegram_id=telegram_id,
        center_id=user_data["center_id"],
        role=user_data["role"].value,
    )

    await message.answer(
        f"🎉 Tabriklaymiz!\n\n"
        f"Siz '{user_data['role'].value}' sifatida qo'shildingiz.\n\n"
        "Davomatni belgilash uchun quyidagi tugmani bosing."
    )
    await set_webapp_button(message.bot, user)


async def handle_parent_link(
    message: Message,
    token: str,
    telegram_id: int,
    session: AsyncSession,
) -> None:
    """
    Ota-ona bog'lash (p_TOKEN).

    Token tekshiruvi: mavjud, revoked emas, hali ulanmagan.
    User yaratish (agar yo'q bo'lsa) va bog'lash.
    """
    parent_link_service = ParentLinkService(session)
    parent_link = await parent_link_service.connect_parent(token)

    if parent_link is None:
        await message.answer(
            "❌ Bog'lanish havolasi noto'g'ri yoki bekor qilingan.\n\n"
            "Iltimos, administrator bilan bog'laning va yangi havola oling."
        )
        return

    # Get student info
    from app.models.student import Student

    student = await session.get(Student, parent_link.student_id)

    # Check if user exists
    from sqlalchemy import select

    from app.models.user import User

    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        # Create parent user (birinchi markaziga bog'lanadi;
        # keyingi markazlardagi bolalar alohida parent_link orqali ulanadi)
        user = User(
            telegram_id=telegram_id,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            username=message.from_user.username,
            role=UserRole.PARENT,
            center_id=student.center_id,
            is_active=True,
        )
        session.add(user)
        await session.flush()

    # Update parent_link with user_id
    parent_link.user_id = user.id
    await session.commit()

    logger.info(
        "Ota-ona ulandi",
        telegram_id=telegram_id,
        student_id=parent_link.student_id,
        user_id=user.id,
    )

    await message.answer(
        f"✅ Bog'lanish muvaffaqiyatli!\n\n"
        f"Siz {student.name}ning ota-onasi sifatida ulangansiz.\n\n"
        "Boshqa bolangiz yoki boshqa o'quv markazidagi bola uchun ham "
        "shu botga yangi havolani bosishingiz mumkin — barcha bolalaringiz "
        "bitta akkauntda ko'rinadi."
    )


async def handle_bot_blocked(message: Message) -> None:
    """
    Bot bloklangan holatni ushlash.

    parent_links va notification holatlariga yozish.
    """
    telegram_id = message.from_user.id

    logger.warning("Bot bloklangan", telegram_id=telegram_id)

    # TODO: Update parent_links and notification status
    # Bu keyingi bosqichlarda worker bilan birga ishlaydi
