"""Read-only checks of the supplied calculation code; no source repair."""
from pathlib import Path
import json, sys, time, resource, warnings
import numpy as np
import pandas as pd
import yaml
from sklearn.impute import KNNImputer
from sklearn.preprocessing import RobustScaler
from sklearn.metrics import silhouette_score, calinski_harabasz_score

ROOT = Path(__file__).resolve().parent
CODE = ROOT / 'calculation_source'
sys.path.insert(0, str(CODE))
from econtypes import icvi, networks, dynamics

def literature_avi_avu(W, lab):
    """Shalileh et al. DOI 10.1134/S1064562425700589, eq.18-21.
    Zero external-degree pairs contribute zero (explicit disconnected-graph extension).
    """
    cs = np.unique(lab)
    E = np.array([[W[np.ix_(lab == a, lab == b)].sum() for b in cs] for a in cs])
    inside = np.diag(E)
    outside = E.sum(1) - inside
    incident = inside + outside
    avi = np.divide(inside, incident, out=np.zeros_like(inside), where=incident > 0).mean()
    den = outside[:, None] + outside[None, :] - E
    U = np.divide(E, den, out=np.zeros_like(E), where=den > 0)
    np.fill_diagonal(U, 0)
    return float(avi), float(U.sum() / len(cs))

def run():
    results = []
    def check(name, fn):
        started = time.perf_counter()
        try:
            detail = fn()
            results.append(dict(test=name, status='PASS', detail=detail, seconds=round(time.perf_counter()-started,4)))
        except Exception as e:
            results.append(dict(test=name, status='FAIL', detail=str(e), seconds=round(time.perf_counter()-started,4)))

    raw = pd.read_csv(CODE / 'outputs/tables/features_raw_2023_2024.csv').set_index('mo')
    t = raw.copy()
    for c in ['proc_pc', 'spend_total']:
        t[c] = np.log(t[c].clip(lower=1))
    t['supply_out_pc'] = np.log1p(t['supply_out_pc'])
    t = t.fillna({c:0 for c in t if c.startswith(('okpd_','proc_'))})
    X = np.clip(RobustScaler().fit_transform(KNNImputer(n_neighbors=5).fit_transform(t)), -4,4)
    labels = pd.read_csv(CODE/'outputs/tables/clusters_final.csv').set_index('mo').reindex(raw.index)['cluster'].to_numpy()
    edges = pd.read_csv(CODE/'outputs/tables/network_edges.csv')
    idx = {m:i for i,m in enumerate(raw.index)}
    cfg=yaml.safe_load((CODE/'config/config.yaml').read_text())['network']
    layers={}
    for key in ['attr',*cfg['layer_weights']]:
        A=np.zeros((len(raw),len(raw)))
        for r in edges[edges.layer==key].itertuples():
            A[idx[r.source],idx[r.target]]=A[idx[r.target],idx[r.source]]=r.weight
        layers[key]=A
    W=networks.fuse(layers['attr'],layers,cfg['layer_weights'],cfg['alpha_attr'])
    old = icvi.all_indices(X,W,labels)
    avi, avu = literature_avi_avu(W,labels)
    recomputed = {**old, 'AVU_literature':avu, 'AVI_literature':avi,
                  'note':'Reconstructed X from exported features; full fusion rebuilt from all exported kNN layers (four-decimal weights). The separately exported fused graph is sparsified again for display and is NOT the graph used for original quality scores. Not a full raw-source rerun.'}
    def dimensions():
        assert X.shape == (63,32) and np.isfinite(X).all()
        assert np.allclose(W,W.T) and (np.diag(W)==0).all() and (W>=0).all()
        return {'N':len(X),'features':X.shape[1],'K':len(np.unique(labels)),'clustering_fused_edges':int((W>0).sum()//2),'display_fused_edges':int((edges.layer=='fused').sum())}
    check('baseline_dimensions_and_finite',dimensions)
    def reproduce():
        saved = pd.read_csv(CODE/'outputs/tables/icvi_methods_at_k.csv').set_index('method').loc['spectral_fused']
        delta={k:float(abs(old[k]-saved[k])) for k in old}
        assert max(delta.values()) < 0.002, delta
        return delta
    check('reproduce_exported_ICVI_with_rounded_edges',reproduce)
    def avu_correctness():
        assert abs(old['AVU']-avu) < 1e-10, {'implemented':old['AVU'],'literature':avu}
        assert icvi.HIGHER_BETTER['AVU'] is False, 'AVU must be minimized'
    check('AVU_formula_and_optimization_direction',avu_correctness)
    def isolated():
        lab = np.repeat(np.arange(3),4); A = (lab[:,None]==lab[None,:]).astype(float); np.fill_diagonal(A,0)
        a,u = icvi.avi_avu(A,lab); ar,ur=literature_avi_avu(A,lab)
        assert a==ar==1 and u==ur==0, {'implemented_AVU':u,'reference_AVU':ur,'AVI':a}
    check('AVU_disconnected_three_cliques',isolated)
    def ppositive():
        p = json.load(open(CODE/'outputs/validation_holdout.json'))
        assert all(v['p_value']>0 for v in p['holdout'].values()), p['holdout']
    check('finite_permutation_pvalues_are_positive',ppositive)
    def constant_dtw():
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            S = networks.dtw_similarity(pd.DataFrame(np.ones((6,24))),2)
        assert np.isfinite(S).all(), 'Constant series: sigma=0 produces NaN'
    check('DTW_all_constant_series',constant_dtw)
    def logzero():
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            R = networks.residual_series(pd.DataFrame([[0,1,2],[0,2,3]]))
        assert np.isfinite(R.to_numpy()).all(), 'Zero expenditure produces non-finite log residuals'
    check('zero_monthly_expenditure',logzero)
    def k_invalid():
        try:
            networks.knn_sparsify(np.ones((5,5)),6)
        except ValueError:
            return 'Rejected with ValueError'
        except Exception as e:
            raise AssertionError('Expected descriptive ValueError; got '+type(e).__name__)
        raise AssertionError('k >= N must be rejected explicitly')
    check('kNN_k_above_N',k_invalid)
    def future_layers():
        s = (CODE/'econtypes/pipeline.py').read_text()
        assert 'lq = dict(struct_layers)' not in s, 'Historical windows reuse comovement/lead_lag/DTW built on full 2023-2024; detected in code, not a executed future-perturbation test'
    check('historical_layers_do_not_reuse_full_horizon',future_layers)
    def scale():
        # Real execution of graph sparsification only; no claim about whole pipeline at N=2016.
        rng=np.random.default_rng(42); n=2016
        S=rng.random((n,n)); S=(S+S.T)/2
        start=time.perf_counter(); K=networks.knn_sparsify(S,8)
        assert np.isfinite(K).all() and np.allclose(K,K.T) and np.count_nonzero(np.diag(K))==0
        return {'N':n,'k':8,'seconds':round(time.perf_counter()-start,3),'dense_matrix_bytes':int(S.nbytes),'edges':int((K>0).sum()//2)}
    check('actual_kNN_stress_N_2016',scale)
    def labels_permutation():
        ref=np.array([0,0,1,1,2,2]); lab=np.array([8,8,3,3,7,7])
        assert np.array_equal(dynamics.align(lab,ref),ref)
        return 'Hungarian alignment preserves unchanged membership after label renaming'
    check('label_permutation_invariance',labels_permutation)
    def singletons():
        try: icvi.all_indices(np.eye(5),np.ones((5,5))-np.eye(5),np.arange(5))
        except ValueError: return 'sklearn rejects K=N; caller must expose reason, not show fabricated metric'
        raise AssertionError('K=N should be unavailable')
    check('ICVI_K_equals_N_rejected',singletons)
    output={'checked_at':'2026-10-09','source_archive':'econtypes_code (4).zip','checks':results,'recomputed':recomputed,
            'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'scope':'Read-only function checks and static leakage check. Full project test suite and raw ingest were not run: core raw parquet files and dependencies are absent.'}
    (ROOT/'project_checks.json').write_text(json.dumps(output,ensure_ascii=False,indent=2))
    print(json.dumps(output,ensure_ascii=False,indent=2))

if __name__=='__main__': run()
