/* ==========================================================================
   Запуск: все страницы строятся из встроенного D; внешних загрузок данных нет.
   ========================================================================== */
$('#foot').innerHTML = `<span>${esc(D.title)}</span><span>Период данных: ${esc(D.period)}</span><span>Сборка: ${esc(D.generated)}</span>
  <span>Границы: geoBoundaries / OpenStreetMap</span><span><a href="#how" data-goto-about>О проекте и технические проверки</a></span>`;
mapInit();
rows();
corrInit();
typesInit(); tfInit();
qualityInit();
howInit();
renderCmp();
activate((location.hash || '#out').slice(1), {noHash: true, scroll: false});
