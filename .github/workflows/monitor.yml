name: Carnegie 3163 价格监控

on:
  schedule:
    - cron: "0 21 * * *"    # 08:00 AEDT
    - cron: "0 1 * * *"     # 12:00 AEDT
    - cron: "0 7 * * *"     # 18:00 AEDT
  workflow_dispatch:

jobs:
  monitor:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    # Playwright 需要更多时间，给足 15 分钟
    timeout-minutes: 15

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: 安装 Python 依赖
        run: pip install -r requirements.txt

      # Playwright 需要单独安装浏览器二进制
      - name: 安装 Playwright 浏览器
        run: playwright install chromium --with-deps

      - name: 运行价格监控
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python monitor.py

      - name: 提交价格历史
        run: |
          git config user.name  "price-bot"
          git config user.email "bot@noreply.github.com"
          git add data/prices.json
          git diff --staged --quiet || \
            git commit -m "prices: $(date +'%Y-%m-%d %H:%M') AEDT" && git push
