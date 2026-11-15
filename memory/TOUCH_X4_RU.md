# Touch x4 — мод «4 пальца» (AML)

Памятка для Claude. Обновлять при каждой работе над модом (версия, что изменилось, новые факты, открытые вопросы).
Общие правила работы с пользователем и его устройство — в `PROJECT_MEMORY_RU.txt`.

## 1. Что это и статус
- AML-мод `libMultiTouch64.so` для GTA San Andreas Android (arm64): игра начинает принимать до 4 пальцев вместо 2.
- **Версия 1.2. Проверена пользователем на планшете: «очень хорошо всё работает».**
- Пользователь решил пока не публиковать его отдельно.
- Лог на устройстве: `mods/touch4_log.txt`. Нормальный лог 1.2:
  `Points -> 4 entries`, `limits lifted (...)`, `4-finger input enabled`, `Mods Settings item id N`,
  `Use2Touches = false: the game now gets up to 4 fingers`.

## 2. Файлы, сборка, тесты, выпуск
- `touch4/touch4.c` — весь мод, C без libc.
- `touch4/gtasa_offsets.h` — смещения и ожидаемые инструкции из `libGTASA.so` пользователя.
- `touch4/build.sh` — сборка без NDK: `clang --target=aarch64-linux-android21` + `lld`, заглушки `libc.so` / `libdl.so`
  только с именами символов. Выход: `build/touch4/libMultiTouch64.so` (копия лежит в `touch4/`).
- `touch4/test_touch4.py` — эмулятор arm64 (unicorn) на настоящем `libGTASA.so`, 381 проверка.
- `touch4/README_RU.txt` — описание для пользователя.
- Команды: `sh touch4/build.sh` ; `python3 touch4/test_touch4.py путь/к/libGTASA.so`
- Установка у пользователя: файл в `Android_unprotected/data/com.rockstargames.gtasa/mods/`.
- Настройка: Настройки игры > Mods Settings > «4-Finger Touch: On/Off»; хранится в
  `configs/net.helicover.touch4.ini` (`Enabled = 0|1`).

## 3. Как устроено
Почему игра знает только два пальца (найдено в `libGTASA.so`):
- `OS_PointerGetNumber()` возвращает 2 -> `CTouchInterface::m_nMaxTouches = 2`;
- `LIB_PointerGet*` / `OS_PointerGetType` отвергают индекс > 1;
- `AND_TouchEvent()` пишет в `Points[2]` (по 0x1c байт);
- JNI-вход на 4 пальца `NVEventMultiTouchEvent4` — пустая заглушка (`return 1`), очередь событий несёт 2 пальца;
- Java шлёт 4 пальца, только когда `NvEventQueueActivity.Use2Touches == false`.

Что делает мод при загрузке (только если КАЖДАЯ инструкция, на которую он опирается, совпала с ожидаемой):
1. GOT-запись `Points` -> своя копия на 4 записи;
2. снимает лимиты (`OS_PointerGetNumber` -> 4, проверки индексов -> 3, `m_nMaxTouches = 4`);
3. перехват `ProcessEvents()` (поток игры): раздаёт накопленные касания через `AND_TouchEvent(type, slot, x, y)`;
4. заглушка `NVEventMultiTouchEvent4` -> `ldr x16, <mt2+16>; br x16`; перехват 2-пальцевого входа. При первом касании
   через JNI ставит `Use2Touches = false` (APK менять не нужно) и дальше сам ведёт пальцы по `MotionEvent.getPointerId`
   (палец держит свой слот, пока не поднят);
5. пункт в Mods Settings через SAUtils (`ISAUtils` слот 3 `AddClickableItem`, тип 5 = `SetType_Mods`).
При любом несовпадении — «nothing changed» в логе, игра остаётся с 2 пальцами.

Смещения (`gtasa_offsets.h`): `AND_TouchEvent` 0x31ec0c, `NVEventMultiTouchEvent` 0x32a6d4, заглушка MT4 0x32ab10,
`ProcessEvents` 0x31e778, GOT `Points` 0x851d38, `Points` 0x8b4ebc (шаг 0x1c, состояние по +8), `m_nMaxTouches` 0x85e748.
Коды типов `AND_TouchEvent`: 1 up, 2 down, 3 move, 4 cancel.

Переходники (возврат в оригинал): первые инструкции функции лежат в самом `.so` (`pe_orig_tramp`, `mt2_orig_tramp`) и
сверяются с игрой; прыжок назад через адрес в данных. Новая исполняемая память не выделяется.

## 4. Грабли
- v1.1 выделяла исполняемую страницу рядом с `libGTASA` — на планшете лог «no executable page near libGTASA».
  Поэтому в 1.2 переходники внутри `.so`. Не возвращаться к `mmap` с `PROT_EXEC`.
- Структура `ModInfo` AML: поля guid / name / version / author + массив версии, дальше загрузчик может хранить своё —
  объект дополнен нулями (336 байт).
- Из-за мода `Points` в игре — уже не оригинальный массив: кто читает касания напрямую (другие моды), должен идти
  через GOT 0x851d38.

## 5. Пожелания пользователя
- Всё ставится с телефона, без ПК. Включение / выключение — из настроек игры.

## 6. Открыто
- Ничего. Публикация — по решению пользователя.

## 7. Журнал
- v1.0 — базовая версия.
- v1.1 — пальцы по pointer id (не «теряются»), пункт в Mods Settings.
- v1.2 (PR #24) — без новой исполняемой памяти; подтверждена пользователем.
- 15.11.2026 — в папке данных пользователя лог 1.2 в порядке; старый `aml_crashlog.txt` (CPhysical::Add) записан до
  установки Touch x4 и к нему не относится.
