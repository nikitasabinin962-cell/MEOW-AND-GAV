#!/usr/bin/env bash
# Собирает сайт проекта для GitHub Pages в папку docs/ (Settings → Pages → Branch: main, папка /docs).
#   docs/index.html     — лендинг
#   docs/dashboard.html — интерактивный дашборд
#   docs/report.pdf, docs/appendix.pdf — отчёт и приложение
set -e
cd "$(dirname "$0")/.."
cp outputs/landing/index.html docs/index.html
cp outputs/dashboard.html docs/dashboard.html
touch docs/.nojekyll
echo "сайт обновлён: docs/index.html, docs/dashboard.html"
