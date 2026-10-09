# Экономические типы муниципалитетов Башкортостана — v4

Автономная интерактивная панель: **63 муниципалитета, 7 типов, 13 индексов,
32 признака, 9 слоёв связей и семь основных разделов**.

Авторы: **Гилязетдинова Елена Рубиновна, Давлетова Лиана Фаритовна**.

## Открыть проект

1. На странице этой ветки нажмите **Code → Download ZIP**.
2. Распакуйте архив.
3. Откройте **[index.html](index.html)** в Chrome, Edge или Firefox.

Python, Node.js и сервер для просмотра не нужны. Библиотеки, шрифты и данные
встроены в HTML. Для карты предусмотрены WebGL и резервный режим 2D.
Подложка OpenStreetMap загружается только при её явном включении.

На GitHub HTML показывается как исходный код: для работы панели откройте
скачанный файл в браузере.

## Разделы

- Выводы и рекомендации.
- Карта и сеть.
- Сравнение районов.
- Корреляции.
- Типы муниципальных образований.
- Качество модели.
- Как это работает.

## Исходники, данные и документы

| Материал | Путь |
|---|---|
| Готовая панель | [index.html](index.html) |
| Исходники интерфейса и сборщик | [reproduction/source/](reproduction/source/) |
| Исходники расчёта и конфигурация | [reproduction/calculation_source/](reproduction/calculation_source/) |
| Основной исходный отчёт PDF | [report.pdf](reproduction/calculation_source/docs/report.pdf) |
| Приложение PDF | [appendix.pdf](reproduction/calculation_source/docs/appendix.pdf) |
| Описание интерфейса v4 | [REPORT_V4.md](reproduction/source/docs/REPORT_V4.md) |
| Исходные материалы | [reproduction/materials/](reproduction/materials/) |
| Полная исследовательская база без Git LFS | [data/research-db/](data/research-db/) |
| Источники и контрольные суммы | [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json) |
| Схема исследовательской базы | [SCHEMA.sql](SCHEMA.sql) |
| Происхождение опубликованной панели | [V4_PROVENANCE.json](V4_PROVENANCE.json) |

## Сборка интерфейса

Из корня проекта, Python 3.11 или новее:

```text
python reproduction/source/build.py --out index.html --check
```

Команда собирает интерфейс из сохранённых данных; экономическая модель при
этом не пересчитывается. Для расчётного кода предусмотрена отдельная
[инструкция](reproduction/calculation_source/README.md).

Полная исследовательская база включена обычным gzip-архивом размером около
83 МБ. Для восстановления с проверкой SHA-256 выполните
`python data/research-db/restore.py`. Для открытия панели это не требуется.

## Версия и проверки

Это **исходная версия v4**, сохранённая из коммита
`b728705dd0b1ce7f104d3e82021fd3826b7ea655`. `index.html` побайтно совпадает
с прежним `reproduction/source/econtypes.html`. Хеши приведены в
`V4_PROVENANCE.json`. Дополнительной вкладки v5 здесь нет.

Опубликованные результаты не пересчитывались при подготовке этой ветки.
Методологические ограничения v4 сохранены и описаны в
[AUDIT.md](AUDIT.md) и [METHODS_SELECTION.md](METHODS_SELECTION.md).
Проверка открытия и интерфейса не означает устранения этих ограничений.

Существовавшие ранее отчёты о тестах имеют собственные даты. Результат
проверки этой публикации приведён в
[docs/V4_PUBLICATION_CHECKS.json](docs/V4_PUBLICATION_CHECKS.json).

Лицензии библиотек и шрифтов сохранены в `reproduction/source/src/vendor/licenses/`.
Лицензия расчётного кода и сведения об условиях использования данных — в
[LICENSE](reproduction/calculation_source/LICENSE).
