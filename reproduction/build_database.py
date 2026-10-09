"""Build a new, versioned SQLite research database; never modifies supplied data.
Usage: python build_database.py --input-root PATH --output NEW_PATH
Inputs must retain their original names under materials/, source/, calculation_source/.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from collections import Counter
import argparse, csv, hashlib, json, re, sqlite3
import pandas as pd
from pypdf import PdfReader

def normalized(s):
    return re.sub(r'\s+',' ',str(s or '').lower().replace('ё','е')).strip()

def inn_valid(s):
    if not s.isdigit() or len(s) not in (10,12): return False
    ns=list(map(int,s))
    ck=lambda co: sum(a*b for a,b in zip(ns,co))%11%10
    if len(ns)==10: return ck([2,4,10,3,5,9,4,6,8])==ns[9]
    return ck([7,2,4,10,3,5,9,4,6,8])==ns[10] and ck([3,7,2,4,10,3,5,9,4,6,8])==ns[11]

def rub_to_kopecks(v):
    if v is None or str(v).strip()=='': return None
    return int((Decimal(str(v).replace(' ','').replace(',','.'))*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))

def date_rb(v):
    if not v:return None
    try:return datetime.fromisoformat(v.replace('Z','+00:00')).astimezone(timezone(timedelta(hours=5))).date().isoformat()
    except ValueError:return None

def main(root, out):
    if out.exists():raise FileExistsError('Choose a NEW output; existing databases are not replaced')
    out.parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(out);con.execute('PRAGMA foreign_keys=ON');con.execute('PRAGMA journal_mode=WAL')
    con.executescript('''
    CREATE TABLE dataset_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE sources(source_id TEXT PRIMARY KEY,relative_path TEXT,original_name TEXT,sha256 TEXT,size_bytes INTEGER,source_url TEXT,observation_period TEXT,role TEXT,limitations TEXT);
    CREATE TABLE municipalities(mo_id INTEGER PRIMARY KEY,name TEXT UNIQUE,kind TEXT,official_oktmo TEXT,territory_id INTEGER,sber_mapping_status TEXT);
    CREATE TABLE population(mo_id INTEGER REFERENCES municipalities,observation_date TEXT,value INTEGER CHECK(value>0),unit TEXT DEFAULT 'persons',source_id TEXT REFERENCES sources,PRIMARY KEY(mo_id,observation_date));
    CREATE TABLE baseline_feature_aggregates(mo_id INTEGER REFERENCES municipalities,feature TEXT,value REAL,period_start TEXT,period_end TEXT,status TEXT,source_id TEXT REFERENCES sources,PRIMARY KEY(mo_id,feature));
    CREATE TABLE baseline_monthly_spending(mo_id INTEGER REFERENCES municipalities,period TEXT,value REAL,unit TEXT,status TEXT,source_id TEXT REFERENCES sources,PRIMARY KEY(mo_id,period));
    CREATE TABLE baseline_cluster_labels(mo_id INTEGER REFERENCES municipalities,period TEXT,label INTEGER,version TEXT,source_id TEXT REFERENCES sources,PRIMARY KEY(mo_id,period));
    CREATE TABLE baseline_graph_edges(layer TEXT,source_mo INTEGER REFERENCES municipalities,target_mo INTEGER REFERENCES municipalities,weight REAL,lag INTEGER,directed INTEGER,unit TEXT,source_id TEXT REFERENCES sources,PRIMARY KEY(layer,source_mo,target_mo));
    CREATE TABLE msp_snapshot_rows(row_id INTEGER PRIMARY KEY,inn TEXT,region_code TEXT,legal_form TEXT,category_code TEXT,category TEXT,name TEXT,okved_main TEXT,headcount_raw TEXT,district_raw TEXT,city_raw TEXT,locality_raw TEXT,inclusion_date_raw TEXT,snapshot_date TEXT,source_xml TEXT,inn_checksum_valid INTEGER,source_id TEXT REFERENCES sources);
    CREATE INDEX msp_inn_idx ON msp_snapshot_rows(inn,snapshot_date);
    CREATE TABLE msp_municipality_candidates(row_id INTEGER PRIMARY KEY REFERENCES msp_snapshot_rows,mo_id_candidate INTEGER REFERENCES municipalities,method TEXT,verified_oktmo TEXT,status TEXT);
    CREATE TABLE msp_supplier_index_snapshot(row_id INTEGER PRIMARY KEY,inn TEXT,category_raw TEXT,region_code TEXT,okved_main TEXT,legal_form TEXT,snapshot_date TEXT,source_id TEXT REFERENCES sources);
    CREATE INDEX msp_supplier_index_inn_idx ON msp_supplier_index_snapshot(inn,snapshot_date);
    CREATE TABLE atmo_contract_observations(row_id INTEGER PRIMARY KEY,law TEXT,api_record_type TEXT,api_record_id TEXT,api_contract_id TEXT,registration_number TEXT,status_code TEXT,published_at_utc TEXT,contract_at_utc TEXT,contract_date_rb TEXT,executed_at_utc TEXT,price_kopecks INTEGER,starting_price_kopecks INTEGER,customer_api_id TEXT,customer_name TEXT,customer_municipality_raw TEXT,supplier_api_id TEXT,supplier_name TEXT,customer_inn TEXT,supplier_inn TEXT,okpd2 TEXT,subject TEXT,proposals_count INTEGER,delivery_addresses_json TEXT,source_id TEXT REFERENCES sources,raw_json TEXT);
    CREATE INDEX atmo_identity_idx ON atmo_contract_observations(law,api_record_type,api_record_id);
    CREATE TABLE procurement_notice_exports(row_id INTEGER PRIMARY KEY,source_id TEXT REFERENCES sources,raw_json TEXT);
    CREATE TABLE data_quality_checks(check_name TEXT PRIMARY KEY,status TEXT,details_json TEXT);
    CREATE VIEW population_growth AS SELECT p.mo_id,m.name,p.observation_date,p.value,prev.value AS previous_value,p.value-prev.value AS delta_persons,1.0*(p.value-prev.value)/prev.value AS growth FROM population p JOIN municipalities m USING(mo_id) LEFT JOIN population prev ON prev.mo_id=p.mo_id AND prev.observation_date=date(p.observation_date,'-1 year');
    CREATE VIEW msp_unique_entities AS SELECT inn,snapshot_date,COUNT(*) AS source_rows,MIN(category_code) AS category_code,COUNT(DISTINCT okved_main) AS okved_versions,MAX(inn_checksum_valid) AS checksum_valid FROM msp_snapshot_rows GROUP BY inn,snapshot_date;
    CREATE VIEW msp_supplier_index_unique AS SELECT inn,snapshot_date,MIN(region_code) AS region_code,MIN(category_raw) AS category_raw,COUNT(*) AS source_rows FROM msp_supplier_index_snapshot GROUP BY inn,snapshot_date;
    CREATE VIEW msp_candidate_counts AS SELECT m.name,c.status,COUNT(DISTINCT r.inn) AS distinct_inns FROM msp_snapshot_rows r JOIN msp_municipality_candidates c USING(row_id) LEFT JOIN municipalities m ON m.mo_id=c.mo_id_candidate GROUP BY c.mo_id_candidate,c.status;
    CREATE VIEW atmo_monthly_observed AS SELECT law,substr(contract_date_rb,1,7) AS month,COUNT(*) AS observation_rows,SUM(price_kopecks) AS price_kopecks FROM atmo_contract_observations GROUP BY law,substr(contract_date_rb,1,7);
    CREATE VIEW atmo_unique_contract_candidates AS SELECT o.* FROM atmo_contract_observations o WHERE o.row_id IN (SELECT MIN(row_id) FROM atmo_contract_observations GROUP BY law,api_record_type,api_record_id,api_contract_id HAVING COUNT(DISTINCT raw_json)=1);
    CREATE VIEW atmo_identity_conflicts AS SELECT law,api_record_type,api_record_id,api_contract_id,COUNT(*) AS rows,COUNT(DISTINCT raw_json) AS payload_versions FROM atmo_contract_observations GROUP BY law,api_record_type,api_record_id,api_contract_id HAVING COUNT(DISTINCT raw_json)>1;
    CREATE VIEW atmo_monthly_unique_candidates AS SELECT law,substr(contract_date_rb,1,7) AS month,COUNT(*) AS unique_api_records,SUM(price_kopecks) AS price_kopecks FROM atmo_unique_contract_candidates GROUP BY law,substr(contract_date_rb,1,7);
    ''')
    source_records=[]
    def source(path,sid,url,period,role,lim=''):
        rec=(sid,str(path.relative_to(root)),path.name,hashlib.sha256(path.read_bytes()).hexdigest(),path.stat().st_size,url,period,role,lim)
        con.execute('INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?)',rec);source_records.append(dict(zip(['source_id','relative_path','original_name','sha256','size_bytes','source_url','observation_period','role','limitations'],rec)));return sid
    def qc(name,passed,details):
        con.execute('INSERT INTO data_quality_checks VALUES (?,?,?)',(name,'PASS' if passed else 'FAIL',json.dumps(details,ensure_ascii=False)))
    dpath=root/'source/src/data/D.json';D=json.loads(dpath.read_text()); nodes=D['nodes'];mos=[n['mo'] for n in nodes];mid={m:i for i,m in enumerate(mos)}
    srcd=source(dpath,'dashboard_baseline','user attachment econtypes-v4-src.zip','2023-01/2024-12','archived_results','Derived dashboard data, not original SberIndex microdata; one municipality imputed. Clusters need recomputation after AVU/leakage fixes.')
    mapping=pd.read_csv(root/'calculation_source/outputs/tables/sberindex_id_to_mo.csv').set_index('mo').territory_id.to_dict()
    for n in nodes:con.execute('INSERT INTO municipalities VALUES (?,?,?,?,?,?)',(mid[n['mo']],n['mo'],n['kind'],None,int(mapping[n['mo']]) if n['mo'] in mapping else None,'algorithmic_mapping_from_original_code' if n['mo'] in mapping else 'unmapped'))
    cols=list(D['feats'])
    for n in nodes:
        moid=mid[n['mo']]
        con.executemany('INSERT INTO baseline_feature_aggregates VALUES (?,?,?,?,?,?,?)',[(moid,f,v,'2023-01-01','2024-12-31','archived_derived_value',srcd) for f,v in zip(cols,n['f'])])
        con.executemany('INSERT INTO baseline_monthly_spending VALUES (?,?,?,?,?,?)',[(moid,p,v,'rub_per_person_per_month_as_described_by_project','archived_derived_value',srcd) for p,v in zip(D['months'],n['sp'])])
        con.executemany('INSERT INTO baseline_cluster_labels VALUES (?,?,?,?,?)',[(moid,p,int(l),'baseline_v4_unrepaired',srcd) for p,l in zip(D['quarters'],n['q'])]+[(moid,'2023-2024_static',int(n['c']),'baseline_v4_unrepaired',srcd)])
    for layer,es in D['layers'].items():
        for i,j,w,lag in es:con.execute('INSERT INTO baseline_graph_edges VALUES (?,?,?,?,?,?,?,?)',(layer,i,j,w,lag,int(layer in ['flow_rub','lead_lag']),'rub' if layer=='flow_rub' else 'similarity',srcd))
    # PDFs contain district totals AND their towns/subdistricts. Only the 63 exact root municipalities are admitted.
    mats=root/'materials';popcontrols=[]
    plan=json.loads((mats/'download_plan.json').read_text(encoding='utf-8-sig'));urlmap={r['filename']:r['url'] for r in plan}
    for year in [2022,2023,2024,2025]:
        ps=[p for p in mats.glob('*.pdf') if f'yanvarya-{year}' in p.name];assert len(ps)==1,(year,ps)
        p=ps[0];sid=source(p,f'rosstat_population_{year}',urlmap.get(p.name,'https://02.rosstat.gov.ru/folder/25491'),f'{year}-01-01','official_population','Download date 2026-10-09 is not observation year.')
        txt='\n'.join(x.extract_text() for x in PdfReader(p).pages).replace('ё','е')
        values={}
        for mo in mos:
            stem=mo[3:]
            pattern=(r'г\.\s*' if mo.startswith('ГО ') else r'(?<![А-Яа-я])')+re.escape(stem)+r'\s+(\d+)'
            hits=re.findall(pattern,txt)
            assert len(hits)==1,(year,mo,hits)
            values[mo]=int(hits[0]);con.execute('INSERT INTO population(mo_id,observation_date,value,source_id) VALUES (?,?,?,?)',(mid[mo],f'{year}-01-01',values[mo],sid))
        total=int(re.search(r'Всего по республике\s+(\d+)',txt)[1]);computed=sum(values.values())
        assert computed==total,(year,computed,total)
        popcontrols.append(dict(year=year,municipalities=len(values),sum_population=computed,pdf_region_control=total))
    qc('population_63_MO_all_years_sum_equals_region',True,popcontrols)
    # Original row grain is retained, even for repeated INNs; aggregates explicitly count distinct entities.
    p=mats/'msp_bashkortostan_20260910.csv';sid=source(p,'fns_msp_20260910','https://www.nalog.gov.ru/opendata/7707329152-rsmp/','2026-09-10','processed_official_snapshot','Supplied processed CSV, not independent XML rerun. Address strings are candidate geography, not verified OKTMO. Historical membership cannot be inferred from this snapshot.')
    district_lookup={normalized(m[3:]):mid[m] for m in mos if m.startswith('МР ')}
    city_lookup={normalized(m[3:]):mid[m] for m in mos if m.startswith('ГО ')}
    inns=Counter();categories=Counter();candidates=Counter();badinn=0;nr=0;missinghead=0
    with p.open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f,delimiter=';'):
            nr+=1;inn=r['inn'];valid=inn_valid(inn);badinn+=not valid;inns[inn]+=1;categories[r['category_code']]+=1;missinghead+=r['headcount']==''
            sd=datetime.strptime(r['snapshot_date'],'%d.%m.%Y').date().isoformat()
            vals=(nr,inn,r['region_code'],r['legal_form'],r['category_code'],r['category'],r['name'],r['okved_main'],r['headcount'],r['district_raw'],r['city_raw'],r['locality_raw'],r['inclusion_date'],sd,r['source_file'],int(valid),sid)
            con.execute('INSERT INTO msp_snapshot_rows VALUES ('+','.join('?' for _ in vals)+')',vals)
            ds=normalized(r['district_raw']);cs=normalized(r['city_raw']);dc=district_lookup.get(ds);cc=city_lookup.get(cs)
            if dc is not None and cc is not None and dc!=cc: cand=None;status='conflicting_address_strings'
            elif dc is not None: cand=dc;status='district_text_candidate'
            elif cc is not None: cand=cc;status='city_text_candidate'
            else:cand=None;status='unresolved_address'
            candidates[status]+=1
            con.execute('INSERT INTO msp_municipality_candidates VALUES (?,?,?,?,?)',(nr,cand,'exact_normalized_address_string_only',None,status))
    qc('msp_unique_INNs_reconcile_supplied_QA',len(inns)==150234 and badinn==0,dict(csv_rows=nr,unique_inns=len(inns),supplied_QA_entity_rows=150247,supplied_QA_unique_inns=150234,note='CSV exports 150234 unique rows; prior QA counts 150247 entity observations. Difference of 13 is retained as an upstream lineage discrepancy, not fabricated duplicate rows in this CSV.',category_counts=dict(categories),invalid_inn_checksum_rows=badinn,missing_headcount_rows=missinghead,address_statuses=dict(candidates)))
    con.commit();print('Imported MSP rows',nr,flush=True)
    p=mats/'msp_index_relevant_entities.csv';sid=source(p,'fns_msp_relevant_suppliers_20260910','https://drive.google.com/file/d/1tldH7Q_sDe-9U1qzSSPBiNpGY7JFllqh/view','2026-09-10','processed_national_MSP_index','Subset selected by upstream processing for Bashkortostan/relevant suppliers; not complete national population of enterprises. Needed for suppliers outside region 02.')
    supplier_index_rows=0;index_bad_inn=0
    with p.open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f,delimiter=';'):
            supplier_index_rows+=1;index_bad_inn+=not inn_valid(r['inn']);sd=datetime.strptime(r['snapshot_date'],'%d.%m.%Y').date().isoformat()
            con.execute('INSERT INTO msp_supplier_index_snapshot VALUES (?,?,?,?,?,?,?,?)',(supplier_index_rows,r['inn'],r['category'],r['region_code'],r['okved_main'],r['legal_form'],sd,sid))
    qc('national_supplier_index_valid_identifiers',index_bad_inn==0,dict(imported_rows=supplier_index_rows,invalid_inns=index_bad_inn))
    con.commit()
    # ATMO: prefer nested original API fields. Contract ID != purchase ID != EIS registry number.
    atmoaudit=[]
    for filename,law,fileid in [('atmo_223.json','223-ФЗ','1nCsFJRW-S8ZnLMoYloiHb7nTpIOOfsTI'),('ATMO_API_44_20261008131737_umgsvm_2024-12_p01508-01516_part00319.json','44-ФЗ','1eZJeT_p5xrTiYujH6Tc7woH4Eey3lFTz')]:
        p=mats/filename;data=json.loads(p.read_text(encoding='utf-8-sig'));rs=data['records']
        sid=source(p,'atmo_'+('223' if law=='223-ФЗ' else '44_sample'),f'https://drive.google.com/file/d/{fileid}/view','exported 2026-10-08','API_contract_observations','223: supplied single collected export; 44: ONLY 135-record sample. No E-signature verification. INN missing. Not full national/regional totals.')
        sumprice=0;normalizeddateempty=0;subjectwrong=0;statuses=Counter();ids=[];dates=[];missinginn=0;negativeprices=0
        for rec in rs:
            raw=rec.get('raw',rec.get('оригинал_API'));norm=rec.get('normalized',rec.get('нормализовано',{}));ct=raw.get('contract') or {}
            status=raw.get('status') or {};scode=status.get('code') or status.get('id');statuses[scode]+=1
            cdate=ct.get('contract_conclusion_date') or raw.get('contract_conclusion_date');localdate=date_rb(cdate)
            price=rub_to_kopecks(ct.get('price',raw.get('price')));sumprice+=price or 0;negativeprices+=price is not None and price<0
            customer=raw.get('customer') or {};subject=raw.get('purchase_object') or raw.get('purchase_name')
            normalizeddateempty+=not(norm.get('Дата_заключения_договора') or norm.get('дата_заключения'))
            oldsubject=norm.get('Предмет',norm.get('предмет'));subjectwrong+=bool(oldsubject!=subject)
            cin=raw.get('customer_inn') or customer.get('inn');sin=raw.get('supplier_inn') or ct.get('supplier_inn');missinginn+=not(cin and sin)
            vals=(None,law,raw.get('type') or 'fl223_purchase',str(raw.get('id')),str(ct['id']) if ct.get('id') is not None else None,raw.get('registration_number') or raw.get('reg_number'),scode,raw.get('purchase_publish_date') or raw.get('published_at'),cdate,localdate,ct.get('contract_execution_date') or raw.get('contract_execution_date'),price,rub_to_kopecks(raw.get('starting_price')),str(customer.get('id') or raw.get('organization_id') or ''),customer.get('name') or raw.get('customer_short_name'),raw.get('customer_municipality_name'),str(ct.get('supplier_id') or raw.get('supplier_id') or ''),ct.get('supplier_name') or raw.get('supplier_short_name'),cin,sin,None,subject,raw.get('proposals_count'),json.dumps(raw.get('delivery_addresses'),ensure_ascii=False),sid,json.dumps(raw,ensure_ascii=False,separators=(',',':')))
            con.execute('INSERT INTO atmo_contract_observations VALUES ('+','.join('?' for _ in vals)+')',vals)
            ids.append((raw.get('type'),raw.get('id')))
            if localdate:dates.append(localdate)
        atmoaudit.append(dict(law=law,rows=len(rs),unique_api_record_ids=len(set(ids)),total_price_kopecks=sumprice,statuses=dict(statuses),contract_date_min=min(dates) if dates else None,contract_date_max=max(dates) if dates else None,empty_normalized_contract_dates=normalizeddateempty,normalized_subject_differs_from_raw=subjectwrong,both_INNs_not_available=missinginn,negative_prices=negativeprices))
    qc('atmo_raw_fields_recovered_with_duplicates_exposed',all(a['negative_prices']==0 for a in atmoaudit),atmoaudit)
    # All eight supplied processed contract parts. Preserve their normalized fields
    # and registry-identity status; do not confuse these with independently reread XLSX/XML.
    inv=json.loads((root/'drive_inventory.json').read_text())
    remote={f['title']:f['url'] for f in inv['folders']['folder_proc_analysis']['files']}
    parts=sorted(mats.glob('contracts_unique_eis_atmo_*.csv'));assert len(parts)==8,len(parts)
    crows=0;finstatus=Counter();lawcounts=Counter();empty_supplier=0;fields=None
    for n,p in enumerate(parts,1):
        sid=source(p,f'processed_contracts_part_{n:03d}',remote[p.name],'2023-01/2026-10; event dates retained','processed_contract_exports','Reuse supplied upstream canonical identity and source references; original 1381 XLSX files not independently reprocessed in this run. Some registry identities remain unconfirmed.')
        with p.open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f,delimiter=';')
            if fields is None:
                fields=reader.fieldnames
                definitions=[]
                for col in fields:
                    tp='INTEGER' if col in ['amount_cents','raw_records','representation_variants'] else 'TEXT'
                    definitions.append('"'+col+'" '+tp+(' PRIMARY KEY' if col=='canonical_contract_id' else ''))
                con.execute('CREATE TABLE processed_contracts('+','.join(definitions)+', import_source_id TEXT REFERENCES sources)')
            assert fields==reader.fieldnames
            insert='INSERT INTO processed_contracts VALUES ('+','.join('?' for _ in range(len(fields)+1))+')';batch=[]
            for r in reader:
                crows+=1;finstatus[r['financial_status']]+=1;lawcounts[r['law']]+=1;empty_supplier+=not r['supplier_inn']
                vals=[None if r[col]=='' else int(r[col]) if col in ['amount_cents','raw_records','representation_variants'] else r[col] for col in fields]
                batch.append(tuple(vals+[sid]))
                if len(batch)==10000:con.executemany(insert,batch);batch=[]
            if batch:con.executemany(insert,batch)
        con.commit();print('Imported contract part',n,'cumulative rows',crows,flush=True)
    con.execute('CREATE INDEX contract_supplier_inn_idx ON processed_contracts(supplier_inn)')
    con.executescript('''CREATE VIEW contract_msp_asof_20260910 AS SELECT c.canonical_contract_id,c.sign_date,c.law,c.supplier_inn,c.amount_cents,c.currency,c.identity_basis,m.region_code AS msp_region_on_snapshot,'2026-09-10' AS msp_snapshot_date,CASE WHEN c.supplier_inn IS NULL THEN 'supplier_inn_unavailable' WHEN m.inn IS NOT NULL THEN 'found_in_snapshot' ELSE 'not_found_in_snapshot' END AS msp_status_asof_snapshot FROM processed_contracts c LEFT JOIN msp_supplier_index_unique m ON m.inn=c.supplier_inn AND m.snapshot_date='2026-09-10';''')
    mspjoin=dict(con.execute('SELECT msp_status_asof_snapshot,COUNT(*) FROM contract_msp_asof_20260910 GROUP BY msp_status_asof_snapshot').fetchall())
    qc('all_8_processed_contract_parts_and_MSP_join',crows==359615 and mspjoin.get('found_in_snapshot')==173892 and empty_supplier==82063,dict(imported_parts=len(parts),rows=crows,law_counts=dict(lawcounts),financial_status_counts=dict(finstatus),missing_supplier_inn=empty_supplier,msp_join=mspjoin,upstream_report_quoted_total_rub=1263174213398.89,note='MSP join is status on 2026-09-10, NOT at contract signing. Amounts across currencies/statuses/identity conflicts must not be blindly summed.'))
    p=mats/'Торги (1)(1).xlsx';sid=source(p,'trade_xlsx','supplied stored export Торги (1)(1).xlsx','read metadata/data dates in workbook','procurement_notice_export','Announcements/lots, not contract table. Never add notice amounts to signed contract amounts.')
    trades=pd.read_excel(p,dtype=str).fillna('')
    con.executemany('INSERT INTO procurement_notice_exports(source_id,raw_json) VALUES (?,?)',[(sid,json.dumps(r,ensure_ascii=False)) for r in trades.to_dict('records')])
    qc('trade_workbook_notice_grain_separate',True,dict(rows=len(trades),columns=list(trades.columns)))
    for k,v in {'database_version':'research_seed_20261009','created_at':'2026-10-09','region':'Республика Башкортостан','municipality_count':'63','status':'usable verified seed; NOT complete upgraded clustering dataset','missing_core_raw':'Original SberIndex category panel/road parquet, core EIS 2023-2024 parquet and verified historical OKTMO crosswalk are not supplied in calculation archive.','historical_rule':'2026 MSP snapshot and 2025 population may not be silently attached to 2023-2024 as information known at that time.','atmo_coverage':'223 export 910 rows; 44 sample 135 rows; manifest 493912 44 records is a supplied collector claim, not imported or independently verified in this database.'}.items():con.execute('INSERT INTO dataset_metadata VALUES (?,?)',(k,v))
    con.commit();integrity=con.execute('PRAGMA integrity_check').fetchone()[0];assert integrity=='ok'
    assert not con.execute('PRAGMA foreign_key_check').fetchall()
    counts={r[0]:con.execute('SELECT COUNT(*) FROM "'+r[0]+'"').fetchone()[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    schema='\n\n'.join(r[0]+';' for r in con.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name").fetchall())
    con.execute('PRAGMA wal_checkpoint(TRUNCATE)');con.execute('PRAGMA journal_mode=DELETE');con.close()
    # Reopen the standalone file after checkpoint: validate actual persisted bytes.
    with sqlite3.connect(out) as verified:
        assert verified.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
        assert not verified.execute('PRAGMA foreign_key_check').fetchall()
        assert verified.execute('SELECT COUNT(*) FROM processed_contracts').fetchone()[0]==359615
    report=dict(database=out.name,integrity=integrity,table_counts=counts,population_controls=popcontrols,atmo=atmoaudit,msp=dict(rows=nr,unique_inns=len(inns),category_counts=dict(categories),invalid_inn_checksum_rows=badinn,missing_headcount_rows=missinghead,address_statuses=dict(candidates)))
    (out.parent/'DATABASE_CHECKS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    (out.parent/'SOURCE_MANIFEST.json').write_text(json.dumps(source_records,ensure_ascii=False,indent=2))
    (out.parent/'SCHEMA.sql').write_text(schema)
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--input-root',type=Path,default=Path(__file__).resolve().parent);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();main(args.input_root.resolve(),args.output.resolve())
