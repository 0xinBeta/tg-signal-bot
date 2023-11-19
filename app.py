from dotenv import load_dotenv
import os
import logging
from telegram.ext import Application
import ccxt
from ret_db import get_trade_parameters
import asyncio
from df_maker import create_df
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

trade_params = []
is_params_updated = False
bot_instance = None


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
        symbol, 2)
    round_decimal_pos = round_decimal_pos_map.get(
        symbol, 2)

    return round_decimal_price, round_decimal_pos


async def send_signal_to_channel(message):
    global bot_instance
    try:
        await bot_instance.send_message(chat_id=channel_id, text=message)
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


async def periodic_trade_logic(exchange):
    global trade_params
    while True:
        if trade_params:
            for param in trade_params:
                await trade_logic(exchange=exchange, symbol=param['symbol'], timeframe=param['timeframe'], tp_m=param['tp_m'], sl_m=param['sl_m'])
        await asyncio.sleep(1)


async def daily_update_trade_parameters():
    global trade_params, is_params_updated
    while True:
        try:
            trade_params = get_trade_parameters()
            is_params_updated = True
            logger.info("Trade parameters updated.")
        except Exception as e:
            logger.error(f"Error updating trade parameters: {e}")

        await asyncio.sleep(86400)


async def trade_logic(exchange, symbol, timeframe, tp_m, sl_m):
    global trade_params, is_params_updated
    logger.info(f"Executing trade logic for {symbol} on {timeframe}.")

    try:
        df = create_df(exchange=exchange, symbol=symbol,
                       time_frame=timeframe, limit=LIMIT)
        long_signal = df['long'].iloc[-2]
        short_signal = df['short'].iloc[-2]

        if long_signal or short_signal:
            entry_price = df['Open'].iloc[-1]
            atr = df['ATR'].iloc[-2]
            direction = 'long' if long_signal else 'short'
            sl, tp = calculate_order_details(
                entry_price, atr, symbol, direction, tp_m, sl_m)

            # Send signal to channel
            signal_message = (
                f"🔔 {'📈 LONG' if long_signal else '📉 SHORT'} Signal for {symbol} on {timeframe} 🔔\n"
                f"🎯 Entry Price: {entry_price}\n"
                f"🛑 Stop Loss (SL): {sl}\n"
                f"✅ Take Profit (TP): {tp}\n"
                f"⚖️ Max Leverage: use maximum leverage possible!\n"
                f"⚠️ Risk Warning: Only risk 0.5% of your equity per trade.\n"
                f"🔄 Trade Safely!"
            )
            await send_signal_to_channel(signal_message)

        await asyncio.sleep(1)

    except ccxt.NetworkError as e:
        logging.error(f'NetworkError: {str(e)}')
        await asyncio.sleep(60)
    except Exception as e:
        logging.error(f'An unexpected error occurred: {str(e)}')
        sys.exit()


def main():
    global bot_instance
    # Initialize the Telegram bot application
    application = Application.builder().token(tg_token).build()

    bot_instance = application.bot

    exchange = ccxt.binanceusdm({"enableRateLimit": True})

    # Create and start the async event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Start the periodic trade logic and daily update tasks
    loop.create_task(periodic_trade_logic(exchange=exchange))
    loop.create_task(daily_update_trade_parameters())

    loop.create_task(application.run_polling())

    try:
        logger.info("Bot is running.")
        loop.run_forever()
    finally:
        loop.close()


if __name__ == "__main__":
    main()
