# CNN 恐懼與貪婪指數 Telegram 機器人

這個專案是一個 Telegram 機器人，用於追蹤 CNN 恐懼與貪婪指數（Fear & Greed Index）並自動發送更新。該指數是一個反映投資者市場情緒的指標，從極度恐懼到極度貪婪，有助於判斷市場情緒。

## 功能

- `/start` - 開始使用機器人
- `/feargreed` - 手動獲取當前的恐懼與貪婪指數、市場情緒和過去12個月的趨勢圖
- `/components` - 獲取構成恐懼與貪婪指數的各組成指標圖表
- **定時更新**：每天早上 8:00 (台北時間) 自動發送恐懼與貪婪指數更新
- **組件分析**：每天早上 8:01 (台北時間) 自動發送各組成指標圖表

## 必要條件

- Python 3.7+
- Telegram Bot Token（從 [BotFather](https://t.me/botfather) 獲取）
- Telegram Chat ID（可通過 [@userinfobot](https://t.me/userinfobot) 或其他方式獲取）

## 安裝

### 方法 1：直接運行

1. 克隆存儲庫：
   ```bash
   git clone <repository-url>
   cd greed_n_fear
   ```

2. 建立虛擬環境並安裝依賴項：
   ```bash
   python -m venv venv
   source venv/bin/activate  # 在 Windows 上使用 venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. 創建 `.env` 文件並添加以下內容：
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   TELEGRAM_CHAT_ID=your_chat_id_here
   ```

4. 運行機器人：
   ```bash
   python main.py
   ```

### 方法 2：使用 Docker

1. 克隆存儲庫：
   ```bash
   git clone <repository-url>
   cd greed_n_fear
   ```

2. 建構 Docker 映像檔：
   ```bash
   docker build -t fear-greed-bot .
   ```

3. 運行 Docker 容器：
   ```bash
   docker run -d --name fear-greed-container \
     -e TELEGRAM_BOT_TOKEN="your_bot_token_here" \
     -e TELEGRAM_CHAT_ID="your_chat_id_here" \
     --restart unless-stopped \
     fear-greed-bot
   ```

## 使用方法

1. 在 Telegram 中找到您創建的機器人並發送 `/start` 命令。
2. 使用以下命令獲取數據：
   - `/feargreed` - 獲取當前恐懼與貪婪指數和圖表
   - `/components` - 獲取各組成指標圖表

## Docker 管理

- **查看日誌**：
  ```bash
  docker logs fear-greed-container
  ```

- **持續追蹤日誌**：
  ```bash
  docker logs fear-greed-container -f
  ```

- **停止容器**：
  ```bash
  docker stop fear-greed-container
  ```

- **啟動容器**：
  ```bash
  docker start fear-greed-container
  ```

- **移除容器**：
  ```bash
  docker rm fear-greed-container
  ```

## 自動更新設定

機器人配置了以下定時任務：

1. **每日總體指數更新**：
   - 時間：每天早上 8:00 (台北時間)
   - 內容：恐懼與貪婪指數當前值、市場情緒和趨勢圖

2. **每日組件指標更新**：
   - 時間：每天早上 8:01 (台北時間)
   - 內容：各組成指標的趨勢圖

這些更新會自動發送到您在 `.env` 或 Docker 環境變數中設定的 `TELEGRAM_CHAT_ID`。

## 技術說明

- 數據來源：CNN Fear & Greed API
- 使用 python-telegram-bot 實現 Telegram 機器人功能
- 使用 APScheduler 實現定時任務
- 使用 matplotlib 生成圖表

## 疑難排解

如果您遇到問題：

1. 檢查 `.env` 文件中的 Token 和 Chat ID 是否正確。
2. 確保您的 Telegram Bot 已啟動（與 BotFather 交談並檢查）。
3. 查看日誌以獲取更多詳細信息。

## 授權

[選擇適當的授權] 