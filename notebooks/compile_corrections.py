import json
import gzip
import cloudpickle
import pickle
import uproot
import numpy as np
from fnal_column_analysis_tools import hist, lookup_tools
from fnal_column_analysis_tools.hist import plot


corrections = {}

extractor = lookup_tools.extractor()
extractor.add_weight_sets(["2017_n2ddt_ * correction_files/n2ddt_transform_2017MC.root"])
extractor.add_weight_sets(["2017_mutrigger_ * correction_files/EfficienciesAndSF_RunBtoF_Nov17Nov2017.root"])
extractor.add_weight_sets(["2017_muid_ * correction_files/Muon2017_RunBCDEF_SF_ID.json"])
extractor.add_weight_sets(["2017_muiso_ * correction_files/Muon2017_RunBCDEF_SF_ISO.json"])
extractor.finalize()
evaluator = extractor.make_evaluator()

corrections['2017_n2ddt_rho_pt'] = evaluator['2017_n2ddt_Rho2D']
corrections['2017_mutrigweight_pt_abseta'] = evaluator['2017_mutrigger_Mu50_PtEtaBins/efficienciesDATA/pt_abseta_DATA']
corrections['2017_mutrigweight_pt_abseta_mutrigweightShift'] = evaluator['2017_mutrigger_Mu50_PtEtaBins/efficienciesDATA/pt_abseta_DATA_error']
corrections['2017_muidweight_abseta_pt'] = evaluator['2017_muid_NUM_SoftID_DEN_genTracks/abseta_pt_value']
corrections['2017_muidweight_abseta_pt_muidweightShift'] = evaluator['2017_muid_NUM_SoftID_DEN_genTracks/abseta_pt_error']


gpar = np.array([1.00626, -1.06161, 0.0799900, 1.20454])
cpar = np.array([1.09302, -0.000150068, 3.44866e-07, -2.68100e-10, 8.67440e-14, -1.00114e-17])
fpar = np.array([1.27212, -0.000571640, 8.37289e-07, -5.20433e-10, 1.45375e-13, -1.50389e-17])
def msd_weight(pt, eta):
    genw = gpar[0] + gpar[1]*np.power(pt*gpar[2], -gpar[3])
    ptpow = np.power.outer(pt, np.arange(cpar.size))
    cenweight = np.dot(ptpow, cpar)
    forweight = np.dot(ptpow, fpar)
    weight = np.where(np.abs(eta)<1.3, cenweight, forweight)
    return weight

corrections['msdweight'] = msd_weight


with gzip.open("correction_files/pileup_mc.pkl.gz", "rb") as fin:
    pileup_corr = pickle.load(fin)

with uproot.open("correction_files/pileup_Cert_294927-306462_13TeV_PromptReco_Collisions17_withVar.root") as fin:
    data_pu = fin["pileup"].values
    for k in pileup_corr.keys():
        mc_pu = pileup_corr[k]
        corr = (data_pu / np.maximum(mc_pu, 1)) / (data_pu.sum() / mc_pu.sum())
        corr[mc_pu==0.] = 1.
        pileup_corr[k] = lookup_tools.dense_lookup.dense_lookup(corr, fin["pileup"].edges)

corrections['2017_pileupweight_dataset'] = pileup_corr


with uproot.open("correction_files/TrigEff_2017BtoF_noPS_Feb21.root") as fin:
    denom = fin["h_denom"]
    num = fin["h_numer"]
    eff = num.values/np.maximum(denom.values, 1)
    efferr = plot.clopper_pearson_interval(num.values, denom.values)
    msd_bins, pt_bins = num.edges
    # Cut pt < 200
    pt_bins = pt_bins[8:]
    eff = eff[:,8:]
    eff_trigweightDown = efferr[0,:,8:]
    eff_trigweightUp = efferr[1,:,8:]

corrections['2017_trigweight_msd_pt'] = lookup_tools.dense_lookup.dense_lookup(eff, (msd_bins, pt_bins))
corrections['2017_trigweight_msd_pt_trigweightDown'] = lookup_tools.dense_lookup.dense_lookup(eff_trigweightDown, (msd_bins, pt_bins))
corrections['2017_trigweight_msd_pt_trigweightUp'] = lookup_tools.dense_lookup.dense_lookup(eff_trigweightUp, (msd_bins, pt_bins))


with open("correction_files/TriggerBitMap.json") as fin:
    trigger_bitmap = json.load(fin)

def triggermask(names, triggerMap):
    version     = names['version']
    hltNames    = names['names']
    branchName  = names['branchName']
    if version in triggerMap:
        bits = triggerMap[version]
    else:
        raise ValueError("Cannot find triggerbit map of the requested bit version =%s. Possible versions are: %s" % (version, ",".join(triggerMap.keys())))
    tCuts = []
    mask = np.array(0, dtype='uint64')
    for hltName in hltNames:
        if hltName not in bits:
            raise ValueError("Cannot find the TriggerBit for %s" % hltName)
        mask |= np.array(1<<int(bits[hltName]), dtype=mask.dtype)
    return mask

triggerNames_2017 = {
    "version": "zprimebit-15.01",
    "branchName":"triggerBits",
    "names": [
        "HLT_AK8PFJet330_PFAK8BTagCSV_p17_v*",
        "HLT_PFHT1050_v*",
        "HLT_AK8PFJet400_TrimMass30_v*",
        "HLT_AK8PFJet420_TrimMass30_v*",
        "HLT_AK8PFHT800_TrimMass50_v*",
        "HLT_PFJet500_v*",
        "HLT_AK8PFJet500_v*"
    ]
}

corrections['2017_triggerMask'] = triggermask(triggerNames_2017, trigger_bitmap)

triggerNames_2018 = {
    "version": "zprimebit-15.01",
    "branchName": "triggerBits",
    "names": [
        'HLT_AK8PFJet400_TrimMass30_v*',
        'HLT_AK8PFJet420_TrimMass30_v*',
        'HLT_AK8PFHT800_TrimMass50_v*',
        'HLT_PFHT1050_v*',
        'HLT_PFJet500_v*',
        'HLT_AK8PFJet500_v*',
        'HLT_AK8PFJet330_PFAK8BTagCSV_p17_v*',
        "HLT_AK8PFJet330_TrimMass30_PFAK8BoostedDoubleB_np4_v*",
    ],
}

corrections['2018_triggerMask'] = triggermask(triggerNames_2018, trigger_bitmap)


with gzip.open("corrections.cpkl.gz", "wb") as fout:
    cloudpickle.dump(corrections, fout)