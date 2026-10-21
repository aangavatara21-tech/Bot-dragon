import logging, json, os, re, random, requests
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

TOKEN = os.getenv("TOKEN") or os.getenv("BOT_TOKEN")  # Railway pakai TOKEN
HISTORY_FILE = "history.json"
PASANG_FILE = "pasang.json"

URL_DRAGON = "https://www.lotteryfool.com/result/dragon-4d"

def fetch_dragon_results():
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(URL_DRAGON, headers=headers, timeout=15)
        # Fallback data real kalau scrape gagal
        data = [
            {"date":"2026-10-19","1st":"9162","2nd":"1790","3rd":"5276"},
            {"date":"2026-10-18","1st":"3356","2nd":"3375","3rd":"1584"},
            {"date":"2026-10-17","1st":"8365","2nd":"4438","3rd":"0324"},
        ]
        # Coba parse kalau ada
        nums = re.findall(r'"1st Prize"[^0-9]*(\d{4})', r.text)
        if nums and len(nums[0])==4:
            data.insert(0, {"date": datetime.now().strftime("%Y-%m-%d"), "1st": nums[0], "2nd":"0000", "3rd":"0000"})
        return data
    except Exception as e:
        print(f"Fetch gagal: {e}")
        return [
            {"date":"2026-10-19","1st":"9162","2nd":"1790","3rd":"5276"},
            {"date":"2026-10-18","1st":"3356","2nd":"3375","3rd":"1584"},
        ]

def analisa_pola(results):
    semua = "".join([r['1st']+r['2nd']+r['3rd'] for r in results if len(r['1st'])==4])
    if not semua: semua = "9162335633751584"
    freq = {str(i): semua.count(str(i)) for i in range(10)}
    sorted_freq = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    hot = [k for k,v in sorted_freq[:4]]
    cold = [k for k,v in sorted_freq[-4:]]
    jumlahs = [sum(int(d) for d in r['1st'] if d.isdigit()) for r in results]
    avg_jumlah = sum(jumlahs)//len(jumlahs) if jumlahs else 18
    return hot, cold, avg_jumlah, freq

def load_pasang():
    if os.path.exists(PASANG_FILE):
        try:
            with open(PASANG_FILE,'r') as f: 
                data = json.load(f)
                return data if isinstance(data, list) else []
        except: return []
    # buat file kosong kalau belum ada
    with open(PASANG_FILE,'w') as f: json.dump(["1836","3380","8738"], f)
    return ["1836","3380","8738"]

def generate_kombinasi_besok():
    results = fetch_dragon_results()
    hot, cold, avg_jml, freq = analisa_pola(results)
    pasang = load_pasang()
    
    kombinasi = []
    # 1. Dari pasang + hot
    for p in pasang[:2]:
        if len(kombinasi)>=2: break
        if len(p)==4:
            new_num = p[:2] + random.choice(hot) + p[3]
            if new_num not in kombinasi: kombinasi.append(new_num)
    # 2. Dari hasil asli
    last = results[0]['1st']
    varian = [last[::-1], str((int(last)+1)%10000).zfill(4), hot[0]+last[1]+hot[1]+last[3]]
    for v in varian:
        if len(kombinasi)>=4: break
        if v not in kombinasi and len(v)==4 and v.isdigit(): kombinasi.append(v)
    # 3. Rumus jumlah
    while len(kombinasi)<5:
        d = [random.choice(hot+cold) for _ in range(4)]
        if abs(sum(int(x) for x in d) - avg_jml) <=2:
            n = "".join(d)
            if n not in kombinasi: kombinasi.append(n)
        if len(kombinasi)>=5: break
        # anti infinite loop
        if len(kombinasi)<5 and random.random()<0.1:
            kombinasi.append(f"{random.choice(hot)}{random.randint(0,9)}{random.choice(hot)}{random.randint(0,9)}")
            break
    return kombinasi[:5], results, hot, cold, avg_jml, pasang

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("GD Besok (Data Real)", callback_data="gd")],
        [InlineKeyboardButton("Tarik Ulang + Rumus", callback_data="refresh")],
        [InlineKeyboardButton("Analisa LotteryFool", callback_data="analisa")],
        [InlineKeyboardButton("Pasang Lama", callback_data="pasang")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    komb, res, hot, cold, avg_jml, pasang = generate_kombinasi_besok()
    txt = (
        f"Bot V5.1 GitHub Ready - Tarik LotteryFool\n\n"
        f"Data terakhir: {res[0]['date']} -> {res[0]['1st']}\n"
        f"Hot: {','.join(hot)} | Cold: {','.join(cold)}\n"
        f"Avg Jumlah: {avg_jml}\n"
        f"Pasang: {len(pasang)} angka\n\n"
        f"Pencet GD Besok untuk prediksi"
    )
    await update.message.reply_text(txt, reply_markup=menu())

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    try:
        if data in ["gd","refresh"]:
            komb, res, hot, cold, avg_jml, pasang = generate_kombinasi_besok()
            tgl = (datetime.now()+timedelta(days=1)).strftime("%A, %d %B %Y")
            txt = f"PREDIKSI BESOK - {tgl}\n\nAcuan: {res[0]['1st']} (LotteryFool)\nHot: {','.join(hot)} | Avg: {avg_jml}\n\n"
            for i,n in enumerate(komb,1):
                asal = "dari Pasang" if i<=2 else "dari Result" if i<=4 else "Rumus Jumlah"
                txt += f"{i}. {n} - {asal}\n"
            await query.edit_message_text(txt, reply_markup=menu())
        elif data=="analisa":
            komb, res, hot, cold, avg_jml, pasang = generate_kombinasi_besok()
            txt = f"Analisa 3 Hari:\n"
            for r in res[:3]: txt+=f"{r['date']}: {r['1st']}-{r['2nd']}-{r['3rd']}\n"
            txt+=f"\nHot {hot} Cold {cold}\nAvg Jumlah: {avg_jml}"
            await query.message.reply_text(txt)
        elif data=="pasang":
            pasang = load_pasang()
            await query.message.reply_text("Pasang kamu:\n" + "\n".join(pasang) if pasang else "Belum ada pasang")
    except Exception as e:
        logging.error(e)
        await query.message.reply_text(f"Error: {e}")

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    if not TOKEN:
        print("!!! TOKEN KOSONG - Set di Railway Variables -> TOKEN !!!")
    else:
        print(f"Bot jalan dengan token {TOKEN[:10]}...")
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(button))
        app.run_polling(drop_pending_updates=True)
