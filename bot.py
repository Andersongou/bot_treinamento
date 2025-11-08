import os
import logging
from datetime import date
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes

# Config
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise RuntimeError("Set the TELEGRAM_TOKEN environment variable")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Plano: datas base
START_DATE = date(2025, 11, 5)
RACE_DATE = date(2025, 11, 30)

# Template semanal genérico
WEEKLY_TEMPLATE = {
    0: "Seg – Intervalado Curto (VO2)\n• Ex.: séries curtas de 400m a ritmo forte",
    1: "Ter – Rodagem leve (Z2)\n• Ex.: 40–50 min a ritmo confortável",
    2: "Qua – Limiar Anaeróbico\n• Ex.: blocos de tempo em ritmo de limiar",
    3: "Qui – Corrida moderada + técnica\n• Ex.: 30–40 min + educativos",
    4: "Sex – Intervalado Longo (sub-ritmo prova)\n• Ex.: 4–6 x 1000-1200m a ritmo forte",
    5: "Sáb – Longão progressivo\n• Ex.: treino longo com progressão",
    6: "Dom – Core/mobilidade ou descanso\n• Ex.: 20–30 min de mobilidade/core ou OFF",
}

# Overrides detalhados por semana (1..4) e dia da semana (0=seg..6=dom)
WEEK_OVERRIDES = {
    1: {
        2: (
            "Qua (05/11) – Limiar Anaeróbico\n"
            "• Aquecimento: 10 min leve\n"
            "• Série Principal: 3 x 8 min a 4:00/km (FC ~ Z4)\n"
            "• Pausa: 2 min trote\n"
            "• Desaquecimento: 10 min leve"
        ),
        3: "Qui – Corrida Moderada + Técnica\n• 35 min a 4:35–4:45/km + 10 min educativos",
        4: "Sex – Intervalado Longo\n• Aquecimento: 12 min\n• 6 x 1000m a 3:44/km • Pausa: 90s\n• Desaquecimento: 10 min",
        5: (
            "Sáb – Longão Progressivo (75–80 min)\n"
            "• 25 min a 5:10–4:50/km\n"
            "• 30 min a 4:50–4:30/km\n"
            "• 20 min a 4:20–4:10/km"
        ),
        6: "Dom – Mobilidade + Core\n• 20 min mobilidade + 15 min core",
    },
    2: {
        0: "Seg – Intervalado Curto (VO2)\n• 10 x 400m a 3:20–3:30/km • Pausa: 75s",
        1: "Ter – Rodagem Z2\n• 45 min a 5:00–5:15/km • FC alvo: 124–155 bpm",
        2: "Qua – Limiar Anaeróbico\n• 2 x 12 min a 4:00/km • Pausa: 3 min",
        3: "Qui – Corrida Moderada + Técnica\n• 40 min a 4:35/km + educativos",
        4: "Sex – Intervalado Longo\n• 5 x 1200m a 3:42/km • Pausa: 90s",
        5: "Sáb – Longão\n• 85 min progressivo; últimos 20 min a 4:10/km",
        6: "Dom – Core/Mobilidade",
    },
    3: {
        0: "Seg – Intervalado Curto (afinando)\n• 12 x 400m a 3:24/km • Pausa: 75s",
        1: "Ter – Rodagem leve Z2\n• 40–45 min solto",
        2: "Qua – Limiar Anaeróbico com final forte\n• 3 x 8 min a 3:58/km • Pausa: 2 min",
        3: "Qui – Técnica + Corrida Leve\n• 30–35 min a 4:50/km + educativos",
        4: "Sex – Intervalado Longo Afinado\n• 4 x 1200m a 3:40/km • Pausa: 90s",
        5: "Sáb – Longão reduzido\n• 70 min; últimos 15 min a 4:00/km",
        6: "Dom – OFF ou 25 min Z2",
    },
    4: {
        0: "Seg (25) – 8 x 200m a 3:10/km • Recuperação completa (jogging leve)",
        1: "Ter – 30 min Z2 + 4 acelerações de 80m",
        2: "Qua – 3 x 1 km a ritmo de prova (3:35/km) • Pausas 2–3 min",
        3: "Qui – 25 min leve + educativos",
        4: "Sex – OFF ou 20 min trote com 2 acelerações",
        5: "Sáb – OFF ou 15 min solto (opcional)",
        6: (
            "Dom (30/11) – DIA DA PROVA – 5 km\n"
            "• Objetivo: Sub 18 min\n• Pace alvo: 3:35/km\n"
            "• Aquecimento: 12 min leve + 3 acelerações\n• Plano: 0–2 km 3:36/km; 2–4 km 3:34/km; 4–5 km: tudo"
        ),
    },
}


def weekday_name_pt(d: date) -> str:
    names = [
        "Segunda-feira",
        "Terça-feira",
        "Quarta-feira",
        "Quinta-feira",
        "Sexta-feira",
        "Sábado",
        "Domingo",
    ]
    return names[d.weekday()]


def get_week_number_for_date(d: date) -> Optional[int]:
    if d < START_DATE or d > RACE_DATE:
        return None
    delta_days = (d - START_DATE).days
    return (delta_days // 7) + 1


def get_training_for_date(d: date) -> str:
    if d < START_DATE:
        return f"O plano começa em {START_DATE.strftime('%d/%m/%Y')}. Hoje é {d.strftime('%d/%m/%Y')}."
    if d > RACE_DATE:
        return f"A prova já passou ({RACE_DATE.strftime('%d/%m/%Y')}). Posso gerar um novo plano se quiser."
    week = get_week_number_for_date(d)
    if not week:
        return "Não encontrei o treino para essa data."
    w = WEEK_OVERRIDES.get(week)
    wd = d.weekday()
    training = None
    if w and wd in w:
        training = w[wd]
    else:
        training = WEEKLY_TEMPLATE.get(wd, "Descanso")
    days_until_race = (RACE_DATE - d).days
    header = (
        f"Perfeito! Como hoje é {weekday_name_pt(d)}, {d.strftime('%d de %B de %Y')}, "
        f"você tem {days_until_race} dias até a prova de 5 km ({RACE_DATE.strftime('%d/%m')}).\n\n"
    )
    return header + training


# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("SIM", callback_data="yes"), InlineKeyboardButton("NÃO", callback_data="no")]
    ]
    reply_markup = InlineKeyboardMarkup(kb)
    await update.message.reply_text("Você quer saber o seu treino de hoje?", reply_markup=reply_markup)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "no":
        await query.edit_message_text("Tudo bem, até a próxima")
        return
    today = date.today()
    msg = get_training_for_date(today)
    await query.edit_message_text(msg)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Use /start para ver o treino de hoje.")


def main():
    token = TOKEN
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    logger.info("Bot iniciado...")
    app.run_polling()


if __name__ == "__main__":
    main()