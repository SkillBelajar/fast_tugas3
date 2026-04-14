from fasthtml.common import *
from dataclasses import dataclass
from datetime import datetime
from starlette.responses import RedirectResponse
import hashlib

# ─────────────────────────────────────────────
# 1. APP SETUP
# ─────────────────────────────────────────────
app, rt = fast_app(hdrs=(picolink,), secret_key="rahasia-psikologi-lens")

# ─────────────────────────────────────────────
# 2. DATABASE & MODELS
# ─────────────────────────────────────────────
db = database("lens_app.db")


@dataclass
class User:
    id: int
    username: str
    pwd_hash: str
    active_task_id: int


@dataclass
class Task:
    id: int
    user_id: int
    title: str
    description: str
    is_done: bool
    created_at: str


@dataclass
class MicroEntry:
    id: int
    task_id: int
    content: str
    is_done: bool
    created_at: str


users        = db.create(User)
tasks        = db.create(Task)
micro_entries = db.create(MicroEntry)

# ─────────────────────────────────────────────
# 3. AUTH HELPERS
# ─────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash password dengan SHA-256 agar tidak tersimpan plaintext."""
    return hashlib.sha256(password.encode()).hexdigest()


def get_current_user(session):
    """Kembalikan objek User dari session, atau None jika belum login."""
    user_id = session.get("user_id")
    return users.get(user_id) if user_id else None


def require_login(session):
    """
    Guard helper — kembalikan redirect ke /login jika user belum login.
    Pemakaian: `guard = require_login(session); if guard: return guard`
    """
    if not session.get("user_id"):
        return RedirectResponse("/login", status_code=303)
    return None

# ─────────────────────────────────────────────
# 4. LAYOUT & UI COMPONENTS
# ─────────────────────────────────────────────

def Layout(*content, session=None):
    """
    Shell halaman global. Nav berubah sesuai status login.
    Terima konten sebagai *args agar bisa menerima elemen ganda.
    """
    is_logged_in = session and session.get("user_id")
    nav_items = [Li(A("Dashboard", href="/"))]

    if is_logged_in:
        nav_items.append(Li(A("Keluar", href="/logout", cls="outline")))
    else:
        nav_items.append(Li(A("Login", href="/login", cls="secondary")))

    return (
        Title("15-Min Lens"),
        Div(
            Header(
                Nav(
                    Ul(Li(Strong("🎯 15-Min Lens"))),
                    Ul(*nav_items),
                ),
                cls="container",
            ),
            Main(*content, cls="container", style="margin-top:2rem; min-height:60vh;"),
            Footer(
                Small(I("Built with FastHTML & Psychology in mind. — Bebas dari kecemasan kognitif.")),
                cls="container",
                style="border-top:1px solid #e5e5e5; padding-top:1.5rem; margin-top:3rem; text-align:center;",
            ),
        ),
    )


def AlertError(message: str, back_href: str = "/login"):
    """Komponen pesan error sederhana dengan tombol kembali."""
    return (
        P(message, style="color:red; text-align:center;"),
        A("Kembali", href=back_href, role="button", cls="outline"),
    )


def TaskInput():
    """Form HTMX untuk menambah tugas baru."""
    return Form(
        Div(
            Input(name="title", placeholder="Apa tugas besar yang membebani pikiranmu?", required=True),
            Input(name="description", placeholder="Detail singkat (opsional)"),
            cls="grid",
        ),
        Button("Tambahkan ke Peta", type="submit"),
        hx_post="/tasks",
        hx_target="#task-list",
        hx_swap="afterbegin",
        hx_on__after_request="this.reset()",
        style="margin-bottom:3rem; padding-bottom:2rem; border-bottom:1px solid #eee;",
    )


def TaskRow(task):
    """Card untuk satu item tugas di Map Mode."""
    desc = P(task.description) if task.description else P(
        I("Tidak ada deskripsi detail"), style="color:#888;"
    )
    return Article(
        Header(Strong(task.title)),
        desc,
        Footer(
            A(
                "🔍 Masuk ke Lens Mode (15-Min)",
                hx_get=f"/tasks/{task.id}/prompt",
                hx_target=f"#task-{task.id}",
                hx_swap="outerHTML",
                role="button",
                cls="outline",
            )
        ),
        id=f"task-{task.id}",
        style="margin-bottom:1rem;",
    )


def FocusLens(task, entry):
    """Tampilan utama Focus Mode — satu langkah 15 menit."""
    return Div(
        Div(
            P("FOKUS 15 MENIT:", style="color:#888; font-weight:bold; letter-spacing:2px;"),
            H1(entry.content, style="font-size:2.5rem; color:#1095c1; margin:1rem 0;"),
            P(f"Bagian dari: {task.title}", style="color:#666; font-style:italic;"),
            Hr(style="margin:2rem 0;"),
            Form(action=f"/complete/{entry.id}", method="post")(
                Button(
                    "✅ Langkah Selesai!",
                    type="submit",
                    style="font-size:1.2rem; padding:1rem; width:100%; border-radius:50px;",
                )
            ),
            style=(
                "text-align:center; padding:4rem; background:#fff;"
                " border:1px solid #eee; border-radius:16px;"
                " box-shadow:0 20px 40px rgba(0,0,0,0.08);"
            ),
        ),
        style="display:flex; justify-content:center; align-items:center; min-height:60vh;",
    )


def LoginForm():
    """Form login/register yang dikemas sebagai komponen tersendiri."""
    return Div(
        H2("Masuk / Daftar", style="text-align:center;"),
        P("Mulai kelola beban kognitifmu hari ini.", style="text-align:center; color:#666;"),
        Form(action="/login", method="post")(
            Input(name="username", placeholder="Username unik", required=True),
            Input(name="password", type="password", placeholder="Password", required=True),
            Div(
                Button("Login", type="submit", name="action", value="login"),
                Button("Daftar Baru", type="submit", name="action", value="register", cls="secondary outline"),
                cls="grid",
            ),
        ),
        style=(
            "max-width:400px; margin:4rem auto 0; padding:2rem;"
            " border:1px solid #eee; border-radius:12px;"
            " box-shadow:0 10px 30px rgba(0,0,0,0.05);"
        ),
    )

# ─────────────────────────────────────────────
# 5. ROUTES — AUTH
# ─────────────────────────────────────────────

@rt("/login")
def get(session):
    if session.get("user_id"):
        return RedirectResponse("/", status_code=303)
    return Layout(LoginForm(), session=session)


@rt("/login")
def post(session, username: str, password: str, action: str):
    pwd_hash = hash_password(password)

    if action == "register":
        if users(where=f"username = '{username}'"):
            return Layout(
                *AlertError("Username sudah terpakai!", back_href="/login"),
                session=session,
            )
        u = users.insert(username=username, pwd_hash=pwd_hash, active_task_id=0)
        session["user_id"] = u.id
        return RedirectResponse("/", status_code=303)

    # action == "login"
    result = users(where=f"username = '{username}' AND pwd_hash = '{pwd_hash}'")
    if result:
        session["user_id"] = result[0].id
        return RedirectResponse("/", status_code=303)

    return Layout(
        *AlertError("Username atau password salah!", back_href="/login"),
        session=session,
    )


@rt("/logout")
def get(session):
    session.clear()
    return RedirectResponse("/login", status_code=303)

# ─────────────────────────────────────────────
# 6. ROUTES — APLIKASI UTAMA
# ─────────────────────────────────────────────

@rt("/")
def get(session):
    guard = require_login(session)
    if guard:
        return guard

    u = get_current_user(session)

    # Cek apakah user sedang dalam Focus Mode
    if u.active_task_id != 0:
        task = tasks.get(u.active_task_id)
        active_entries = micro_entries(
            where=f"task_id = {task.id} AND is_done = 0",
            order_by="id DESC",
        )
        if active_entries:
            return Layout(FocusLens(task, active_entries[0]), session=session)
        # Tidak ada entry aktif — reset state fokus
        u.active_task_id = 0
        users.update(u)

    # Map Mode: daftar tugas milik user
    active_tasks = tasks(
        where=f"is_done = 0 AND user_id = {u.id}",
        order_by="id DESC",
    )
    return Layout(
        Div(
            H2(f"Peta Tugas: {u.username} 🗺️"),
            P(
                "Tuangkan semua beban pikiranmu di sini. Biarkan sistem yang mengingatnya untukmu.",
                style="color:#666;",
            ),
            TaskInput(),
            Div(*[TaskRow(t) for t in active_tasks], id="task-list"),
        ),
        session=session,
    )


@rt("/tasks")
def post(session, title: str, description: str):
    """Endpoint HTMX — tambah tugas baru dan kembalikan TaskRow."""
    guard = require_login(session)
    if guard:
        return ""  # HTMX gagal diam-diam jika sesi kedaluwarsa

    new_task = tasks.insert(
        user_id=session["user_id"],
        title=title,
        description=description,
        is_done=False,
        created_at=datetime.now().isoformat(),
    )
    return TaskRow(new_task)


@rt("/tasks/{id}/prompt")
def get(session, id: int):
    """Endpoint HTMX — munculkan form pembedahan tugas 15 menit."""
    guard = require_login(session)
    if guard:
        return ""

    task = tasks.get(id)
    if task.user_id != session["user_id"]:
        return "Unauthorized"  # Cegah IDOR

    return Article(
        Header(Strong(f"Membedah: {task.title}")),
        P(
            "Tarik napas panjang. Jangan pikirkan selesainya, pikirkan langkah 15 menit pertamanya saja.",
            style="color:#666;",
        ),
        Form(action=f"/focus/{id}", method="post")(
            Input(
                name="content",
                placeholder="Contoh: Buka file excel dan tulis judul...",
                required=True,
            ),
            Button("Mulai Fokus 15 Menit 🎯", type="submit"),
        ),
        id=f"task-{id}",
        style="border:2px solid #1095c1; background-color:#f6fcff;",
    )


@rt("/focus/{id}")
def post(session, id: int, content: str):
    """Simpan langkah 15 menit dan kunci user ke Focus Mode."""
    guard = require_login(session)
    if guard:
        return guard

    micro_entries.insert(
        task_id=id,
        content=content,
        is_done=False,
        created_at=datetime.now().isoformat(),
    )

    u = get_current_user(session)
    u.active_task_id = id
    users.update(u)

    return RedirectResponse("/", status_code=303)


@rt("/complete/{entry_id}")
def post(session, entry_id: int):
    """Tandai langkah & tugas selesai, lepas user dari Focus Mode."""
    guard = require_login(session)
    if guard:
        return guard

    entry = micro_entries.get(entry_id)
    entry.is_done = True
    micro_entries.update(entry)

    task = tasks.get(entry.task_id)
    task.is_done = True
    tasks.update(task)

    u = get_current_user(session)
    u.active_task_id = 0
    users.update(u)

    return RedirectResponse("/", status_code=303)

# ─────────────────────────────────────────────
# 7. ENTRYPOINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    serve()