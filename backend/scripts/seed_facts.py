"""Nạp fact thói quen làm việc — chạy 1 lần.

    python -m scripts.seed_facts

Chỉ cần Postgres đang chạy (không cần key embedding — facts lưu phẳng, không vector).
Plan flow gọi tool `recall` (category="planning") để đọc lại các fact này khi xếp lịch
→ kế hoạch tôn trọng ràng buộc mềm.
"""

from __future__ import annotations

import asyncio

from app.api.deps import build_runtime

FACTS = [
    "Làm việc sâu (deep work) tốt nhất buổi sáng 9h–12h; buổi chiều để việc nhẹ và họp.",
    "Trần khoảng 6 giờ deep work mỗi ngày — đừng xếp quá tay.",
    "Thứ 6 giữ nhẹ: dành để review tuần và dọn việc tồn.",
    "Ưu tiên việc có deadline gần và priority cao (P1) trước.",
    "Task lớn hơn 3h nên tách ra nhiều ngày, không dồn 1 buổi, chỉ cần đảm bảo có output của ngày của task đó.",
]


async def main() -> None:
    rt = build_runtime()
    for f in FACTS:
        await rt.store.write_fact(f, source="seed:planning", meta={"category": "planning"})
        print("+", f)
    print(f"\nĐã nạp {len(FACTS)} fact.")


if __name__ == "__main__":
    asyncio.run(main())
