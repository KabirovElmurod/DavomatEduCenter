import Alpine from "alpinejs";
import "./style.css";

const API = "/api/v1";
const STATUSES = ["present", "absent", "late"];

let token = null;
let idempotencyKey = null;

function newIdempotencyKey() {
  if (crypto.randomUUID) return crypto.randomUUID();
  return "k_" + Date.now().toString(36) + Math.random().toString(36).slice(2, 12);
}

async function api(path, options = {}) {
  const res = await fetch(API + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Xato ${res.status}`);
  }
  return res.json();
}

function tg() {
  return window.Telegram?.WebApp;
}

function app() {
  return {
    screen: "loading",
    error: "",
    today: "",
    groups: [],
    currentGroup: null,
    students: [],
    resultText: "",

    async init() {
      const webApp = tg();
      webApp?.ready();
      webApp?.expand();
      this.applyTheme(webApp);

      try {
        if (!webApp?.initData) throw new Error("Telegram ichida oching");
        const auth = await api("/auth/telegram", {
          method: "POST",
          body: JSON.stringify({ init_data: webApp.initData }),
        });
        token = auth.access_token;
        await this.loadGroups();
      } catch (e) {
        const w = window.Telegram?.WebApp;
        this.error =
          e.message +
          ` [tg=${!!window.Telegram} initData=${w?.initData?.length ?? "yo'q"}]`;
        this.screen = "groups";
      }
    },

    applyTheme(webApp) {
      if (!webApp?.themeParams) return;
      const p = webApp.themeParams;
      const root = document.documentElement.style;
      root.setProperty("--tg-bg", p.bg_color || "#ffffff");
      root.setProperty("--tg-text", p.text_color || "#000000");
      root.setProperty("--tg-hint", p.hint_color || "#999999");
      root.setProperty("--tg-button", p.button_color || "#40a7e3");
      root.setProperty("--tg-button-text", p.button_text_color || "#ffffff");
    },

    async loadGroups() {
      this.screen = "loading";
      try {
        const data = await api("/teacher/groups");
        this.today = data.date;
        this.groups = data.groups;
        this.screen = "groups";
      } catch (e) {
        this.error = e.message;
        this.screen = "groups";
      }
    },

    async openGroup(g) {
      this.currentGroup = g;
      this.screen = "loading";
      try {
        const data = await api(`/groups/${g.id}/lesson/today`);
        this.students = data.students.map((s) => ({
          ...s,
          status: s.status || "present",
        }));
        idempotencyKey = newIdempotencyKey();
        this.screen = "attendance";
        this.setupMainButton();
      } catch (e) {
        this.error = e.message;
        this.screen = "groups";
      }
    },

    cycleStatus(s) {
      const i = STATUSES.indexOf(s.status);
      s.status = STATUSES[(i + 1) % STATUSES.length];
    },

    allPresent() {
      this.students.forEach((s) => (s.status = "present"));
    },

    statusLabel(s) {
      return { present: "Keldi", absent: "Yo'q", late: "Kech" }[s.status];
    },

    setupMainButton() {
      const mb = tg()?.MainButton;
      if (!mb) return;
      mb.setText("Yuborish");
      mb.enable();
      mb.show();
      mb.offClick?.();
      mb.onClick?.(() => this.submit());
    },

    submitting: false,

    async submit() {
      if (this.submitting) return;
      this.submitting = true;
      const mb = tg()?.MainButton;
      mb?.disable();
      this.error = "";
      try {
        const res = await api(`/groups/${this.currentGroup.id}/attendance`, {
          method: "POST",
          headers: { "Idempotency-Key": idempotencyKey },
          body: JSON.stringify({
            items: this.students.map((s) => ({
              student_id: s.id,
              status: s.status,
            })),
          }),
        });
        mb?.hide();
        this.resultText = `Yuborildi: ${res.students} o'quvchi, ${res.notifications_queued} ta xabar navbatda`;
        this.screen = "result";
      } catch (e) {
        // Xatoda o'sha Idempotency-Key bilan retry
        this.error = e.message;
        mb?.enable();
      } finally {
        this.submitting = false;
      }
    },
  };
}

Alpine.data("app", app);
Alpine.start();
