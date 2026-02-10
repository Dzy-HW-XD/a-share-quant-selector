#!/bin/bash
# A股量化选股系统 - 快捷命令脚本

QUANT_DIR="/root/quant-csv"
PYTHON="/usr/bin/python3"

cd "$QUANT_DIR" || exit 1

case "$1" in
    init)
        $PYTHON main.py init
        ;;
    update)
        $PYTHON main.py update
        ;;
    select)
        $PYTHON main.py select
        ;;
    run)
        $PYTHON main.py run
        ;;
    schedule)
        $PYTHON main.py schedule
        ;;
    web)
        $PYTHON main.py web "${@:2}"
        ;;
    *)
        echo "使用方法: $0 {init|update|select|run|schedule}"
        echo ""
        echo "命令说明:"
        echo "  init     - 首次全量抓取6年历史数据"
        echo "  update   - 每日增量更新"
        echo "  select   - 执行选股策略"
        echo "  run      - 完整流程（更新+选股+通知）"
        echo "  schedule - 启动定时调度"
        exit 1
        ;;
esac
