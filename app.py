from dotenv import load_dotenv
import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackContext
import ccxt
from ret_db import get_trade_parameters
import asyncio
from df_maker import create_df_async
import sys



load_dotenv()

tg_token = os.getenv("BOT_TOKEN")
channel_id = "@oxin_signals"  # Replace with your channel ID or username

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Constants
LIMIT = 500
RISK_PERCENTAGE = 0.005

async def set_max_leverage(exchange, symbol, coin):
    """
    Fetch the maximum leverage and set it for the given symbol.
    """
    available_tiers = await exchange.fetch_leverage_tiers(symbols=[symbol])
    max_lev = int(available_tiers[f'{coin}/USDT:USDT'][0]['maxLeverage'])
    return max_lev


def get_rounding_values(symbol):
    round_decimal_price_map = {
        "BTCUSDT": 1,
        "ETHUSDT": 2,
        "ADAUST": 4,
        "SANDUSDT": 4,
        "BNBUSDT": 2,
        "MATICUSDT": 4,
        "XRPUSDT": 4,
        "APEUSDT": 3,
        "LTCUSDT": 2,
        "LINKUSDT": 3,
    }

    round_decimal_pos_map = {
        "BTCUSDT": 3,
        "ETHUSDT": 3,
        "ADAUST": 0,
        "SANDUSDT": 0,
        "BNBUSDT": 2,
        "MATICUSDT": 0,
        "XRPUSDT": 0,
        "APEUSDT": 0,
        "LTCUSDT": 3,
        "LINKUSDT": 2,
    }

    round_decimal_price = round_decimal_price_map.get(
        symbol, 2)  # Default to 2 if symbol not found
    round_decimal_pos = round_decimal_pos_map.get(
        symbol, 2)     # Default to 2 if symbol not found

    return round_decimal_price, round_decimal_pos

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message with two inline buttons attached."""

async def send_signal_to_channel(context, message):
    try:
        await context.bot.send_message(chat_id=channel_id, text=message)
    except Exception as e:
        logger.error(f"Error sending signal message: {e}")


def calculate_order_details(entry_price, atr, symbol, direction, tp_multiplier, sl_multiplier):
    """
    Calculate the position size, stop loss, and take profit based on entry price, ATR, balance, and multipliers.
    """
    round_decimal_price, _ = get_rounding_values(symbol)

    sl_multiplier = sl_multiplier if direction == 'long' else -sl_multiplier
    tp_multiplier = tp_multiplier if direction == 'long' else -tp_multiplier

    sl = entry_price - round((atr * sl_multiplier), round_decimal_price)
    tp = entry_price + round((atr * tp_multiplier), round_decimal_price)

    return sl, tp


async def trade_logic(context, exchange, symbol, timeframe, tp_m, sl_m):
    """
    The core trading logic for a symbol.
    """
    while True:
        try:
            df = await create_df_async(exchange=exchange, symbol=symbol, time_frame=timeframe, limit=LIMIT)

            long_signal = df['long'].iloc[-2]
            short_signal = df['short'].iloc[-2]

            if long_signal or short_signal:
                max_lev = await set_max_leverage(exchange, symbol, coin=symbol[:-4])
                entry_price = df['Open'].iloc[-1]
                atr = df['ATR'].iloc[-2]
                direction = 'long' if long_signal else 'short'
                _, sl, tp = calculate_order_details(entry_price, atr, symbol, direction, tp_m, sl_m)
                
                # Send signal to channel
                signal_message = (
    f"🔔 {'📈 LONG' if long_signal else '📉 SHORT'} Signal for {symbol} 🔔\n"
    f"🎯 Entry Price: {entry_price}\n"
    f"🛑 Stop Loss (SL): {sl}\n"
    f"✅ Take Profit (TP): {tp}\n"
    f"⚖️ Max Leverage: {max_lev}x\n"
    f"⚠️ Risk Warning: Only risk 0.5% of your equity per trade.\n"
    f"🔄 Trade Safely!"
)
                await send_signal_to_channel(context, signal_message)

            await asyncio.sleep(1)

        except ccxt.NetworkError as e:
            logging.error(f'NetworkError: {str(e)}')
            await asyncio.sleep(60)
        except Exception as e:
            logging.error(f'An unexpected error occurred: {str(e)}')
            sys.exit()

async def signal_checking_job(context: CallbackContext):
    exchange = ccxt.binanceusdm({
        "enableRateLimit": True,
    })
    trade_params = get_trade_parameters()

    if not trade_params:
        logger.info("No trading today, trade parameters are empty.")
        return  # Skip until the next scheduled job

    tasks = [trade_logic(context.bot, exchange, param['symbol'], param['timeframe'],
                         param['tp_m'], param['sl_m']) for param in trade_params]
    await asyncio.gather(*tasks)

def main() -> None:
    application = Application.builder().token(tg_token).build()

    # Add the command and message handlers
    application.add_handler(CommandHandler("start", start))

    # Create a job queue and start the job
    job_queue = application.job_queue
    job_queue.run_repeating(signal_checking_job, interval=86400)  # Run every day

    application.run_polling()

if __name__ == "__main__":
    main()
