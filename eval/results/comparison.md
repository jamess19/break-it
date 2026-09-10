# Eval — planning agent

Đo chất lượng agent xếp lịch tuần: seed task giả vào DB (cô lập) → agent nhận
"xếp lịch tuần này" → đọc lại plan từ DB → chấm theo assert. Chạy đúng
`engine.run()` thật, không mock.

Chạy: `python -m eval [--model NAME] [--gap SECONDS]` · cập nhật **2026-09-10**

## Phương pháp

- **DB cô lập**: `TRUNCATE tasks/plans/plan_slots/checklist_items/facts` giữa mỗi
  case → mỗi case bắt đầu từ rỗng.
- **Assert hard vs soft**:
  - HARD (hợp đồng — sai là FAIL): `plan_exists`, `all_p1_scheduled`, `nothing_after_deadline`
  - SOFT (chất lượng — chỉ báo): `no_day_over` (trần 6h/ngày), `total_hours_within`
    — estimate do người nhập nên vượt trần được, không phạt model
- **Số đo/case**: pass, steps, tool_calls, tokens, cost USD, latency

## Case (`eval/cases/planning.yaml`)

| id | tình huống | test gì |
|---|---|---|
| `basic_fit` | 3 việc / 9h, thừa chỗ | làm đúng chuyện dễ (không overload khi rảnh) |
| `split_big_task` | 1 task 10h > trần | tách task lớn ra nhiều ngày |
| `deadline_pressure` | báo cáo hạn thứ 3, việc khác đẩy sau | tôn trọng deadline |
| `overload_prioritize` | 18h P1 + 10h P3 | P1 phải đủ, P3 rớt là đúng |

## Kết quả — 3 model Groq (2026-09-10)

| model | pass | soft-fail | tổng tok (4 case) | cost | latency tb |
|---|---|---|---|---|---|
| **openai/gpt-oss-120b** | **4/4** | 0 | 22,248 | **$0.0060** | **15.6s** |
| openai/gpt-oss-20b | 4/4 | 0 | 31,029 | $0.0067 | 28.6s |
| qwen/qwen3.8-27b | 3/4 | 0 | 26,922¹ | $0.0084¹ | ~43s¹ |

¹ trừ case ERROR

### Chi tiết

| case | gpt-oss-120b | gpt-oss-20b | qwen3-27b |
|---|---|---|---|
| basic_fit | ✅ 3 step · 4.6s | ✅ 5 step · 9.0s | ✅ 3 step · 4.4s |
| split_big_task | ✅ 4 step · 6.5s | ✅ 4 step · 35.6s | ✅ 5 step · 65.6s |
| deadline_pressure | ✅ 3 step · 15.7s | ✅ 4 step · 34.7s | 💥 tool-call hỏng |
| overload_prioritize | ✅ 4 step · 35.7s | ✅ 4 step · 35.2s | ✅ 4 step · 59.6s |

## Nhận xét

- **gpt-oss-120b thắng rõ**: 4/4, ít step nhất (3–4), rẻ nhất, nhanh nhất, 0 soft-fail.
  Tôn trọng deadline, tách task lớn, không overload cả khi `no_day_over` chỉ soft.
- **gpt-oss-20b**: cũng 4/4 nhưng dài dòng hơn — nhiều step/token hơn ~40%, chậm 2x.
- **qwen3.8-27b: 3/4**. Trên `deadline_pressure` nó degrade sang pseudo-XML
  (`<function=save_plan>`, key rác `"task_id²"`) thay vì JSON → Groq reject 400
  `tool_use_failed`. qwen train với format tool-call kiểu Hermes/XML, khi rối rơi
  về format lai hỏng; gpt-oss (format OpenAI) không bị.
  → đã thêm `engine/loop.py` nhắc model gọi lại khi `tool_use_failed` (≤2 lần) —
  **cần chạy lại qwen xem có phục hồi không**.

## Caveat

- **Groq free tier không ổn định**: 429 + `ConnectTimeout` khi chạy nhiều call
  liên tục. `_http.py` retry (429/5xx + `TransportError`, backoff ≤30s) — nhưng
  latency vẫn nhiễu nặng (cùng model dao động 4s→35s giữa các case). Latency ở
  bảng KHÔNG phải tín hiệu model đáng tin.
- Cost ước lượng cho qwen (`(0.29, 0.59)` /1M) — cần verify giá Groq thật.

## TODO (eval v2)

- Chạy lại qwen sau fix tool-format recovery
- `scorers.llm_judge` cho case hội thoại (`cases/chat.yaml`)
- `.github/workflows/eval.yml` — CI chạy subset (fake provider / model rẻ)
