import os
import random
import json
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("ERROR: Please set BOT_TOKEN environment variable.")
    exit(1)

user_state = {}
points_file = 'points.json'
MAX_ATTEMPTS = 10
WIN_POINTS = 10
LOSS_POINTS = -5
ADMIN_ID = None
points_data = {}

# بارگذاری امتیازها
try:
    with open(points_file, 'r', encoding='utf-8') as f:
        points_data = json.load(f)
except:
    points_data = {}

def save_points():
    with open(points_file, 'w', encoding='utf-8') as f:
        json.dump(points_data, f, ensure_ascii=False, indent=2)

def get_top_users(n=5):
    sorted_users = sorted(points_data.values(), key=lambda x: x["points"], reverse=True)
    return sorted_users[:n]

async def send_live_top(context: ContextTypes.DEFAULT_TYPE):
    top_users = get_top_users()
    if not top_users:
        return
    leaderboard = "\n".join([f"🏆 {i+1}. @{u['username']} → {u['points']} امتیاز" for i, u in enumerate(top_users)])
    message = f"🔥 جدول لحظه‌ای ۵ نفر برتر:\n{leaderboard}"
    for user_id in list(points_data.keys()):
        try:
            await context.bot.send_message(chat_id=int(user_id), text=message)
        except:
            pass

async def notify_if_top5(context, user_id, username):
    top_users = get_top_users()
    usernames = [u["username"] for u in top_users]
    if username in usernames:
        rank = usernames.index(username) + 1
        await context.bot.send_message(chat_id=user_id, text=f"🏅 تبریک! شما وارد رتبه {rank} جدول Top 5 شدید!")
        if ADMIN_ID:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"📢 کاربر @{username} وارد رتبه {rank} جدول Top 5 شد! 🎉")

async def update_score(context, user_id, username, score):
    sid = str(user_id)
    if sid not in points_data:
        points_data[sid] = {"username": username, "points": 0}
    points_data[sid]["points"] += score
    save_points()
    await notify_if_top5(context, user_id, username)
    if points_data[sid]["points"] >= 1000:
        if ADMIN_ID:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"📢 کاربر @{username} امتیازش بالای 1000 شد و در قرعه‌کشی شرکت داده شد!")
        await context.bot.send_message(chat_id=user_id, text="🎉 تبریک! امتیاز شما بالای ۱۰۰۰ رفت و در قرعه‌کشی شرکت داده شدید.")
    await send_live_top(context)

def draw_winner():
    eligible = [u for u in points_data.values() if u["points"] >= 1000]
    if not eligible:
        return None
    return random.choice(eligible)

def reset_user(username):
    for user_id, data in points_data.items():
        if data["username"] == username:
            points_data[user_id]["points"] = 0
            save_points()
            return True
    return False

def remove_user(username):
    for user_id, data in list(points_data.items()):
        if data["username"] == username:
            del points_data[user_id]
            save_points()
            return True
    return False

# handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ADMIN_ID
    user = update.effective_user
    if ADMIN_ID is None:
        ADMIN_ID = user.id
        await update.message.reply_text("📢 شما مدیر ربات شدید و می‌توانید تنظیمات را کنترل کنید.")
    await update.message.reply_text(
        "👋 خوش اومدی!\n"
        "یک عدد بین ۱ تا ۱۰۰ بفرست.\n\n"
        "دستورات:\n"
        "/score — دیدن امتیاز\n"
        "/top — جدول ۵ نفر برتر\n"
        "مدیر:\n"
        "/users /draw /reset <username> /remove <username>\n"
    )

async def show_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    score = points_data.get(str(user.id), {"points": 0})["points"]
    await update.message.reply_text(f"امتیاز فعلی شما: {score}")

async def show_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top_users = get_top_users()
    if top_users:
        ranking = "\n".join([f"🏆 {i+1}. @{u['username']} → {u['points']} امتیاز" for i, u in enumerate(top_users)])
        await update.message.reply_text(f"🔥 جدول ۵ نفر برتر:\n{ranking}")
    else:
        await update.message.reply_text("⛔ هنوز هیچ کاربری ثبت نشده.")

async def handle_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = user.username or f"user{user.id}"
    sid = str(user.id)
    if sid not in user_state:
        user_state[sid] = {"number": random.randint(1, 100), "attempts": 0}
    state = user_state[sid]
    try:
        guess = int(update.message.text)
    except:
        return await update.message.reply_text("❗ لطفاً یک عدد بین ۱ تا ۱۰۰ بفرستید.")
    state["attempts"] += 1
    remaining = MAX_ATTEMPTS - state["attempts"]
    if guess < state["number"]:
        await update.message.reply_text(f"⬆️ عدد بالاتر است! تلاش باقی‌مانده: {remaining}")
    elif guess > state["number"]:
        await update.message.reply_text(f"⬇️ عدد پایین‌تر است! تلاش باقی‌مانده: {remaining}")
    else:
        await update.message.reply_text(f"🎯 آفرین! عدد {state['number']} رو درست حدس زدی. +{WIN_POINTS} امتیاز گرفتی.")
        await update_score(context, user.id, username, WIN_POINTS)
        user_state[sid] = {"number": random.randint(1, 100), "attempts": 0}
        return
    if state["attempts"] >= MAX_ATTEMPTS:
        await update.message.reply_text(f"❌ باختی! عدد درست {state['number']} بود. {LOSS_POINTS} امتیاز ازت کم شد.")
        await update_score(context, user.id, username, LOSS_POINTS)
        user_state[sid] = {"number": random.randint(1, 100), "attempts": 0}

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    user_list = "\n".join([f"@{data['username']}: {data['points']} امتیاز" for data in points_data.values()])
    await update.message.reply_text(f"📊 لیست کاربران:\n{user_list if user_list else 'هیچ کاربری ثبت نشده'}")

async def admin_draw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    winner = draw_winner()
    if winner:
        await update.message.reply_text(f"🎁 برنده قرعه‌کشی: @{winner['username']} ({winner['points']} امتیاز)")
    else:
        await update.message.reply_text("⛔ هیچ کاربری با امتیاز بالای ۱۰۰۰ نیست.")

# main
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("score", show_score))
    app.add_handler(CommandHandler("top", show_top))
    app.add_handler(CommandHandler("users", admin_users))
    app.add_handler(CommandHandler("draw", admin_draw))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_guess))
    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
