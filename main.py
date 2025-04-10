import logging
import os
import requests
import json
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from telegram import Update, InputMediaPhoto
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# 加載環境變數
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 配置日誌
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# API URL
API_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def get_fear_greed_data():
    """獲取 CNN Fear & Greed 指數的歷史數據"""
    try:
        response = requests.get(API_URL, headers=HEADERS)
        response.raise_for_status()
        data = response.json()

        if 'fear_and_greed_historical' not in data:
            logger.error("API 響應中缺少 'fear_and_greed_historical' 鍵")
            return None

        historical_data_dict = data['fear_and_greed_historical'] # Rename for clarity
        
        # 添加日誌：打印歷史數據字典類型和內容
        logger.info(f"獲取到的 historical_data_dict 類型: {type(historical_data_dict)}")
        logger.info(f"獲取到的 historical_data_dict 內容 (前 500 字元): {str(historical_data_dict)[:500]}") 

        # 檢查 historical_data_dict 是否是字典以及是否包含 'data' 鍵
        if not isinstance(historical_data_dict, dict) or 'data' not in historical_data_dict:
            logger.error("historical_data_dict 不是預期的字典格式或缺少 'data' 鍵")
            logger.info(f"實際內容: {historical_data_dict}")
            return None

        # 從字典中提取實際的歷史數據列表
        actual_historical_list = historical_data_dict['data']

        if not isinstance(actual_historical_list, list):
            logger.error("historical_data_dict 中的 'data' 不是列表")
            logger.info(f"'data' 的實際類型: {type(actual_historical_list)}")
            return None

        if not actual_historical_list:
            logger.error("恐懼與貪婪指數歷史數據列表 ('data' 鍵內部) 為空")
            return None
        
        logger.info(f"從 'data' 鍵提取到的 actual_historical_list 長度: {len(actual_historical_list)}")
        logger.info(f"actual_historical_list 第一個元素: {actual_historical_list[0]}")

        # 處理數據 (使用 actual_historical_list)
        time_series_data = []
        for item in actual_historical_list:
            if isinstance(item, dict) and 'x' in item and 'y' in item:
                time_series_data.append({
                    'timestamp': item['x'],
                    'value': item['y']
                })
            else:
                logger.warning(f"跳過不符合預期結構的 item: {item}")

        # 添加日誌：打印提取後的數據長度
        logger.info(f"提取到的 time_series_data 長度: {len(time_series_data)}")

        if not time_series_data:
            logger.error("無法從歷史數據中提取時間序列數據")
            return None

        # 創建 DataFrame
        df = pd.DataFrame(time_series_data)

        # 將時間戳轉換為日期時間 (從毫秒轉換)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        # 確保數據按時間排序
        df = df.sort_values('timestamp')

        # 過濾最近一年的數據 (從今天回推365天)
        # 使用 timezone-naive Timestamp for comparison
        last_year = pd.Timestamp.now().normalize() - pd.Timedelta(days=365)
        df = df[df['timestamp'] >= last_year]

        # 確保 value 列為數值類型
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        df = df.dropna(subset=['value']) # 移除 value 為 NaN 的行

        if df.empty:
            logger.error("處理後的恐懼與貪婪指數歷史數據為空 (最近一年)")
            return None

        logger.info(f"成功獲取並處理了 {len(df)} 筆歷史數據。")
        return df

    except requests.exceptions.RequestException as e:
        logger.error(f"請求歷史數據時發生錯誤: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"解析歷史數據 JSON 時發生錯誤: {e}")
        return None
    except Exception as e:
        logger.error(f"處理歷史數據時發生未預期的錯誤: {e}", exc_info=True) # Log stack trace
        return None

def get_current_fear_greed():
    """獲取 CNN Fear & Greed 指數的當前數據"""
    try:
        response = requests.get(API_URL, headers=HEADERS)
        response.raise_for_status()
        data = response.json()

        if 'fear_and_greed' not in data:
            logger.error("API 響應中缺少 'fear_and_greed' 鍵")
            return None, None

        current_data = data['fear_and_greed']
        score = current_data.get('score')
        rating = current_data.get('rating')

        if score is None or rating is None:
            logger.error("當前數據中缺少 'score' 或 'rating'")
            return None, None
        
        logger.info(f"成功獲取當前數據: score={score}, rating={rating}")
        return score, rating

    except requests.exceptions.RequestException as e:
        logger.error(f"請求當前數據時發生錯誤: {e}")
        return None, None
    except json.JSONDecodeError as e:
        logger.error(f"解析當前數據 JSON 時發生錯誤: {e}")
        return None, None
    except Exception as e:
        logger.error(f"處理當前數據時發生未預期的錯誤: {e}", exc_info=True)
        return None, None

def create_fear_greed_chart(df, filename="fear_greed_chart.png"):
    """根據 DataFrame 創建恐懼與貪婪指數圖表"""
    try:
        if df is None or df.empty:
            logger.error("無法創建圖表，因為 DataFrame 為空或 None")
            return None

        plt.style.use('seaborn-v0_8-darkgrid') # 使用現代化的樣式
        fig, ax = plt.subplots(figsize=(12, 6))

        # 繪製線圖
        ax.plot(df['timestamp'], df['value'], color='#1f77b4', linewidth=2, label='Fear & Greed Index')

        # 添加顏色區域以表示情緒
        ax.fill_between(df['timestamp'], 0, 25, color='#d62728', alpha=0.3, label='Extreme Fear (0-25)')
        ax.fill_between(df['timestamp'], 25, 45, color='#ff7f0e', alpha=0.3, label='Fear (25-45)')
        ax.fill_between(df['timestamp'], 45, 55, color='#bcbd22', alpha=0.3, label='Neutral (45-55)')
        ax.fill_between(df['timestamp'], 55, 75, color='#2ca02c', alpha=0.3, label='Greed (55-75)')
        ax.fill_between(df['timestamp'], 75, 100, color='#17becf', alpha=0.3, label='Extreme Greed (75-100)')
        
        # 添加水平線
        ax.axhline(25, color='gray', linestyle='--', linewidth=0.8)
        ax.axhline(45, color='gray', linestyle='--', linewidth=0.8)
        ax.axhline(55, color='gray', linestyle='--', linewidth=0.8)
        ax.axhline(75, color='gray', linestyle='--', linewidth=0.8)

        # 設置標題和標籤
        ax.set_title('CNN Fear & Greed Index (Last 12 Months)', fontsize=16)
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Index Value', fontsize=12)
        ax.set_ylim(0, 100) # Y 軸範圍固定為 0-100

        # 格式化 X 軸日期
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1)) # 每月顯示一個主刻度
        fig.autofmt_xdate() # 自動旋轉日期標籤以避免重疊

        # 添加圖例
        ax.legend(loc='upper left')

        # 調整佈局並保存
        plt.tight_layout()
        plt.savefig(filename)
        plt.close(fig) # 關閉圖表以釋放內存
        logger.info(f"圖表已成功保存到 {filename}")
        return filename

    except Exception as e:
        logger.error(f"創建圖表時發生錯誤: {e}", exc_info=True)
        return None

# 定義組件信息
COMPONENTS_INFO = {
    'market_momentum_sp500': {'title': 'Market Momentum (S&P 500)', 'color': '#1f77b4'},
    # 'market_momentum_sp125': {'title': 'Market Momentum (S&P 125)', 'color': '#ff7f0e'}, # 根據 API 確認鍵名
    'stock_price_strength': {'title': 'Stock Price Strength', 'color': '#2ca02c'},
    'stock_price_breadth': {'title': 'Stock Price Breadth', 'color': '#d62728'},
    'put_call_options': {'title': 'Put/Call Options', 'color': '#9467bd'},
    'market_volatility_vix': {'title': 'Market Volatility (VIX)', 'color': '#8c564b'},
    # 'market_volatility_vix_50': {'title': 'Market Volatility (VIX 50)', 'color': '#e377c2'},
    'junk_bond_demand': {'title': 'Junk Bond Demand', 'color': '#7f7f7f'},
    'safe_haven_demand': {'title': 'Safe Haven Demand', 'color': '#bcbd22'}
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理 /start 命令"""
    await update.message.reply_text(
        "您好！我是恐懼與貪婪指數機器人。\n"
        "使用 /feargreed 來獲取最新的指數和圖表。\n"
        "使用 /components 來獲取各組成指標的圖表。"
    )

async def feargreed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理 /feargreed 命令，獲取並發送總體指數和圖表"""
    chat_id = update.effective_chat.id
    logger.info(f"收到來自 chat_id {chat_id} 的 /feargreed 命令")

    processing_message = await update.message.reply_text("正在獲取數據和生成圖表，請稍候...")

    try:
        current_score, current_rating = get_current_fear_greed()
        if current_score is None or current_rating is None:
            await processing_message.edit_text("抱歉，無法獲取當前的恐懼與貪婪指數數據。")
            return

        df_historical = get_fear_greed_data() # 獲取總體歷史數據
        if df_historical is None:
            message = f"📊 *CNN 恐懼與貪婪指數更新*\n\n"
            message += f"當前指數：*{current_score:.2f}*\n"
            formatted_rating = current_rating.replace('_', ' ').title()
            message += f"市場情緒：*{formatted_rating}*\n\n"
            message += "無法獲取歷史數據以生成圖表。"
            await processing_message.edit_text(message, parse_mode='Markdown')
            return

        chart_filename = "fear_greed_chart.png"
        chart_path = create_fear_greed_chart(df_historical, filename=chart_filename)

        message = f"📊 *CNN 恐懼與貪婪指數更新*\n\n"
        message += f"當前指數：*{current_score:.2f}*\n"
        formatted_rating = current_rating.replace('_', ' ').title()
        message += f"市場情緒：*{formatted_rating}*\n\n"

        if chart_path:
            message += "圖表顯示過去12個月的趨勢："
            await processing_message.edit_text(message, parse_mode='Markdown')
            with open(chart_path, 'rb') as photo:
                await update.message.reply_photo(photo=photo)
            # os.remove(chart_path)
        else:
            message += "無法生成總體指數圖表。"
            await processing_message.edit_text(message, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"處理 /feargreed 命令時發生錯誤: {e}", exc_info=True)
        try:
            await processing_message.edit_text("抱歉，處理 /feargreed 請求時發生內部錯誤。")
        except Exception as inner_e:
            logger.error(f"編輯 /feargreed 錯誤訊息時也發生錯誤: {inner_e}")

async def components(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理 /components 命令，獲取並發送各組成指標圖表"""
    chat_id = update.effective_chat.id
    logger.info(f"收到來自 chat_id {chat_id} 的 /components 命令")

    processing_message = await update.message.reply_text("正在獲取各組件數據並生成圖表，請稍候...")

    media_group = []
    chart_files_to_delete = []
    has_error = False

    for key, info in COMPONENTS_INFO.items():
        title = info['title']
        color = info['color']
        logger.info(f"正在處理組件: {title} ({key})")
        component_df = get_component_data(key)
        
        if component_df is not None:
            chart_filename = f"component_{key}_chart.png"
            chart_path = create_component_chart(component_df, title, chart_filename, color)
            if chart_path:
                media_group.append(InputMediaPhoto(media=open(chart_path, 'rb')))
                chart_files_to_delete.append(chart_path)
            else:
                logger.error(f"無法為組件 {key} 生成圖表")
                has_error = True
        else:
            logger.error(f"無法獲取組件 {key} 的數據")
            has_error = True

    try:
        if media_group:
            await processing_message.delete() # 刪除提示訊息
            await update.message.reply_text("以下是各組成指標過去12個月的趨勢圖：")
            # 分批發送圖片，避免超過 Telegram Media Group 限制 (通常是10張)
            for i in range(0, len(media_group), 10):
                await update.message.reply_media_group(media=media_group[i:i+10])
            if has_error:
                 await update.message.reply_text("(部分組件圖表可能因錯誤無法生成)")
        elif has_error:
            await processing_message.edit_text("抱歉，無法獲取或生成任何組件的圖表。請檢查日誌。")
        else:
            # 理論上不應該發生，除非 COMPONENTS_INFO 是空的
             await processing_message.edit_text("沒有設定任何組件指標。")

    except Exception as e:
        logger.error(f"發送組件圖表時發生錯誤: {e}", exc_info=True)
        try:
            # 如果發送 media group 失敗，嘗試只發送錯誤訊息
            await processing_message.edit_text("抱歉，發送組件圖表時發生錯誤。")
        except Exception as inner_e:
             logger.error(f"編輯 /components 錯誤訊息時也發生錯誤: {inner_e}")
    finally:
        # 清理生成的圖表文件
        for f in chart_files_to_delete:
            try:
                # 確保關閉文件句柄（雖然 media_group 應該會處理，但以防萬一）
                # photo_file = next((p.media for p in media_group if p.media.name == f), None)
                # if photo_file and not photo_file.closed:
                #    photo_file.close()
                os.remove(f)
                logger.info(f"已刪除臨時圖表文件: {f}")
            except Exception as e:
                logger.error(f"刪除臨時圖表文件 {f} 時發生錯誤: {e}")

def get_component_data(component_key: str):
    """獲取指定 CNN Fear & Greed 組件指標的歷史數據"""
    try:
        response = requests.get(API_URL, headers=HEADERS)
        response.raise_for_status()
        data = response.json()

        if component_key not in data:
            logger.error(f"API 響應中缺少 '{component_key}' 鍵")
            return None

        component_data_dict = data[component_key]
        
        # 檢查 component_data_dict 是否是字典以及是否包含 'data' 鍵
        if not isinstance(component_data_dict, dict) or 'data' not in component_data_dict:
            logger.error(f"'{component_key}' 的值不是預期的字典格式或缺少 'data' 鍵")
            logger.info(f"實際內容: {component_data_dict}")
            return None

        # 從字典中提取實際的歷史數據列表
        actual_component_list = component_data_dict['data']

        if not isinstance(actual_component_list, list):
            logger.error(f"'{component_key}' 字典中的 'data' 不是列表")
            logger.info(f"'data' 的實際類型: {type(actual_component_list)}")
            return None

        if not actual_component_list:
            logger.error(f"組件 '{component_key}' 的歷史數據列表 ('data' 鍵內部) 為空")
            return None
        
        logger.info(f"成功獲取組件 '{component_key}' 的原始數據列表，長度: {len(actual_component_list)}")

        # 處理數據 (使用 actual_component_list)
        time_series_data = []
        for item in actual_component_list:
            if isinstance(item, dict) and 'x' in item and 'y' in item:
                # 注意：有些組件的值可能需要特殊處理，但我們先假設都是數值
                time_series_data.append({
                    'timestamp': item['x'],
                    'value': item['y'] 
                })
            else:
                logger.warning(f"[{component_key}] 跳過不符合預期結構的 item: {item}")
        
        if not time_series_data:
            logger.error(f"無法從組件 '{component_key}' 的數據中提取時間序列數據")
            return None

        # 創建 DataFrame
        df = pd.DataFrame(time_series_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.sort_values('timestamp')

        # 過濾最近一年的數據
        last_year = pd.Timestamp.now().normalize() - pd.Timedelta(days=365)
        df = df[df['timestamp'] >= last_year]

        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        df = df.dropna(subset=['value'])

        if df.empty:
            logger.error(f"處理後的組件 '{component_key}' 數據為空 (最近一年)")
            return None

        logger.info(f"成功處理了組件 '{component_key}' 的 {len(df)} 筆歷史數據。")
        return df

    except requests.exceptions.RequestException as e:
        logger.error(f"請求組件 '{component_key}' 數據時發生錯誤: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"解析組件 '{component_key}' JSON 時發生錯誤: {e}")
        return None
    except Exception as e:
        logger.error(f"處理組件 '{component_key}' 數據時發生未預期的錯誤: {e}", exc_info=True)
        return None

def create_component_chart(df, title: str, filename: str, color='#1f77b4'):
    """根據 DataFrame 創建指定組件的圖表"""
    try:
        if df is None or df.empty:
            logger.error(f"無法創建圖表 '{title}'，因為 DataFrame 為空或 None")
            return None

        plt.style.use('seaborn-v0_8-darkgrid') 
        fig, ax = plt.subplots(figsize=(10, 5)) # 可以稍微調整大小

        # 繪製線圖
        ax.plot(df['timestamp'], df['value'], color=color, linewidth=1.5)

        # 設置標題和標籤
        ax.set_title(f'{title} (Last 12 Months)', fontsize=14)
        ax.set_xlabel('Date', fontsize=10)
        ax.set_ylabel('Value', fontsize=10)
        
        # 格式化 X 軸日期
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2)) # 可以調整刻度間隔
        fig.autofmt_xdate()

        # 調整佈局並保存
        plt.tight_layout()
        plt.savefig(filename)
        plt.close(fig)
        logger.info(f"組件圖表 '{title}' 已成功保存到 {filename}")
        return filename

    except Exception as e:
        logger.error(f"創建組件圖表 '{title}' 時發生錯誤: {e}", exc_info=True)
        return None

async def scheduled_feargreed(app: Application):
    """定時執行的任務：發送總體指數和圖表"""
    logger.info("執行定時任務：scheduled_feargreed")
    if not TELEGRAM_CHAT_ID:
        logger.error("定時任務 scheduled_feargreed 無法執行：未設定 TELEGRAM_CHAT_ID")
        return

    bot = app.bot
    chat_id = TELEGRAM_CHAT_ID

    try:
        # 發送提示訊息 (可選)
        # await bot.send_message(chat_id=chat_id, text="定時任務：正在獲取 Fear & Greed 數據...")

        current_score, current_rating = get_current_fear_greed()
        if current_score is None or current_rating is None:
            await bot.send_message(chat_id=chat_id, text="定時任務錯誤：無法獲取當前的恐懼與貪婪指數數據。")
            return

        df_historical = get_fear_greed_data()
        if df_historical is None:
            message = f"📊 *CNN 恐懼與貪婪指數 (定時更新)*\n\n"
            message += f"當前指數：*{current_score:.2f}*\n"
            formatted_rating = current_rating.replace('_', ' ').title()
            message += f"市場情緒：*{formatted_rating}*\n\n"
            message += "無法獲取歷史數據以生成圖表。"
            await bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
            return

        chart_filename = "scheduled_fear_greed_chart.png" # 使用不同檔名避免衝突
        chart_path = create_fear_greed_chart(df_historical, filename=chart_filename)

        message = f"📊 *CNN 恐懼與貪婪指數 (定時更新)*\n\n"
        message += f"當前指數：*{current_score:.2f}*\n"
        formatted_rating = current_rating.replace('_', ' ').title()
        message += f"市場情緒：*{formatted_rating}*\n\n"

        if chart_path:
            message += "圖表顯示過去12個月的趨勢："
            await bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
            try:
                with open(chart_path, 'rb') as photo:
                    await bot.send_photo(chat_id=chat_id, photo=photo)
            finally:
                 # 無論成功或失敗都嘗試刪除文件
                if os.path.exists(chart_path):
                    os.remove(chart_path)
                    logger.info(f"已刪除定時任務圖表文件: {chart_path}")
        else:
            message += "無法生成總體指數圖表。"
            await bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"執行定時任務 scheduled_feargreed 時發生錯誤: {e}", exc_info=True)
        try:
            await bot.send_message(chat_id=chat_id, text="定時任務 scheduled_feargreed 執行失敗。")
        except Exception as inner_e:
            logger.error(f"發送 scheduled_feargreed 錯誤通知時也發生錯誤: {inner_e}")

async def scheduled_components(app: Application):
    """定時執行的任務：發送各組成指標圖表"""
    logger.info("執行定時任務：scheduled_components")
    if not TELEGRAM_CHAT_ID:
        logger.error("定時任務 scheduled_components 無法執行：未設定 TELEGRAM_CHAT_ID")
        return

    bot = app.bot
    chat_id = TELEGRAM_CHAT_ID
    media_group = []
    chart_files_to_delete = []
    opened_files = [] # 追蹤打開的文件以便關閉
    has_error = False

    try:
        # await bot.send_message(chat_id=chat_id, text="定時任務：正在獲取各組件數據...")

        for key, info in COMPONENTS_INFO.items():
            title = info['title']
            color = info['color']
            logger.info(f"定時任務：正在處理組件: {title} ({key})")
            component_df = get_component_data(key)

            if component_df is not None:
                chart_filename = f"scheduled_component_{key}_chart.png" # 使用不同檔名
                chart_path = create_component_chart(component_df, title, chart_filename, color)
                if chart_path:
                    try:
                        # 打開文件並添加到列表，以便稍後關閉
                        photo_file = open(chart_path, 'rb')
                        opened_files.append(photo_file)
                        media_group.append(InputMediaPhoto(media=photo_file))
                        chart_files_to_delete.append(chart_path)
                    except Exception as file_e:
                         logger.error(f"打開或處理圖表文件 {chart_path} 時出錯: {file_e}")
                         has_error = True
                         # 如果文件已打開但添加到 media_group 失敗，也需確保關閉
                         if 'photo_file' in locals() and photo_file and not photo_file.closed:
                             photo_file.close()
                         if os.path.exists(chart_path):
                            chart_files_to_delete.append(chart_path) # 仍然嘗試刪除
                else:
                    logger.error(f"定時任務：無法為組件 {key} 生成圖表")
                    has_error = True
            else:
                logger.error(f"定時任務：無法獲取組件 {key} 的數據")
                has_error = True

        if media_group:
            await bot.send_message(chat_id=chat_id, text="定時更新：以下是各組成指標過去12個月的趨勢圖：")
            for i in range(0, len(media_group), 10):
                await bot.send_media_group(chat_id=chat_id, media=media_group[i:i+10])
            if has_error:
                 await bot.send_message(chat_id=chat_id, text="(部分組件圖表可能因錯誤無法生成)")
        elif has_error:
            await bot.send_message(chat_id=chat_id, text="定時任務錯誤：無法獲取或生成任何組件的圖表。請檢查日誌。")
        else:
             await bot.send_message(chat_id=chat_id, text="定時任務：沒有設定任何組件指標。")

    except Exception as e:
        logger.error(f"執行定時任務 scheduled_components 時發生錯誤: {e}", exc_info=True)
        try:
            await bot.send_message(chat_id=chat_id, text="定時任務 scheduled_components 執行失敗。")
        except Exception as inner_e:
            logger.error(f"發送 scheduled_components 錯誤通知時也發生錯誤: {inner_e}")
    finally:
        # 關閉所有打開的文件句柄
        for f in opened_files:
            if not f.closed:
                f.close()
        # 清理生成的圖表文件
        for f_path in chart_files_to_delete:
            if os.path.exists(f_path):
                try:
                    os.remove(f_path)
                    logger.info(f"已刪除定時任務圖表文件: {f_path}")
                except Exception as e:
                    logger.error(f"刪除定時任務圖表文件 {f_path} 時發生錯誤: {e}")

if __name__ == '__main__':
    logger.info("機器人啟動中...")

    if not TELEGRAM_BOT_TOKEN:
        logger.critical("錯誤：未設置 TELEGRAM_BOT_TOKEN 環境變數！")
        exit()
    
    # 檢查 Chat ID 是否設定，對於定時任務是必要的
    if not TELEGRAM_CHAT_ID:
       logger.critical("錯誤：未設置 TELEGRAM_CHAT_ID 環境變數！定時任務需要此設定。")
       exit() 
    else:
        logger.info(f"定時任務將發送到 Chat ID: {TELEGRAM_CHAT_ID}")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # 註冊命令處理器
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("feargreed", feargreed))
    application.add_handler(CommandHandler("components", components))

    # --- 新增：設定並啟動排程器 ---
    try:
        scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Taipei'))
        
        # 每天早上 8:00 執行 scheduled_feargreed
        scheduler.add_job(
            scheduled_feargreed, 
            trigger=CronTrigger(hour=8, minute=0, second=0), 
            args=[application], # 將 application 實例傳遞給任務
            id='job_feargreed', # 為任務指定 ID
            replace_existing=True # 如果已存在同 ID 任務則替換
        )
        logger.info("已安排 scheduled_feargreed 任務在每天 08:00 (Asia/Taipei) 執行。")

        # 每天早上 8:01 執行 scheduled_components (稍微錯開)
        scheduler.add_job(
            scheduled_components, 
            trigger=CronTrigger(hour=8, minute=1, second=0), 
            args=[application], # 將 application 實例傳遞給任務
            id='job_components', # 為任務指定 ID
            replace_existing=True
        )
        logger.info("已安排 scheduled_components 任務在每天 08:01 (Asia/Taipei) 執行。")

        scheduler.start()
        logger.info("排程器已啟動。")
        
    except Exception as e:
        logger.error(f"初始化或啟動排程器時發生錯誤: {e}", exc_info=True)
        # 即使排程器失敗，仍然嘗試運行 polling 以處理手動命令
    # --- 排程器設定結束 ---

    logger.info("機器人正在啟動 polling 模式以監聽手動命令...")
    # 開始運行機器人 (polling 會阻塞主線程)
    application.run_polling()
