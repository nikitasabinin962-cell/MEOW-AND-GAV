# Как запустить

## Посмотреть готовый результат

1. Возьмите `econtypes_v5.html` из репозитория дашборда (`nikitasabinin962-cell/-`, ветка `claude/compassionate-carson-i2yna8`).
2. Откройте файл в Chrome, Edge, Firefox или Safari. Сервер, интернет и ключи не нужны: данные, шрифты и библиотеки встроены. Открывается вкладка «v5: пересчет», вкладки 1–7 показывают архив v4.
3. Если в браузере нет WebGL2, карта v4 переключается на 2D. Принудительно: добавить к адресу `?render=2d`.

## Скачать всю базу

- Кнопка «Скачать всю базу» во вкладке v5 или ссылка `url` в `data/DB_MANIFEST.json`. Вход в GitHub не нужен.
- Без сети: заранее выполните в папке дашборда `python3 tools/fetch_db.py`. Файл ляжет в `data/econtypes_v5.sqlite.gz` рядом со страницей, сумма будет проверена.
- Проверка и распаковка: конец `docs/DATA_DICTIONARY.md`.

## Пересчитать

Нужно: Python 3.11+ (проверено на 3.13), Git LFS для `../econtypes_research_20261009.sqlite`, для PDF LibreOffice, для дашборда Node.js 18+ и репозиторий дашборда рядом (`../../-`).

```bash
git lfs pull --include econtypes_research_20261009.sqlite    # из корня MEOW-AND-GAV
cd econtypes_v5
bash scripts/run_all.sh
```

На проверенной машине (4 vCPU, 15 GiB) полный расчет занял 1 018 с, пик памяти 752 МиБ; вместе с базой, проверками и отчетом около 25 минут. Результаты: `outputs/latest/` (с `RUN_MANIFEST.json`), база `data/econtypes_v5.sqlite`, снимок для скачивания `data/econtypes_v5.sqlite.gz`, отчет `docs/REPORT_v5.md/.docx/.pdf`, дашборд `../../-/econtypes_v5.html`.

Windows: те же шаги в PowerShell через Git Bash (`bash scripts/run_all.sh`), Python из python.org. Инструкция подготовлена, запуск под Windows не проверялся.

## Если что-то не так

- Вместо базы файл на 134 байта: это указатель Git LFS. Выполните `git lfs pull`.
- Нет репозитория дашборда рядом: расчет пройдет, шаг сборки дашборда будет пропущен.
- Нет LibreOffice: Markdown и Word соберутся, PDF нет.
- Скрипт падает: сообщение и код возврата пишутся в `outputs/*_log*`; `run_all.sh` останавливается на первой ошибке.
