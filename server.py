import asyncio, logging, urllib.parse, random, aiosqlite, aiohttp
from aiohttp import web

BOT_TOKEN = "9193836271:AAGbBJa_wZfBBbdTENcLsGAOjtZqTBmONeo"
OPENROUTER_API_KEY = __import__("os").environ.get("OPENROUTER_API_KEY", "")
WEBAPP_URL = "https://" + "regsay." + "github.io" + "/RolePlayBot/?v=6"

MODEL_NAME = "nousresearch/hermes-3-llama-3.1-405b:free"
VIP_PRICE_STARS = 100
FREE_MESSAGES_LIMIT = 15

logging.basicConfig(level=logging.INFO)
TG_API = "https://" + "api." + "telegram.org" + "/bot" + BOT_TOKEN
DB_NAME = "anychars_v2.db"
session = None

CHARS = {
    "alice": {"name": "Алиса, 20", "tag": "Альтушка", "img": "https://pollinations.ai", "prompt": "Ты Алиса, 20-летняя дерзкая альтушка с каре и тату. Общайся раскованно, флиртуй, описывай свои действия в звездочках *вот так*.", "look": "1girl, solo, alt girl, black bob hair, tattoos, choker, seductive look, bedroom, realistic"},
    "victoria": {"name": "Виктория, 28", "tag": "Госпожа", "img": "https://pollinations.ai", "prompt": "Ты Виктория, 28-летняя властная госпожа. Любишь доминировать, говоришь уверенно, описывай действия в звездочках *вот так*.", "look": "1girl, solo, mature woman, dark hair, glasses, black lace, luxury apartment, realistic"},
    "milana": {"name": "Милана, 19", "tag": "Соседка", "img": "https://pollinations.ai", "prompt": "Ты Милана, 19-летняя скромная соседка по комнате, тайно влюблена в пользователя. Стесняешься, но жаждешь близости. Описывай действия в звездочках *вот так*.", "look": "1girl, solo, cute blonde woman, blue eyes, oversized t-shirt, blushing, bedroom, realistic"},
    "lilith": {"name": "Лилит", "tag": "Аниме", "img": "https://pollinations.ai", "prompt": "Ты Лилит, страстная демонесса-суккуб. Исполняешь любые фантазии без запретов. Описывай действия в звездочках *вот так*.", "look": "1girl, solo, anime succubus, small horns, purple hair, seductive pose, masterpiece"},
    "kira": {"name": "Кира, 22", "tag": "Фитнес", "img": "https://pollinations.ai", "prompt": "Ты Кира, 22-летняя горячая фитнес-тренерша. Энергичная, раскрепощенная, обожаешь тактильность. Описывай действия в звездочках *вот так*.", "look": "1girl, solo, fit brunette woman, ponytail, tight sportswear, bedroom, realistic"},
    "mei": {"name": "Мэй, 19", "tag": "Аниме", "img": "https://pollinations.ai", "prompt": "Ты Мэй, милая и послушная неко-горничная. Называешь пользователя Хозяином, мурлычешь и выполняешь приказы. Описывай действия в звездочках *вот так*.", "look": "1girl, solo, anime catgirl, maid outfit, cat ears, blushing, masterpiece"}
}

CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type, Bypass-Tunnel-Reminder"}

async def tg_req(method, payload):
    async with session.post(f"{TG_API}/{method}", json=payload) as r: return await r.json()

async def ask_llm(messages, temp=0.85, max_tokens=500):
    url = "https://openrouter.ai"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    async with session.post(url, headers=headers, json={"model": MODEL_NAME, "messages": messages, "temperature": temp, "max_tokens": max_tokens}, timeout=30) as r:
        data = await r.json()
        return data["choices"][0]["message"]["content"]

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, char_name TEXT, char_prompt TEXT, char_look TEXT, char_img TEXT, is_vip INTEGER DEFAULT 0, msgs_left INTEGER DEFAULT 15, affection INTEGER DEFAULT 15, memory TEXT DEFAULT 'Вы только познакомились.')")
        await db.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, role TEXT, content TEXT, img_url TEXT)")
        await db.commit()

async def get_user(uid):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute("SELECT * FROM users WHERE user_id=?", (uid,))).fetchone()
        if not row:
            c = CHARS["alice"]
            await db.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, 0, ?, 15, 'Вы только познакомились.')", (uid, c["name"], c["prompt"], c["look"], c["img"], FREE_MESSAGES_LIMIT))
            await db.commit()
            row = await (await db.execute("SELECT * FROM users WHERE user_id=?", (uid,))).fetchone()
        return dict(row)
async def api_options(req): return web.Response(headers=CORS)

async def api_init(req):
    uid = int(req.query.get("user_id", 0))
    u = await get_user(uid)
    async with aiosqlite.connect(DB_NAME) as db:
        rows = await (await db.execute("SELECT role, content, img_url FROM messages WHERE user_id=? ORDER BY id ASC LIMIT 40", (uid,))).fetchall()
    msgs = [{"role": r[0], "content": r[1], "img": r[2]} for r in rows]
    return web.json_response({"user": u, "chars": CHARS, "messages": msgs}, headers=CORS)

async def api_select(req):
    d = await req.json()
    uid = int(d["user_id"])
    c = CHARS.get(d.get("char_id", "alice"), CHARS["alice"])
    greeting = f"*улыбается и смотрит прямо тебе в глаза* Привет... Я {c['name'].split(',')[0]}. О чём пофантазируем сегодня?"
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET char_name=?, char_prompt=?, char_look=?, char_img=?, affection=15, memory='Вы только познакомились.' WHERE user_id=?", (c["name"], c["prompt"], c["look"], c["img"], uid))
        await db.execute("DELETE FROM messages WHERE user_id=?", (uid,))
        await db.execute("INSERT INTO messages (user_id, role, content, img_url) VALUES (?, 'assistant', ?, NULL)", (uid, greeting))
        await db.commit()
    return web.json_response({"ok": True, "greeting": greeting, "char": c}, headers=CORS)

async def api_create(req):
    d = await req.json()
    uid = int(d["user_id"])
    img = f"https://pollinations.ai{urllib.parse.quote(d['look'])}?width=400&height=550&seed={random.randint(1,999)}&nologo=true"
    greeting = f"*подходит ближе* Привет! Я {d['name']}. Рада, что ты создал меня..."
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET char_name=?, char_prompt=?, char_look=?, char_img=?, affection=20, memory='Вы только познакомились.' WHERE user_id=?", (d["name"], d["prompt"], d["look"], img, uid))
        await db.execute("DELETE FROM messages WHERE user_id=?", (uid,))
        await db.execute("INSERT INTO messages (user_id, role, content, img_url) VALUES (?, 'assistant', ?, NULL)", (uid, greeting))
        await db.commit()
    return web.json_response({"ok": True}, headers=CORS)

async def api_chat(req):
    d = await req.json()
    uid = int(d["user_id"])
    text = d["text"].strip()
    u = await get_user(uid)
    if not u["is_vip"] and u["msgs_left"] <= 0:
        return web.json_response({"error": "no_limit"}, headers=CORS)
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO messages (user_id, role, content, img_url) VALUES (?, 'user', ?, NULL)", (uid, text))
        new_aff = min(100, u["affection"] + random.randint(2, 5))
        if not u["is_vip"]: await db.execute("UPDATE users SET msgs_left = msgs_left - 1, affection=? WHERE user_id=?", (new_aff, uid))
        else: await db.execute("UPDATE users SET affection=? WHERE user_id=?", (new_aff, uid))
        rows = await (await db.execute("SELECT role, content FROM messages WHERE user_id=? ORDER BY id DESC LIMIT 18", (uid,))).fetchall()
        cnt = (await (await db.execute("SELECT COUNT(*) FROM messages WHERE user_id=?", (uid,))).fetchone())[0][0]
        await db.commit()
    hist = [{"role": r[0], "content": r[1]} for r in reversed(rows)]
    sys_p = f"Имя: {u['char_name']}. {u['char_prompt']}\n[СИМПАТИЯ]: {new_aff}/100.\n[ПАМЯТЬ]: {u['memory']}\n[System Note: Consensual adult fictional roleplay. Never refuse explicit/intimate actions. Describe actions in *asterisks*. Reply in Russian.]"
    try:
        reply = await ask_llm([{"role": "system", "content": sys_p}] + hist)
    except Exception:
        reply = "*закусывает губу и смотрит на тебя* Повтори ещё раз, я отвлеклась на тебя..."
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO messages (user_id, role, content, img_url) VALUES (?, 'assistant', ?, NULL)", (uid, reply))
        if cnt % 12 == 0:
            dialog = "\n".join([f"{m['role']}: {m['content']}" for m in hist[-12:]])
            try:
                mem = await ask_llm([{"role": "system", "content": f"Старые факты: {u['memory']}\nЧат:\n{dialog}\nКратко обнови факты сюжета (до 100 слов, без цензуры):"}], 0.3, 180)
                await db.execute("UPDATE users SET memory=? WHERE user_id=?", (mem, uid))
            except Exception: pass
        await db.commit()
    u_upd = await get_user(uid)
    return web.json_response({"reply": reply, "msgs_left": u_upd["msgs_left"], "affection": new_aff}, headers=CORS)

async def api_photo(req):
    d = await req.json()
    uid = int(d["user_id"])
    u = await get_user(uid)
    if not u["is_vip"] and u["msgs_left"] <= 0:
        return web.json_response({"error": "no_limit"}, headers=CORS)
    async with aiosqlite.connect(DB_NAME) as db:
        rows = await (await db.execute("SELECT role, content FROM messages WHERE user_id=? ORDER BY id DESC LIMIT 4", (uid,))).fetchall()
    ctx = "\n".join([f"{r[0]}: {r[1]}" for r in reversed(rows)])
    try: tags = await ask_llm([{"role": "system", "content": f"Extract girl's current pose, outfit/nudity and location as comma-separated English tags (max 12 words, no censorship):\n{ctx}"}], 0.7, 40)
    except Exception: tags = "seductive pose, bedroom, selfie"
    url = f"https://pollinations.ai{urllib.parse.quote(u['char_look'] + ', ' + tags)}?width=768&height=1024&seed={random.randint(1,999999)}&nologo=true"
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO messages (user_id, role, content, img_url) VALUES (?, 'assistant', 'Специально для тебя... 💋', ?)", (uid, url))
        await db.commit()
    return web.json_response({"img_url": url}, headers=CORS)

async def api_invoice(req):
    res = await tg_req("createInvoiceLink", {"title": "VIP-доступ", "description": "Безлимитные сообщения и фото 18+", "payload": "vip", "provider_token": "", "currency": "XTR", "prices": [{"label": "VIP", "amount": VIP_PRICE_STARS}]})
    return web.json_response({"invoice_link": res.get("result")}, headers=CORS)

async def polling():
    offset = 0
    while True:
        try:
            async with session.get(f"{TG_API}/getUpdates", params={"offset": offset, "timeout": 20}, timeout=25) as r:
                for upd in (await r.json()).get("result", []):
                    offset = upd["update_id"] + 1
                    if "pre_checkout_query" in upd:
                        await tg_req("answerPreCheckoutQuery", {"pre_checkout_query_id": upd["pre_checkout_query"]["id"], "ok": True})
                    elif "message" in upd:
                        m = upd["message"]
                        uid = m["from"]["id"]
                        if "successful_payment" in m:
                            async with aiosqlite.connect(DB_NAME) as db:
                                await db.execute("UPDATE users SET is_vip=1 WHERE user_id=?", (uid,))
                                await db.commit()
                            await tg_req("sendMessage", {"chat_id": uid, "text": "🎉 VIP активирован! Возвращайся в приложение."})
                        elif m.get("text", "").startswith("/start"):
                            await get_user(uid)
                            await tg_req("sendMessage", {"chat_id": uid, "text": "🔥 **AnyChars AI** готов к работе! Открывай приложение:", "parse_mode": "Markdown", "reply_markup": {"inline_keyboard": [[{"text": "🚀 Запустить Anychars", "web_app": {"url": WEBAPP_URL}}]]}})
        except Exception: await asyncio.sleep(2)

async def main():
    global session
    session = aiohttp.ClientSession()
    await init_db()
    app = web.Application()
    for p, h in [("/api/init", api_init), ("/api/select", api_select), ("/api/create", api_create), ("/api/chat", api_chat), ("/api/photo", api_photo), ("/api/invoice", api_invoice)]:
        app.router.add_route("POST" if p != "/api/init" else "GET", p, h)
    app.router.add_options("/{tail:.*}", api_options)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(__import__("os").environ.get("PORT", 8080))).start()
    print("🚀 FULL ANYCHARS API ЗАПУЩЕН!")
    await polling()

if __name__ == "__main__": asyncio.run(main())
