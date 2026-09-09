#!/usr/bin/env bash
#
# Curl thô để test API key / kết nối LLM. Đọc key từ .env.
#
#   bash tests/check_api_key.sh openai
#   bash tests/check_api_key.sh anthropic
#   bash tests/check_api_key.sh ollama
#
# Hoặc copy thẳng lệnh curl bên dưới, thay $OPENAI_API_KEY bằng key thật.

cd "$(dirname "$0")/.." || exit 1
[ -f .env ] && { set -a; . ./.env; set +a; }

PROVIDER="${1:-openai}"
MODEL="${2:-$MODEL}"           # arg#2 > MODEL trong .env

case "$PROVIDER" in

  openai)
    curl -i "${OPENAI_BASE_URL:-https://api.openai.com/v1}/chat/completions" \
      -H "Authorization: Bearer $OPENAI_API_KEY" \
      -H "Content-Type: application/json" \
      -d "{
        \"model\": \"${MODEL:-gpt-4o-mini}\",
        \"max_tokens\": 5,
        \"messages\": [{\"role\":\"user\",\"content\":\"reply with the word ok\"}]
      }"
    ;;

  anthropic)
    curl -i "https://api.anthropic.com/v1/messages" \
      -H "x-api-key: $ANTHROPIC_API_KEY" \
      -H "anthropic-version: 2023-06-01" \
      -H "Content-Type: application/json" \
      -d "{
        \"model\": \"${MODEL:-claude-haiku-4-5}\",
        \"max_tokens\": 5,
        \"messages\": [{\"role\":\"user\",\"content\":\"reply with the word ok\"}]
      }"
    ;;

  ollama)
    curl -i "${OLLAMA_BASE_URL:-http://localhost:11434/v1}/chat/completions" \
      -H "Content-Type: application/json" \
      -d "{
        \"model\": \"${MODEL:-qwen2.5:3b}\",
        \"stream\": false,
        \"messages\": [{\"role\":\"user\",\"content\":\"reply with the word ok\"}]
      }"
    ;;

esac
echo

# ── Đọc kết quả ──
#  HTTP/1.1 200  → OK, chạy tiếp: python -m scripts.try_call
#  401 / 403     → key sai
#  404           → sai model hoặc sai base_url
#  429           → hết quota / chưa nạp tiền / rate limit
#  (không phản hồi) → server chưa chạy / sai URL / mất mạng
