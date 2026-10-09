"""Потоковый анализ реестра ФНС МСП 10.09.2026 + ЕИС/АТМО 2023–2026.
Исходники Google Drive читаются только на чтение. Результаты — только в новой папке.
Запускать в Google Colab с подключённым Google Drive.
"""
from __future__ import annotations
import csv
import io
import json
import os
import re
import shutil
import sqlite3
import time
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path('/content/drive/MyDrive/конкурсы/сбер конкурс')
ZIP_NAME = 'data-10092026-structure-12052026.zip'
XML_FOLDER = 'data-10092026-structure-12052026_распаковано'
CONTRACT_FOLDER = 'ЕИС и АТМО — анализ 2023–2026 — 2026-10-08_11-38'
CATEGORY = {'1': 'Микропредприятие', '2': 'Малое предприятие', '3': 'Среднее предприятие'}
REPORT_FIELDS = ['canonical_contract_id', 'processing_group', 'contract_number', 'sign_date', 'law',
                 'amount', 'amount_cents', 'currency', 'financial_status', 'customer', 'customer_inn',
                 'supplier', 'supplier_inn', 'subject', 'contract_url', 'tender_url', 'source_file',
                 'msp_status_20260910', 'msp_category', 'msp_type_code', 'msp_region_code',
                 'msp_legal_form', 'msp_okved_main', 'msp_headcount', 'msp_inn']


def norm_inn(v):
    s = str(v or '').strip().replace(' ', '')
    return s if s.isascii() and s.isdigit() and len(s) in (10, 12) else ''


def contract_parts(root):
    p = root / CONTRACT_FOLDER
    files = sorted(p.glob('contracts_unique_eis_atmo_[0-9][0-9][0-9].csv'))
    if not files:
        raise FileNotFoundError(f'Не найдены 8 частей канонического реестра: {p}')
    print(f'Контрактных файлов: {len(files)}, {files[0].name} ... {files[-1].name}', flush=True)
    return files


def contract_supplier_index(parts):
    inns = set()
    total = missing = invalid = 0
    for p in parts:
        with p.open('r', encoding='utf-8-sig', newline='') as fp:
            rd = csv.DictReader(fp, delimiter=';')
            required = {'supplier_inn', 'canonical_contract_id', 'sign_date'}
            if not required.issubset(set(rd.fieldnames or [])):
                raise ValueError(f'Нет ожидаемых колонок в {p.name}: {required - set(rd.fieldnames or [])}')
            n = 0
            for r in rd:
                total += 1
                n += 1
                raw = (r.get('supplier_inn') or '').strip()
                inn = norm_inn(raw)
                if inn:
                    inns.add(inn)
                elif raw:
                    invalid += 1
                else:
                    missing += 1
        print(f'Индекс контрактов: {p.name}: {n:,} строк', flush=True)
    print(f'Строк контрактов {total:,}; разных корректных ИНН поставщика {len(inns):,}; '
          f'без ИНН {missing:,}; некорректных ИНН {invalid:,}', flush=True)
    return inns, {'contract_rows': total, 'supplier_inns_unique': len(inns),
                  'supplier_inn_empty_rows': missing, 'supplier_inn_invalid_rows': invalid}


def xml_items(root):
    original = root / ZIP_NAME
    extracted = root / XML_FOLDER
    if original.is_file():
        # Один ZIP читается существенно быстрее большого числа файлов с Google Drive mount.
        path = original
        try:
            need = original.stat().st_size
            free = shutil.disk_usage('/content').free
            if free > need * 1.35 + 400_000_000:
                temp = Path('/content/msp_fns_20260910_source.zip')
                if not temp.exists() or temp.stat().st_size != need:
                    print('Копирую исходный ZIP с Google Drive во временное облачное хранилище Colab...', flush=True)
                    shutil.copy2(original, temp)
                path = temp
        except (OSError, ValueError) as exc:
            print('Копирование пропущено:', exc, flush=True)
        print('Режим: чтение XML внутри ZIP без распаковки:', path, flush=True)
        with zipfile.ZipFile(path) as z:
            names = [i for i in z.infolist() if not i.is_dir() and i.filename.lower().endswith('.xml')]
            if not names:
                raise RuntimeError('ZIP не содержит XML')
            print('XML внутри ZIP:', len(names), flush=True)
            for info in names:
                with z.open(info) as fp:
                    yield info.filename, fp
    elif extracted.is_dir():
        files = sorted(extracted.rglob('*.xml'))
        print('Режим: чтение распакованной папки; XML:', len(files), flush=True)
        if not files:
            raise RuntimeError('В папке нет XML')
        for fp in files:
            with fp.open('rb') as stream:
                yield fp.name, stream
    else:
        raise FileNotFoundError(f'Нет архива {original} и папки {extracted}')


def create_database(path):
    db = sqlite3.connect(str(path))
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA synchronous=NORMAL')
    db.execute('''CREATE TABLE IF NOT EXISTS registry(
      inn TEXT PRIMARY KEY, source_file TEXT, region_code TEXT, legal_form TEXT,
      category TEXT, type_code TEXT, name TEXT, okved_main TEXT,
      headcount TEXT, district TEXT, city TEXT, locality TEXT,
      inclusion_date TEXT, snapshot_date TEXT)''')
    db.commit()
    return db


def first_attr(doc, path, attr):
    node = doc.find(path)
    return (node.attrib.get(attr) or '').strip() if node is not None else ''


def parse_one_xml(fp, filename, db, supplier_inns, counters):
    declared = None
    found = 0
    root_seen = False
    for ev, elem in ET.iterparse(fp, events=('start', 'end')):
        if not root_seen and ev == 'start':
            if elem.tag != 'Файл':
                raise ValueError(f'Неожиданный корневой тег: {elem.tag}')
            root_seen = True
            declared = elem.attrib.get('КолДок')
        if ev != 'end' or elem.tag != 'Документ':
            continue
        found += 1
        counters['total_documents'] += 1
        date = (elem.attrib.get('ДатаСост') or '').strip()
        counters['dates'][date] += 1
        region = first_attr(elem, './СведМН', 'КодРегион')
        region = region.zfill(2) if region.isdigit() else region
        counters['regions'][region] += 1
        if not region:
            counters['missing_region'] += 1
        legal = elem.find('ОргВклМСП')
        person = elem.find('ИПВклМСП')
        if legal is not None:
            inn = norm_inn(legal.attrib.get('ИННЮЛ'))
            entity_name = legal.attrib.get('НаимОргСокр') or legal.attrib.get('НаимОрг') or ''
            legal_form = 'ЮЛ'
        elif person is not None:
            inn = norm_inn(person.attrib.get('ИННФЛ'))
            entity_name = 'ИП'  # ФИО физлиц не дублируем в результатах исследования
            legal_form = 'ИП'
        else:
            inn = ''
            entity_name = ''
            legal_form = 'НЕИЗВЕСТНО'
        if not inn:
            counters['missing_inn'] += 1
        cat = elem.attrib.get('КатСубМСП', '')
        typ = elem.attrib.get('ВидСубМСП', '')
        main = first_attr(elem, './СвОКВЭД/СвОКВЭДОсн', 'КодОКВЭД')
        head = elem.attrib.get('ССЧР', '')
        if region == '02':
            counters['bash_entities'] += 1
            counters['bash_categories'][cat] += 1
            counters['bash_legal'][legal_form] += 1
            counters['bash_okved2'][main[:2] if main else 'не указан'] += 1
            counters['bash_headcount_nonempty'] += int(bool(head))
        if inn and (region == '02' or inn in supplier_inns):
            cur = db.execute('''INSERT OR IGNORE INTO registry
            (inn,source_file,region_code,legal_form,category,type_code,name,okved_main,
             headcount,district,city,locality,inclusion_date,snapshot_date)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                inn, filename, region, legal_form, cat, typ, entity_name, main, head,
                first_attr(elem, './СведМН/Район', 'Наим'),
                first_attr(elem, './СведМН/Город', 'Наим'),
                first_attr(elem, './СведМН/НаселПункт', 'Наим'),
                elem.attrib.get('ДатаВклМСП', ''), date))
            if cur.rowcount == 0:
                counters['duplicate_inn'] += 1
        elem.clear()
    if declared and declared.isdigit() and int(declared) != found:
        counters['declared_mismatch'] += 1
        counters['errors'].append(f'{filename}: КолДок={declared}, реально={found}')
    return found


def write_table(path, fields, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(fields)
        for row in rows:
            w.writerow(row)


def write_msp_tables(db, output, c):
    write_table(output/'msp_bashkortostan_20260910.csv',
        ['inn','region_code','legal_form','category_code','category','name','okved_main',
         'headcount','district_raw','city_raw','locality_raw','inclusion_date','snapshot_date','source_file'],
        ((r[0],r[2],r[3],r[4],CATEGORY.get(r[4],r[4]),r[6],r[7],r[8],r[9],r[10],r[11],r[12],r[13],r[1])
         for r in db.execute('SELECT * FROM registry WHERE region_code="02" ORDER BY inn')))
    write_table(output/'msp_bash_categories.csv', ['category_code','category','entities'],
                ((k,CATEGORY.get(k,'Не определено'),v) for k,v in sorted(c['bash_categories'].items())))
    write_table(output/'msp_bash_okved2.csv', ['okved2','entities'],
                sorted(c['bash_okved2'].items(), key=lambda p:(-p[1],p[0])))
    write_table(output/'msp_regions_control.csv', ['region_code','entities'],
                sorted(c['regions'].items()))
    # География доступна как текст, но не как проверенный ОКТМО.
    write_table(output/'msp_bash_address_strings_UNVERIFIED.csv',
                ['district_raw','city_raw','locality_raw','entities','warning'],
                ((a,b,d,n,'НЕ ЯВЛЯЕТСЯ сопоставлением с ОКТМО') for (a,b,d),n in db.execute(
                    '''SELECT district,city,locality,COUNT(*) FROM registry WHERE region_code="02"
                       GROUP BY district,city,locality ORDER BY COUNT(*) DESC''')))
    write_table(output/'msp_index_relevant_entities.csv',
                ['inn','category','region_code','okved_main','legal_form','snapshot_date'],
                ((r[0],CATEGORY.get(r[4],r[4]),r[2],r[7],r[3],r[13])
                 for r in db.execute('SELECT * FROM registry ORDER BY inn')))


def contract_join(parts, db, output, source_summary, c):
    summaries = defaultdict(lambda: Counter())
    sums = defaultdict(int)
    overview = Counter()
    badinn = Counter()
    outno = 0
    written = 0
    writer = None
    fhandle = None
    try:
        for part in parts:
            with part.open('r',encoding='utf-8-sig',newline='') as fp:
                rd = csv.DictReader(fp,delimiter=';')
                for r in rd:
                    inn = norm_inn(r.get('supplier_inn'))
                    found = db.execute('SELECT inn,region_code,category,type_code,legal_form,okved_main,headcount FROM registry WHERE inn=?',(inn,)).fetchone() if inn else None
                    status = ('Найден в реестре МСП на 2026-09-10' if found else
                              'Нет корректного ИНН поставщика' if not inn else
                              'Не найден в реестре МСП на 2026-09-10')
                    fields = {k:(r.get(k) or '') for k in REPORT_FIELDS if not k.startswith('msp_')}
                    fields.update({'msp_status_20260910':status,
                                   'msp_category':CATEGORY.get(found[2],found[2]) if found else '',
                                   'msp_type_code':found[3] if found else '',
                                   'msp_region_code':found[1] if found else '',
                                   'msp_legal_form':found[4] if found else '',
                                   'msp_okved_main':found[5] if found else '',
                                   'msp_headcount':found[6] if found else '',
                                   'msp_inn':found[0] if found else ''})
                    if writer is None or written >= 50000:
                        if fhandle: fhandle.close()
                        outno += 1; written = 0
                        fname = output / f'contracts_msp_enriched_{outno:03}.csv'
                        fhandle = fname.open('w',encoding='utf-8-sig',newline='')
                        writer = csv.DictWriter(fhandle,fieldnames=REPORT_FIELDS,delimiter=';',extrasaction='ignore')
                        writer.writeheader()
                    writer.writerow(fields)
                    written += 1
                    overview[status] += 1
                    yr = (r.get('sign_date') or '')[:4]
                    if len(yr)!=4 or not yr.isdigit(): yr='НЕ ОПРЕДЕЛЁН'
                    grp = r.get('processing_group') or ''
                    law = r.get('law') or ''
                    curr = r.get('currency') or ''
                    key=(yr,grp,law,curr,status)
                    summaries[key]['contracts'] += 1
                    cents=(r.get('amount_cents') or '').strip()
                    if (r.get('financial_status') or '')=='known' and re.fullmatch(r'-?\d+',cents):
                        sums[key]+=int(cents)
                        summaries[key]['contracts_with_known_amount']+=1
                    else:
                        summaries[key]['contracts_without_known_amount']+=1
        if fhandle: fhandle.close()
        write_table(output/'contracts_msp_summary_year_law_currency.csv',
            ['sign_year','processing_group','law','currency','msp_status_20260910','contracts',
             'known_amount_contracts','amount_kopeks','amount_currency_units'],
            ((yr,grp,law,curr,st,stats['contracts'],stats['contracts_with_known_amount'],
              sums[(yr,grp,law,curr,st)],f'{sums[(yr,grp,law,curr,st)]/100:.2f}')
             for (yr,grp,law,curr,st),stats in sorted(summaries.items())))
        source_summary['enriched_contracts']=sum(overview.values())
        source_summary['contract_msp_status_counts']=dict(overview)
        source_summary['contract_enriched_parts']=outno
        if source_summary['enriched_contracts']!=source_summary['contract_rows']:
            c['errors'].append('Количество строк контракта после join не совпало с числом исходных')
    finally:
        if fhandle and not fhandle.closed: fhandle.close()


def run(root=ROOT):
    root=Path(root)
    if not root.is_dir(): raise FileNotFoundError(f'Папка проекта не найдена: {root}')
    parts=contract_parts(root)
    supplier_inns, summary=contract_supplier_index(parts)
    label=datetime.now().strftime('%Y%m%d_%H%M%S')
    output=root / f'АНАЛИЗ_МСП_ЕИС_20260910_{label}'
    output.mkdir(exist_ok=False)
    print('Папка результатов:', output, flush=True)
    dbpath=(Path('/content') if Path('/content').is_dir() else Path('/tmp'))/f'msp_analysis_index_{label}.sqlite'
    db=create_database(dbpath)
    c={ 'regions':Counter(),'dates':Counter(),'bash_categories':Counter(),'bash_legal':Counter(),
        'bash_okved2':Counter(),'total_documents':0,'bash_entities':0,
        'bash_headcount_nonempty':0,'missing_inn':0,'missing_region':0,
        'duplicate_inn':0,'declared_mismatch':0,'errors':[]}
    attempted=0
    t0=time.time()
    try:
        for filename, fp in xml_items(root):
            attempted+=1
            try:
                parse_one_xml(fp,filename,db,supplier_inns,c)
            except Exception as exc:
                c['errors'].append(f'{filename}: {type(exc).__name__}: {exc}')
                print('ОШИБКА XML:',filename,exc,flush=True)
            if attempted%100==0:
                db.commit()
                print(f'XML {attempted:,}, документов {c["total_documents"]:,}, '
                      f'Башкортостан {c["bash_entities"]:,}, ошибок {len(c["errors"])}',flush=True)
        db.commit()
        print(f'Обход завершён: {attempted:,} XML, {c["total_documents"]:,} записей. '
              f'В Бaшкортостане {c["bash_entities"]:,}; ошибок {len(c["errors"])}.',flush=True)
        write_msp_tables(db,output,c)
        contract_join(parts,db,output,summary,c)
        summary.update({'status':'COMPLETE' if not c['errors'] else 'INCOMPLETE',
                        'files_xml_attempted':attempted,
                        'xml_documents_processed':c['total_documents'],
                        'msp_snapshot_dates':dict(c['dates']),
                        'bashkortostan_entities':c['bash_entities'],
                        'bash_category_codes':dict(c['bash_categories']),
                        'bash_legal_forms':dict(c['bash_legal']),
                        'bash_headcount_present':c['bash_headcount_nonempty'],
                        'missing_inn_in_fns':c['missing_inn'],
                        'missing_region_in_fns':c['missing_region'],
                        'duplicate_inn_in_index':c['duplicate_inn'],
                        'xml_declared_count_mismatch':c['declared_mismatch'],
                        'elapsed_seconds':round(time.time()-t0,1),
                        'errors':c['errors'][:200],
                        'notes':['ФНС фиксирует статус МСП на 10.09.2026, НЕ исторический статус в дату контракта.',
                                 'ФНС не содержит контракты — связь с ЕИС/АТМО исключительно по ИНН поставщика.',
                                 'Нет в ФНС на 10.09.2026 НЕ значит, что поставщик не был МСП в прошлые годы.',
                                 'Адресные строки ФНС НЕ являются достоверным ОКТМО. Муниципальные итоги запрещены без верифицированного справочника.',
                                 'Суммы агрегированы отдельно по валюте и только при финансовом статусе known; источник contracts_unique_eis_atmo уникален.',
                                 'Результаты охватывают только имеющиеся в проекте контракты, а не все контракты Башкортостана.',
                                 '2026 — неполный год.']})
        (output/'QA_results.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        (output/'README.txt').write_text(
            'Результат потокового разбора ФНС МСП 10.09.2026 и соединения с каноническими контрактами.\n'
            'QA_results.json — контроль полноты, неполные результаты = INCOMPLETE.\n'
            'msp_bashkortostan_20260910.csv — юридические лица и ИП региона 02; дата снимка 10.09.2026.\n'
            'msp_bash_okved2.csv — направления по основному ОКВЭД (двузначная группа).\n'
            'msp_bash_categories.csv — категории МСП.\n'
            'msp_bash_address_strings_UNVERIFIED.csv — строки адреса, НЕ уровни ОКТМО!\n'
            'msp_regions_control.csv — число записей по коду региона для контроля.\n'
            'contracts_msp_enriched_NNN.csv — уникальные контракты с МСП-атрибутами на 10.09.2026.\n'
            'contracts_msp_summary_year_law_currency.csv — сводка по году/закону/группе/валюте и результату проверки.\n'
            'msp_index_relevant_entities.csv — минимальный реестр ИНН из XML, связанных с контрактами или Башкортостаном.\n'
            'ФНС не содержит номер контракта, ОКТМО муниципалитета и подтверждение МСП на историческую дату закупки.\n'
            'Данные исходных файлов не изменены.\n',encoding='utf-8')
        print('СТАТУС:',summary['status'],'Папка:',output,'\n',
              'Записей в Башкортостане:',c['bash_entities'],'; связанных контрактов:',
              summary.get('contract_msp_status_counts',{}).get('Найден в реестре МСП на 2026-09-10'),flush=True)
        return summary,output
    finally:
        db.close()

if __name__=='__main__':
    run(ROOT)
