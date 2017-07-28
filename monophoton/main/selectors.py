import sys
import os
import array
import logging

needHelp = False
for opt in ['-h', '--help']:
    if opt in sys.argv:
        needHelp = True
        sys.argv.remove(opt)

thisdir = os.path.dirname(os.path.realpath(__file__))
basedir = os.path.dirname(thisdir)
datadir = basedir + '/data'

if basedir not in sys.path:
    sys.path.append(basedir)

import config

logger = logging.getLogger(__name__)

import ROOT

ROOT.gSystem.Load(config.libobjs)
ROOT.gSystem.Load('libfastjet.so')

# if the objects library is compiled with CLING dictionaries, ROOT must load the
# full library first before compiling the macros.
try:
    e = ROOT.panda.Event
except AttributeError:
    pass

ROOT.gROOT.LoadMacro(thisdir + '/operators.cc+')
try:
    o = ROOT.Operator
except:
    logger.error("Couldn't compile operators.cc. Quitting.")
    sys.exit(1)

ROOT.gROOT.LoadMacro(thisdir + '/selectors.cc+')
try:
    o = ROOT.EventSelectorBase
except:
    logger.error("Couldn't compile selectors.cc. Quitting.")
    sys.exit(1)

## Selector-dependent configurations

selconf = {
    'photonFullSelection': [],
    'photonIDTune': -1,
    'photonWP': 1,
    'puweightSource': ('', ''), # gROOT directory name, file name
    'hadronTFactorSource': ('', ''), # file name, suffix
    'hadronProxyDef': []
}
ROOT.gROOT.ProcessLine("int idtune;")

def monophotonSetting():
    logger.info('Applying monophoton setting.')

    selconf['photonFullSelection'] = [
        'HOverE',
        'Sieie',
        'NHIso',
        'PhIso',
        'CHIsoMax',
        'EVeto',
        'MIP49',
        'Time',
        'SieieNonzero',
        'SipipNonzero',
        'NoisyRegion'
    ]
    ROOT.gROOT.ProcessLine("idtune = panda::XPhoton::kGJetsCWIso;")
    selconf['photonIDTune'] = ROOT.idtune
    selconf['puweightSource'] = ('puweight_fulllumi', datadir + '/pileup.root')
    selconf['hadronTFactorSource'] = (datadir + '/hadronTFactor.root', '_gjetscwiso')
    selconf['hadronProxyDef'] = ['!CHIsoMax', '+CHIsoMax11']

def vbfgSetting():
    logger.info('Applying vbfg setting.')

    selconf['photonFullSelection'] = [
        'HOverE',
        'Sieie',
        'NHIso',
        'PhIso',
        'CHIso',
        'EVeto'
    ]
    ROOT.gROOT.ProcessLine("idtune = panda::XPhoton::kSpring16;")
    selconf['photonIDTune'] = ROOT.idtune
    selconf['puweightSource'] = ('puweight_vbf75', datadir + '/pileup_vbf75.root')
    selconf['hadronTFactorSource'] = (datadir + '/hadronTFactor_Spring16.root', '_spring16')
    selconf['hadronProxyDef'] = ['!CHIso', '+CHIso11']

## utility functions

def setupPhotonSelection(operator, veto = False, changes = []):
    ##### !!!!! IMPORTANT - NOTE THE RESETS #####
    if veto:
        operator.resetVeto()
    else:
        operator.resetSelection()

    sels = list(selconf['photonFullSelection'])

    for change in changes:
        if change.startswith('-'):
            sels.remove(change[1:])
        elif change.startswith('+'):
            sels.append(change[1:])
        elif change.startswith('!'):
            try:
                sels.remove(change[1:])
            except:
                pass

            sels.append(change)

    if veto:
        for sel in sels:
            if sel.startswith('!'):
                operator.addVeto(False, getattr(ROOT.PhotonSelection, sel[1:]))
            else:
                operator.addVeto(True, getattr(ROOT.PhotonSelection, sel))
    else:
        for sel in sels:
            if sel.startswith('!'):
                operator.addSelection(False, getattr(ROOT.PhotonSelection, sel[1:]))
            else:
                operator.addSelection(True, getattr(ROOT.PhotonSelection, sel))
    
# avoid auto-deletion by python
_garbage = []

# Other weights
def getFromFile(path, name, newname = ''):
    if newname == '':
        newname = name

    obj = ROOT.gROOT.Get(newname)
    if obj:
        return obj

    f = ROOT.TFile.Open(path)
    orig = f.Get(name)
    if not orig:
        return None

    ROOT.gROOT.cd()
    obj = orig.Clone(newname)

    f.Close()

    logger.debug('Picked up %s from %s', name, path)
    
    _garbage.append(obj)

    return obj

##################
# BASE SELECTORS #
##################

def monophotonBase(sample, rname, selcls = None):
    """
    Monophoton candidate-like selection (high-pT photon, lepton veto, dphi(photon, MET) and dphi(jet, MET)).
    Base for other selectors.
    """

    monophotonSetting()

    if selcls is None:
        selector = ROOT.EventSelector(rname)
    else:
        selector = selcls(rname)

    if sample.data:
        selector.addOperator(ROOT.HLTFilter('HLT_Photon165_HE10'))

    operators = [
        'MetFilters',
        'PhotonSelection',
        'LeptonSelection',
        'TauVeto',
        'JetCleaning',
        'BjetVeto',
        'CopyMet',
        'CopySuperClusters'
    ]

    if not sample.data:
        operators.append('MetVariations')
        
    operators += [
        'PhotonMetDPhi',
        'JetMetDPhi',
        'PhotonJetDPhi',
        'Met',
        'PhotonMt'
    ]

    for op in operators:
        selector.addOperator(getattr(ROOT, op)())

    photonSel = selector.findOperator('PhotonSelection')
    photonSel.setMinPt(175.)
    photonSel.setIDTune(selconf['photonIDTune'])
    photonSel.setWP(selconf['photonWP'])

    leptonSel = selector.findOperator('LeptonSelection')
    leptonSel.setN(0, 0)
    leptonSel.setRequireMedium(False)
    leptonSel.setRequireTight(False)

    if not sample.data:
        metVar = selector.findOperator('MetVariations')
        metVar.setPhotonSelection(photonSel)

        photonDPhi = selector.findOperator('PhotonMetDPhi')
        photonDPhi.setMetVariations(metVar)
        
        jetDPhi = selector.findOperator('JetMetDPhi')
        jetDPhi.setMetVariations(metVar)

        selector.findOperator('PhotonJetDPhi').setMetVariations(metVar)

        selector.addOperator(ROOT.ConstantWeight(sample.crosssection / sample.sumw, 'crosssection'))

        addPUWeight(sample, selector)
        addPDFVariation(sample, selector)

    selector.findOperator('TauVeto').setIgnoreDecision(True)
    selector.findOperator('BjetVeto').setIgnoreDecision(True)
    selector.findOperator('JetCleaning').setCleanAgainst(ROOT.cTaus, False)
    selector.findOperator('PhotonMetDPhi').setIgnoreDecision(True)
    selector.findOperator('JetMetDPhi').setIgnoreDecision(True)
    selector.findOperator('Met').setIgnoreDecision(True)

    return selector

def emjetBase(sample, rname):
    """
    Base selector for EM+Jet control region. For MC, a gen-level photon is required.
    """

    monophotonSetting()

    selector = monophotonBase(sample, rname)

    selector.removeOperator('PhotonMt')

    selector.findOperator('Met').setThreshold(0.)
    selector.findOperator('Met').setCeiling(170.)
    selector.findOperator('Met').setIgnoreDecision(False)

    photonSel = selector.findOperator('PhotonSelection')

    jets = ROOT.HighPtJetSelection()
    jets.setJetPtCut(100.)
    selector.addOperator(jets)

    dijetSel = ROOT.DijetSelection()
    dijetSel.setMinDEta(3.)
    dijetSel.setMinMjj(500.)
    dijetSel.setIgnoreDecision(True)
    selector.addOperator(dijetSel)

    if not sample.data:
        genPhotonSel = ROOT.GenParticleSelection("GenPhotonSelection")
        genPhotonSel.setPdgId(22)
        genPhotonSel.setMinPt(140.)
        genPhotonSel.setMaxEta(1.7)

        selector.addOperator(genPhotonSel, 1)

    return selector

def leptonBase(sample, rname, flavor, selcls = None):
    """
    Base for n-lepton + photon selection.
    For MC, we could use PartonSelector, but for interest of clarity and comparing cut flow
    with the other groups, we let events with all flavors pass.
    """

    monophotonSetting()

    if selcls is None:
        selector = ROOT.EventSelector(rname)
    else:
        selector = selcls(rname)

    if sample.data:
        selector.addOperator(ROOT.HLTFilter('HLT_Photon165_HE10'))
    else:
        partons = ROOT.PartonFlavor()
        if flavor == ROOT.lElectron:
            partons.setRequiredPdgId(11)
        elif flavor == ROOT.lMuon:
            partons.setRequiredPdgId(13)

        selector.addOperator(partons)

    operators = [
        'MetFilters',
        'PhotonSelection',
        'LeptonSelection',
        'TauVeto',
        'JetCleaning',
        'BjetVeto',
        'CopyMet',
        'CopySuperClusters',
        'LeptonRecoil',
    ]

    if not sample.data:
        operators.append('MetVariations')
        
    operators += [
        'PhotonMetDPhi',
        'JetMetDPhi',
        'Met'
    ]

    for op in operators:
        selector.addOperator(getattr(ROOT, op)())

    jetDPhi = selector.findOperator('JetMetDPhi')
    jetDPhi.setMetSource(ROOT.kInMet)

    photonSel = selector.findOperator('PhotonSelection')
    photonSel.setIDTune(selconf['photonIDTune'])
    photonSel.setWP(selconf['photonWP'])

    leptonSel = selector.findOperator('LeptonSelection')
    leptonSel.setRequireMedium(False)

    setupPhotonSelection(photonSel)

    selector.findOperator('LeptonRecoil').setFlavor(flavor)

    if not sample.data:
        metVar = selector.findOperator('MetVariations')
        metVar.setPhotonSelection(photonSel)

        realMetVar = ROOT.MetVariations('RealMetVar')
        realMetVar.setMetSource(ROOT.kInMet)
        realMetVar.setPhotonSelection(photonSel)

        selector.findOperator('PhotonMetDPhi').setMetVariations(metVar)
        
        jetDPhi.setMetVariations(realMetVar)

        selector.addOperator(ROOT.ConstantWeight(sample.crosssection / sample.sumw, 'crosssection'))

        addPUWeight(sample, selector)
        addIDSFWeight(sample, selector)
        addPDFVariation(sample, selector)

        if flavor == ROOT.lElectron:
            addElectronIDSFWeight(sample, selector)
        else:
            addMuonIDSFWeight(sample, selector)

    if not sample.data:
        selector.findOperator('PartonFlavor').setIgnoreDecision(True)

    selector.findOperator('TauVeto').setIgnoreDecision(True)
    selector.findOperator('BjetVeto').setIgnoreDecision(True)
    selector.findOperator('JetCleaning').setCleanAgainst(ROOT.cTaus, False)
    selector.findOperator('PhotonMetDPhi').setIgnoreDecision(True)
    selector.findOperator('JetMetDPhi').setIgnoreDecision(True)
    selector.findOperator('Met').setIgnoreDecision(True)

    return selector

def zmumu(sample, rname):
    """
    Just dimuon. 
    """

    selconf['puweightSource'] = ('puweight_fulllumi', datadir + '/pileup.root')

    selector = ROOT.EventSelector(rname)
    selector.setCanPhotonSkim(False)

    selector.addOperator(ROOT.MetFilters())

    leptons = ROOT.LeptonSelection()
    leptons.setN(0, 2)
    leptons.setStrictMu(False)
    leptons.setRequireTight(False)
    selector.addOperator(leptons)

    vtx = ROOT.LeptonVertex()
    vtx.setSpecies(ROOT.lMuon)
    selector.addOperator(vtx)

    mass = ROOT.Mass()
    mass.setPrefix('dimu')
    mass.setMin(60.)
    mass.setMax(120.)
    mass.setCollection1(ROOT.cMuons)
    mass.setCollection2(ROOT.cMuons)
    selector.addOperator(mass)

    if not sample.data:
        selector.addOperator(ROOT.ConstantWeight(sample.crosssection / sample.sumw, 'crosssection'))

        addPUWeight(sample, selector)

        if 'amcatnlo' in sample.fullname or 'madgraph' in sample.fullname: # ouh la la..
            selector.addOperator(ROOT.NNPDFVariation())

    return selector

def TagAndProbeBase(sample, rname):
    """
    Base for Z->ll tag and probe stuff.
    """

    selconf['puweightSource'] = ('puweight_fulllumi', datadir + '/pileup.root')

    selector = ROOT.EventSelector(rname)

    operators = [
        'MetFilters',
        'LeptonSelection',
        'TauVeto',
        'TagAndProbePairZ',
        'JetCleaning',
        'BjetVeto',
        'CopyMet',
        'CopySuperClusters',
        'JetMetDPhi',
        'Met'
    ]
    
    for op in operators:
        selector.addOperator(getattr(ROOT, op)())

    if not sample.data:
        selector.addOperator(ROOT.ConstantWeight(sample.crosssection / sample.sumw))

        addPUWeight(sample, selector)

    selector.findOperator('LeptonSelection').setN(0, 0)

    selector.findOperator('LeptonSelection').setIgnoreDecision(True)
    selector.findOperator('TauVeto').setIgnoreDecision(True)
    selector.findOperator('BjetVeto').setIgnoreDecision(True)
    selector.findOperator('JetCleaning').setCleanAgainst(ROOT.cTaus, False)
    # selector.findOperator('JetCleaning').setCleanAgainst(ROOT.cElectrons, False)
    selector.findOperator('Met').setThreshold(50.)
    selector.findOperator('Met').setIgnoreDecision(True)

    return selector

def tagprobeBase(sample, rname):
    """
    Base for selectors skimming tag & probe input trees.
    """

    selconf['puweightSource'] = ('puweight_fulllumi', datadir + '/pileup.root')

    selector = ROOT.TagAndProbeSelector(rname)

    setSampleId(sample, selector)

    if not sample.data:
        selector.addOperator(ROOT.ConstantWeight(sample.crosssection / sample.sumw))
        addPUWeight(sample, selector)

    return selector

def vbfgBase(sample, rname):
    """
    Base for VBF + photon.
    """

    vbfgSetting()

    selector = ROOT.EventSelector(rname)
    selector.setCanPhotonSkim(False)

    selector.addOperator(ROOT.HLTFilter('HLT_Photon75_R9Id90_HE10_Iso40_EBOnly_VBF'))

    operators = [
        'MetFilters',
        'PhotonSelection',
        'LeptonSelection',
        'JetCleaning',
        'DijetSelection',
        'BjetVeto',
        'CopyMet',
        'PhotonMt',
        'PhotonMetDPhi',
        'JetMetDPhi'
    ]

    for op in operators:
        selector.addOperator(getattr(ROOT, op)())

    photonSel = selector.findOperator('PhotonSelection')
    photonSel.setIDTune(1)
    photonSel.setMinPt(80.)

    leptonSel = selector.findOperator('LeptonSelection')
    leptonSel.setN(0, 0)
    leptonSel.setRequireTight(False)
    leptonSel.setRequireMedium(False)

    dijetSel = selector.findOperator('DijetSelection')
    dijetSel.setMinDEta(3.)
    dijetSel.setMinMjj(500.)

    selector.findOperator('JetCleaning').setCleanAgainst(ROOT.cTaus, False)

    if not sample.data:
        selector.addOperator(ROOT.ConstantWeight(sample.crosssection / sample.sumw, 'crosssection'))

        addPUWeight(sample, selector)
        addPDFVariation(sample, selector)

    selector.findOperator('BjetVeto').setIgnoreDecision(True)
    selector.findOperator('PhotonMetDPhi').setIgnoreDecision(True)
    selector.findOperator('JetMetDPhi').setIgnoreDecision(True)

    return selector


#####################
# DERIVED SELECTORS #
#####################

def monoph(sample, rname):
    """
    Full monophoton selection.
    """

    selector = monophotonBase(sample, rname)

    setupPhotonSelection(selector.findOperator('PhotonSelection'))

    if not sample.data:
        addIDSFWeight(sample, selector)

    return selector

def monophNoE(sample, rname):
    """
    Full monophoton selection filtering out electron events.
    """

    selector = monophotonBase(sample, rname, selcls = ROOT.PartonSelector)
    selector.setRejectedPdgId(11)

    setupPhotonSelection(selector.findOperator('PhotonSelection'))

    addIDSFWeight(sample, selector)

    return selector

def monophNoLVeto(sample, rname):
    """
    Full monophoton selection without lepton veto (for lepton veto eff. scale factor measurement)
    """

    selector = monoph(sample, rname)

    selector.findOperator('LeptonSelection').setIgnoreDecision(True)

    return selector

def signalRaw(sample, rname):
    """
    Ignore decisions of all cuts to compare shapes for different simulations.
    """

    selector = monoph(sample, rname)

    cuts = [
        'MetFilters',
        'PhotonSelection',
        'LeptonSelection',
        'TauVeto',
        'PhotonMetDPhi',
        'JetMetDPhi',
        'Met'
    ]

    for cut in cuts:
        selector.findOperator(cut).setIgnoreDecision(True)

    selector.findOperator('PhotonSelection').setMinPt(30.)
    selector.findOperator('LeptonSelection').setN(0, 0)
    
    dimuMass = ROOT.Mass()
    dimuMass.setPrefix('dimu')
    dimuMass.setMin(60.)
    dimuMass.setMax(120.)
    dimuMass.setCollection1(ROOT.cMuons)
    dimuMass.setCollection2(ROOT.cMuons)
    dimuMass.setIgnoreDecision(True)
    selector.addOperator(dimuMass)

    dielMass = ROOT.Mass()
    dielMass.setPrefix('diel')
    dielMass.setMin(60.)
    dielMass.setMax(120.)
    dielMass.setCollection1(ROOT.cElectrons)
    dielMass.setCollection2(ROOT.cElectrons)
    dielMass.setIgnoreDecision(True)
    selector.addOperator(dielMass)

    return selector

def efake(sample, rname):
    """
    Candidate-like but with inverted electron veto
    """

    selector = monophotonBase(sample, rname)

    modEfake(selector)

    return selector

def emjet(sample, rname):
    """
    EM Object is candidate-like. used for photon purity measurement and hadronTFactor derivation.
    """

    selector = emjetBase(sample, rname)

    if not sample.data:
        # measure the parton-level dR between gamma and q/g.
        selector.addOperator(ROOT.GJetsDR())

    photonSel = selector.findOperator('PhotonSelection')
    
    setupPhotonSelection(photonSel, changes = ['-Sieie', '+Sieie15', '-CHIsoMax', '-NHIso', '+NHIsoLoose', '-PhIso', '+PhIsoLoose', '-EVeto'])
        
    return selector

def hfake(sample, rname):
    """
    Candidate-like but with inverted CHIso.
    """

    selector = monophotonBase(sample, rname)

    filename, suffix = selconf['hadronTFactorSource']

    hadproxyTightWeight = getFromFile(filename, 'tfactTight', 'tfactTight' + suffix)
    hadproxyLooseWeight = getFromFile(filename, 'tfactLoose', 'tfactLoose' + suffix)
    hadproxyPurityUpWeight = getFromFile(filename, 'tfactNomPurityUp', 'tfactNomPurityUp' + suffix)
    hadproxyPurityDownWeight = getFromFile(filename, 'tfactNomPurityDown', 'tfactNomPurityDown' + suffix)

    modHfake(selector)

    weight = selector.findOperator('hadProxyWeight')

    weight.addVariation('proxyDefUp', hadproxyTightWeight)
    weight.addVariation('proxyDefDown', hadproxyLooseWeight)
    weight.addVariation('purityUp', hadproxyPurityUpWeight)
    weight.addVariation('purityDown', hadproxyPurityDownWeight)

    photonSel = selector.findOperator('PhotonSelection')

    # Need to keep the cuts looser than nominal to accommodate proxyDefUp & Down
    # Proper cut applied at plotconfig as variations
    setupPhotonSelection(photonSel, changes = ['!CHIsoMax', '+CHIsoMax11', '-NHIso', '+NHIsoLoose', '-PhIso', '+PhIsoLoose'])
    setupPhotonSelection(photonSel, veto = True)

    return selector

def hfakeVtx(sample, rname):
    """
    Candidate-like but with inverted CHIso and vertex-adjusted proxy weighting.
    """

    selector = monophotonBase(sample, rname)

    filename, suffix = selconf['hadronTFactorSource']

    hadproxyTightWeight = getFromFile(filename, 'tfactTight', 'tfactTight' + suffix)
    hadproxyLooseWeight = getFromFile(filename, 'tfactLoose', 'tfactLoose' + suffix)
    hadproxyPurityUpWeight = getFromFile(filename, 'tfactNomPurityUp', 'tfactNomPurityUp' + suffix)
    hadproxyPurityDownWeight = getFromFile(filename, 'tfactNomPurityDown', 'tfactNomPurityDown' + suffix)

    isoTFactor = getFromFile(filename, 'tfactNom', 'tfactNom' + suffix)
    noIsoTFactor = getFromFile(datadir + '/hadronTFactorNoICH.root', 'tfactNom')
    isoVertexScore = getFromFile(datadir + '/vertex_scores.root', 'iso')
    noIsoVertexScore = getFromFile(datadir + '/vertex_scores.root', 'noIso')
    rcProb = getFromFile(datadir + '/randomcone.root', 'chIso')

    vtxWeight = ROOT.VtxAdjustedJetProxyWeight(isoTFactor, isoVertexScore, noIsoTFactor, noIsoVertexScore)

    vtxWeight.setRCProb(rcProb, 1.163)
    vtxWeight.addVariation('proxyDefUp', hadproxyTightWeight)
    vtxWeight.addVariation('proxyDefDown', hadproxyLooseWeight)
    vtxWeight.addVariation('purityUp', hadproxyPurityUpWeight)
    vtxWeight.addVariation('purityDown', hadproxyPurityDownWeight)

    selector.addOperator(vtxWeight)

    photonSel = selector.findOperator('PhotonSelection')

    # Need to keep the cuts looser than nominal to accommodate proxyDefUp & Down
    # Proper cut applied at plotconfig as variations
    setupPhotonSelection(photonSel, changes = ['!CHIsoMax', '+CHIsoMax11', '-NHIso', '+NHIsoLoose', '-PhIso', '+PhIsoLoose'])
    setupPhotonSelection(photonSel, veto = True)

    return selector

def gjets(sample, rname):
    """
    For GJets MC study. 
    """
    
    selector = emjetBase(sample, rname)

    if not sample.data:
        # measure the parton-level dR between gamma and q/g.
        selector.addOperator(ROOT.GJetsDR())

    photonSel = selector.findOperator('PhotonSelection')

    setupPhotonSelection(photonSel, changes = ['-Sieie', '-CHIsoMax', '+Sieie15', '+CHIsoMax11'])
    photonSel.addSelection(False, ROOT.PhotonSelection.Sieie12, ROOT.PhotonSelection.CHIso)
    setupPhotonSelection(photonSel, veto = True)
    
    return selector

def gjSmeared(sample, rname):
    """
    Candidate-like, with a smeared MET distribution.
    """

    selector = monophotonBase(sample, rname, selcls = ROOT.SmearingSelector)

    params = {}
    paramsFile = file(datadir + '/gjSmearParams_linear.txt', 'r')
    for line in paramsFile:
        param = line.split()
        params[param[0]] = (param[1], param[2])
    paramsFile.close()

    smearing = ROOT.TF1('smearing', 'TMath::Landau(x, [0], [1]*(1. + [2]*x))', 0., 100.)
    mean = params['mean'][0]
    sigmar = params['sigmar'][0]
    alpha = params['alpha'][0]
    smearing.SetParameters(mean, sigmar, alpha) # measured in gjets/smearfit.py
    selector.setNSamples(1)
    selector.setFunction(smearing)

    setupPhotonSelection(selector.findOperator('PhotonSelection'))

    addIDSFWeight(sample, selector)

    return selector

def dijet(sample, rname):
    """
    Dijet events with no overlap removal for jet vertex score study.
    """

    monophotonSetting()
    
    selector = ROOT.EventSelector(rname)

    if sample.data:
        selector.addOperator(ROOT.HLTFilter('HLT_Photon165_HE10'))

    photonSel = ROOT.PhotonSelection()
    
    setupPhotonSelection(photonSel, changes = ['!Sieie'])
    setupPhotonSelection(photonSel, veto = True)

    selector.addOperator(photonSel)

    jets = ROOT.JetClustering()
    jets.setMinPt(30.)
    jets.setOverwrite(True)
    selector.addOperator(jets)

    photonSel.setIgnoreDecision(True)

#    jetSel = ROOT.HighPtJetSelection()
#    jetSel.setJetPtCut(150.)
#    jetSel.setNMin(2)
#    jetSel.setNMax(2)
#    selector.addOperator(jetSel)

    selector.addOperator(ROOT.JetScore())

    selector.addOperator(ROOT.CopyMet())

    if not sample.data:
        addPDFVariation(sample, selector)

    return selector

def halo(sample, rname):
    """
    Candidate sample but with inverted MIP cut and halo tag.
    """

    selector = monophotonBase(sample, rname)

    photonSel = selector.findOperator('PhotonSelection')

    # setting up loose to allow variations at plot level
    setupPhotonSelection(photonSel, changes = ['-MIP49', '-Sieie'])
    setupPhotonSelection(photonSel, veto = True)

    selector.findOperator('MetFilters').setFilter(0, 0)

    return selector

def trivialShower(sample, rname):
    """
    Candidate sample but with inverted sieie cut.
    """

    selector = monophotonBase(sample, rname)

    photonSel = selector.findOperator('PhotonSelection')

    setupPhotonSelection(photonSel, changes = ['-SieieNonzero', '-SipipNonzero'])
    photonSel.addSelection(True, ROOT.PhotonSelection.Sieie08, ROOT.PhotonSelection.Sipip08)

    return selector

def diel(sample, rname):
    selector = leptonBase(sample, rname, ROOT.lElectron)
    selector.findOperator('LeptonSelection').setN(2, 0)

    dielMass = ROOT.Mass()
    dielMass.setPrefix('diel')
    dielMass.setMin(60.)
    dielMass.setMax(120.)
    dielMass.setCollection1(ROOT.cElectrons)
    dielMass.setCollection2(ROOT.cElectrons)
    dielMass.setIgnoreDecision(True)
    selector.addOperator(dielMass)

    dielSign = ROOT.OppositeSign()
    dielSign.setPrefix('diel')
    dielSign.setCollection1(ROOT.cElectrons)
    dielSign.setCollection2(ROOT.cElectrons)
    dielSign.setIgnoreDecision(True)
    selector.addOperator(dielSign)

    if not sample.data:
        electronLooseSF = getFromFile(datadir + '/egamma_electron_loose_SF_ichep.root', 'EGamma_SF2D', 'electronLooseSF') # x: sc eta, y: pt
        electronTrackSF = getFromFile(datadir + '/egamma_gsf_tracking_SF_ichep.root', 'EGamma_SF2D', 'electronTrackSF') # x: sc eta, y: npv

        idsf = selector.findOperator('ElectronSF')
        idsf.addFactor(electronLooseSF)
        idsf.setNParticles(2)

        track = selector.findOperator('GsfTrackSF')
        track.addFactor(electronTrackSF)
        track.setNParticles(2)

    return selector

def dielAllPhoton(sample, rname):
    selector = diel(sample, rname)

    vtx = ROOT.LeptonVertex()
    vtx.setSpecies(ROOT.lElectron)
    selector.addOperator(vtx)

    electrons = selector.findOperator('LeptonSelection')
    electrons.setRequireTight(True)

    photons = selector.findOperator('PhotonSelection')
    photons.resetSelection()
    photons.addSelection(True, ROOT.PhotonSelection.HOverE)

    return selector

def dielHfake(sample, rname):
    selector = diel(sample, rname)
        
    modHfake(selector)

    return selector

def monoel(sample, rname, selcls = None):
    selector = leptonBase(sample, rname, ROOT.lElectron, selcls = selcls)
    selector.findOperator('LeptonSelection').setN(1, 0)

    mtCut = ROOT.LeptonMt()
    mtCut.setFlavor(ROOT.lElectron)
    mtCut.setMax(160.)
    mtCut.setIgnoreDecision(True)
    selector.addOperator(mtCut)

    metCut = ROOT.Met('RealMetCut')
    metCut.setMetSource(ROOT.kInMet)
    metCut.setThreshold(50.)
    metCut.setIgnoreDecision(True)
    selector.addOperator(metCut)

    return selector

def monoelHfake(sample, rname):
    selector = monoel(sample, rname)
    
    modHfake(selector)

    return selector

def monoelEfake(sample, rname):
    selector = monoel(sample, rname, selcls = ROOT.ZeeEventSelector)
    selector.findOperator('LeptonSelection').setStrictEl(False)

    modEfake(selector)

    return selector

def monoelQCD(sample, rname):
    selector = monoel(sample, rname)

    # by inserting FakeElectron before LeptonSelection, electron collection size
    # is already bumped up by the number of fake electrons. LeptonSelection will
    # count the number of output electron collection.
    idx = selector.index('LeptonSelection')
    selector.addOperator(ROOT.FakeElectron(), idx)

    leptonSel = selector.findOperator('LeptonSelection')
    leptonSel.setRequireMedium(False)
    leptonSel.setRequireTight(False)

    return selector

def dimu(sample, rname):
    selector = leptonBase(sample, rname, ROOT.lMuon)
    selector.findOperator('LeptonSelection').setN(0, 2)

    dimuMass = ROOT.Mass()
    dimuMass.setPrefix('dimu')
    dimuMass.setMin(60.)
    dimuMass.setMax(120.)
    dimuMass.setCollection1(ROOT.cMuons)
    dimuMass.setCollection2(ROOT.cMuons)
    dimuMass.setIgnoreDecision(True)
    selector.addOperator(dimuMass)

    dimuSign = ROOT.OppositeSign()
    dimuSign.setPrefix('dimu')
    dimuSign.setCollection1(ROOT.cMuons)
    dimuSign.setCollection2(ROOT.cMuons)
    dimuSign.setIgnoreDecision(True)
    selector.addOperator(dimuSign)

    if not sample.data:
        muonLooseSF = getFromFile(datadir + '/scaleFactor_muon_looseid_12p9.root', 'scaleFactor_muon_looseid_RooCMSShape') # x: abs eta, y: pt
        muonTrackSF = getFromFile(datadir + '/muonpog_muon_tracking_SF_ichep.root', 'htrack2') # x: npv

        idsf = selector.findOperator('MuonSF')
        idsf.addFactor(muonLooseSF)
        idsf.setNParticles(2)

        track = selector.findOperator('MuonTrackSF')
        track.addFactor(muonTrackSF)
        track.setNParticles(2)

    return selector

def dimuAllPhoton(sample, rname):
    selector = dimu(sample, rname)

    vtx = ROOT.LeptonVertex()
    vtx.setSpecies(ROOT.lMuon)
    selector.addOperator(vtx)

    muons = selector.findOperator('LeptonSelection')
    muons.setRequireTight(False)
    muons.setRequireMedium(True)

    photons = selector.findOperator('PhotonSelection')
    photons.resetSelection()
    photons.addSelection(True, ROOT.PhotonSelection.HOverE)

    return selector

def dimuHfake(sample, rname):
    selector = dimu(sample, rname)

    modHfake(selector)

    return selector

def monomu(sample, rname, selcls = None):
    selector = leptonBase(sample, rname, ROOT.lMuon, selcls = selcls)
    selector.findOperator('LeptonSelection').setN(0, 1)

    mtCut = ROOT.LeptonMt()
    mtCut.setFlavor(ROOT.lMuon)
    mtCut.setMax(160.)
    mtCut.setIgnoreDecision(True)
    selector.addOperator(mtCut)

    return selector

def monomuAllPhoton(sample, rname):
    selector = monomu(sample, rname)

    vtx = ROOT.LeptonVertex()
    vtx.setSpecies(ROOT.lMuon)
    selector.addOperator(vtx)

    muons = selector.findOperator('LeptonSelection')
    muons.setRequireMedium(True)

    photons = selector.findOperator('PhotonSelection')
    photons.resetSelection()
    photons.addSelection(True, ROOT.PhotonSelection.HOverE)

    return selector

def monomuHfake(sample, rname):
    selector = monomu(sample, rname)

    modHfake(selector)

    return selector

def monomuEfake(sample, rname):
    selector = monomu(sample, rname)

    modEfake(selector)

    return selector

def elmu(sample, rname):
    selector = leptonBase(sample, rname, ROOT.lMuon)
    selector.findOperator('LeptonSelection').setN(1, 1)

    if not sample.data:
        addElectronIDSFWeight(sample, selector)

    return selector

def wenu(sample, rname):
    """
    Candidate-like selection but for W->enu, no pixel veto on the photon.
    """

    selector = monophotonBase(sample, rname, selcls = ROOT.PartonSelector)
    selector.setRequiredPdgId(11)

    photonSel = selector.findOperator('PhotonSelection')
    photonSel.setMinPt(15.)
    
    setupPhotonSelection(photonSel, changes = ['-EVeto'])

    return selector

def monoelVertex(sample, rname):
    """
    Monoel-like selection with e or mu, with LeptonVertex
    """

    selector = monoel(sample, rname)

    vtx = ROOT.LeptonVertex()
    vtx.setSpecies(ROOT.lElectron)
    selector.addOperator(vtx)

    return selector

def monomuVertex(sample, rname):
    """
    Monomu-like selection with e or mu, with LeptonVertex
    """

    selector = monomu(sample, rname)

    leptons = selector.findOperator('LeptonSelection')
    leptons.setRequireTight(False)
    leptons.setRequireMedium(True)

    vtx = ROOT.LeptonVertex()
    vtx.setSpecies(ROOT.lMuon)
    selector.addOperator(vtx)

    return selector

def dielVertex(sample, rname):
    """
    Diel-like selection with e or mu, with LeptonVertex
    """

    selector = diel(sample, rname)

    vtx = ROOT.LeptonVertex()
    vtx.setSpecies(ROOT.lElectron)
    selector.addOperator(vtx)

    return selector

def dimuVertex(sample, rname):
    """
    Dimu-like selection with e or mu, with LeptonVertex
    """

    selector = dimu(sample, rname)

    leptons = selector.findOperator('LeptonSelection')
    leptons.setRequireTight(True)
#    leptons.setRequireMedium(True)

    vtx = ROOT.LeptonVertex()
    vtx.setSpecies(ROOT.lMuon)
    selector.addOperator(vtx)

    return selector

def zeeJets(sample, rname):
    """
    Require Z->ee plus at least one high pt jet.
    """

    selector = TagAndProbeBase(sample, rname)
    if sample.data:
        selector.addOperator(ROOT.HLTFilter('HLT_Ele27_WPTight_Gsf'), 0)

    tnp = selector.findOperator('TagAndProbePairZ')
    tnp.setTagSpecies(ROOT.cElectrons)
    tnp.setProbeSpecies(ROOT.cElectrons)

    b2b = ROOT.ZJetBackToBack()
    b2b.setTagAndProbePairZ(selector.findOperator('TagAndProbePairZ'))
    b2b.setMinJetPt(100.)
    b2b.setMinDeltaPhi(3.)
    selector.addOperator(b2b)

    return selector

def zmmJets(sample, rname):
    """
    Require Z->mumu plus at least one high pt jet.
    """

    selector = TagAndProbeBase(sample, rname)
    if sample.data:
        selector.addOperator(ROOT.HLTFilter('HLT_IsoMu20_OR_HLT_IsoTkMu20'), 0)

    tnp = selector.findOperator('TagAndProbePairZ')
    tnp.setTagSpecies(ROOT.cMuons)
    tnp.setProbeSpecies(ROOT.cMuons)

    b2b = ROOT.ZJetBackToBack()
    b2b.setTagAndProbePairZ(selector.findOperator('TagAndProbePairZ'))
    b2b.setMinJetPt(100.)
    b2b.setMinDeltaPhi(3.)
    selector.addOperator(b2b)

    return selector

def tpeg(sample, rname):
    """
    Electron + photon tag & probe run on SinglePhoton dataset.
    """

    selector = tagprobeBase(sample, rname)
    selector.setOutEventType(ROOT.kTPEG)

    if sample.data:
        selector.addOperator(ROOT.HLTFilter('HLT_Photon165_HE10'))

    tp = ROOT.TPLeptonPhoton(ROOT.kTPEG)
    if sample.data:
        tp.setProbeTriggerMatch(True)

    selector.addOperator(tp)

    selector.addOperator(ROOT.TPJetCleaning(ROOT.kTPEG))

    return selector

def tpmg(sample, rname):
    """
    Muon + photon tag & probe run on SinglePhoton dataset.
    """

    selector = tagprobeBase(sample, rname)
    selector.setOutEventType(ROOT.kTPMG)

    if sample.data:
        selector.addOperator(ROOT.HLTFilter('HLT_Photon165_HE10'))

    tp = ROOT.TPLeptonPhoton(ROOT.kTPMG)
    if sample.data:
        tp.setProbeTriggerMatch(True)

    selector.addOperator(tp)

    selector.addOperator(ROOT.TPJetCleaning(ROOT.kTPEG))

    return selector

def tpegLowPt(sample, rname):
    """
    Electron + photon tag & probe run on SingleElectron dataset or MC.
    """

    selector = tagprobeBase(sample, rname)
    selector.setOutEventType(ROOT.kTPEG)

    if sample.data:
        selector.addOperator(ROOT.HLTFilter('HLT_Ele27_WPTight_Gsf'))

    tp = ROOT.TPLeptonPhoton(ROOT.kTPEG)
    tp.setMinProbePt(25.)
    if sample.data:
        tp.setMinTagPt(30.)
        tp.setTagTriggerMatch(True)

    selector.addOperator(tp)

    selector.addOperator(ROOT.TPJetCleaning(ROOT.kTPEG))

    selector.setCanPhotonSkim(False)

    return selector

def tpmgLowPt(sample, rname):
    """
    Muon + photon tag & probe run on SingleMuon dataset or MC.
    """

    selector = tagprobeBase(sample, rname)
    selector.setOutEventType(ROOT.kTPMG)

    if sample.data:
        selector.addOperator(ROOT.HLTFilter('HLT_IsoMu24_OR_HLT_IsoTkMu24'))

    tp = ROOT.TPLeptonPhoton(ROOT.kTPMG)
    tp.setMinProbePt(25.)
    if sample.data:
        tp.setMinTagPt(30.)
        tp.setTagTriggerMatch(True)

    selector.addOperator(tp)

    selector.addOperator(ROOT.TPJetCleaning(ROOT.kTPMG))

    selector.setCanPhotonSkim(False)

    return selector

def tpmmg(sample, rname):
    """
    Dimuon + photon tag & probe.
    """

    selector = tagprobeBase(sample, rname)
    selector.setOutEventType(ROOT.kTPMMG)

    if sample.data:
        selector.addOperator(ROOT.HLTFilter('HLT_IsoMu24_OR_HLT_IsoTkMu24'))

    tp = ROOT.TPLeptonPhoton(ROOT.kTPMMG)
    tp.setMinProbePt(25.)
    tp.setMinTagPt(30.)
    tp.setTagTriggerMatch(True)
    selector.addOperator(tp)

    # for lepton veto efficiency measurement; just write electron and muon sizes
    veto = ROOT.TPLeptonVeto(ROOT.kTPMMG)
    veto.setIgnoreDecision(True)
    selector.addOperator(veto)

    selector.addOperator(ROOT.TPJetCleaning(ROOT.kTPMMG))

    selector.setCanPhotonSkim(False)

    return selector

def tp2e(sample, rname):
    """
    Dielectron T&P.
    """

    selector = tagprobeBase(sample, rname)
    selector.setOutEventType(ROOT.kTP2E)

    if sample.data:
        selector.addOperator(ROOT.HLTFilter('HLT_Ele27_WPTight_Gsf'))

    tp = ROOT.TPDilepton(ROOT.kTP2E)
    tp.setMinProbePt(25.)
    tp.setMinTagPt(35.)
    tp.setTagTriggerMatch(True)
    selector.addOperator(tp)

    selector.addOperator(ROOT.TPJetCleaning(ROOT.kTP2E))

    selector.setCanPhotonSkim(False)

    return selector

def tp2m(sample, rname):
    """
    Dimuon T&P.
    """

    selector = tagprobeBase(sample, rname)
    selector.setOutEventType(ROOT.kTP2M)

    if sample.data:
        selector.addOperator(ROOT.HLTFilter('HLT_IsoMu24_OR_HLT_IsoTkMu24'))

    tp = ROOT.TPDilepton(ROOT.kTP2M)
    tp.setMinProbePt(25.)
    tp.setMinTagPt(30.)
    tp.setTagTriggerMatch(True)
    selector.addOperator(tp)

    selector.addOperator(ROOT.TPJetCleaning(ROOT.kTP2M))

    selector.setCanPhotonSkim(False)

    return selector

def vbfg(sample, rname):
    """
    VBF + photon candidate sample.
    """

    selector = vbfgBase(sample, rname)

    setupPhotonSelection(selector.findOperator('PhotonSelection'))

    if not sample.data:
        addIDSFWeight(sample, selector)

    return selector

def vbfgEfake(sample, rname):
    """
    VBF + photon e->photon fake control sample.
    """

    selector = vbfgBase(sample, rname)

    modEfakeLowPt(selector)

    return selector

def vbfgHfake(sample, rname):
    """
    VBF + photon had->photon fake control sample.
    """

    selector = vbfgBase(sample, rname)

    modHfake(selector)

    return selector

def vbfe(sample, rname):
    """
    VBF + single electron.
    """

    selconf['puweightSource'] = ('puweight_vbf75', datadir + '/pileup_vbf75.root')

    selector = ROOT.EventSelector(rname)
    selector.setCanPhotonSkim(False)

    selector.addOperator(ROOT.HLTFilter('HLT_Ele27_WPTight_Gsf'))

    trig = ROOT.HLTFilter('HLT_Photon75_R9Id90_HE10_Iso40_EBOnly_VBF')
    trig.setIgnoreDecision(True)
    selector.addOperator(trig)

    operators = [
        'MetFilters',
        'LeptonSelection',
        'JetCleaning',
        'DijetSelection',
        'BjetVeto',
        'CopyMet',
        'JetMetDPhi',
        'Met'
    ]

    for op in operators:
        selector.addOperator(getattr(ROOT, op)())

    leptonSel = selector.findOperator('LeptonSelection')
    leptonSel.setN(1, 0)
    leptonSel.setRequireMedium(False)

    dijetSel = selector.findOperator('DijetSelection')
    dijetSel.setMinDEta(0.)
    dijetSel.setMinMjj(0.)

    if not sample.data:
        selector.addOperator(ROOT.ConstantWeight(sample.crosssection / sample.sumw, 'crosssection'))

        addPUWeight(sample, selector)
        addPDFVariation(sample, selector)

    selector.findOperator('BjetVeto').setIgnoreDecision(True)
    selector.findOperator('JetCleaning').setCleanAgainst(ROOT.cTaus, False)
    selector.findOperator('JetMetDPhi').setIgnoreDecision(True)
    selector.findOperator('Met').setIgnoreDecision(True)

    return selector

def vbfm(sample, rname):
    """
    VBF + single muon.
    """

    selconf['puweightSource'] = ('puweight_vbf75', datadir + '/pileup_vbf75.root')

    selector = ROOT.EventSelector(rname)
    selector.setCanPhotonSkim(False)

    selector.addOperator(ROOT.HLTFilter('HLT_IsoMu24_OR_HLT_IsoTkMu24'))

    trig = ROOT.HLTFilter('HLT_Photon75_R9Id90_HE10_Iso40_EBOnly_VBF')
    trig.setIgnoreDecision(True)
    selector.addOperator(trig)

    operators = [
        'MetFilters',
        'LeptonSelection',
        'JetCleaning',
        'DijetSelection',
        'BjetVeto',
        'CopyMet',
        'JetMetDPhi',
        'Met'
    ]

    for op in operators:
        selector.addOperator(getattr(ROOT, op)())

    leptonSel = selector.findOperator('LeptonSelection')
    leptonSel.setN(0, 1)
    leptonSel.setRequireMedium(False)

    dijetSel = selector.findOperator('DijetSelection')
    dijetSel.setMinDEta(0.)
    dijetSel.setMinMjj(0.)

    if not sample.data:
        selector.addOperator(ROOT.ConstantWeight(sample.crosssection / sample.sumw, 'crosssection'))

        addPUWeight(sample, selector)
        addPDFVariation(sample, selector)

    selector.findOperator('BjetVeto').setIgnoreDecision(True)
    selector.findOperator('JetCleaning').setCleanAgainst(ROOT.cTaus, False)
    selector.findOperator('JetMetDPhi').setIgnoreDecision(True)
    selector.findOperator('Met').setIgnoreDecision(True)

    return selector

######################
# SELECTOR MODIFIERS #
######################

def addPUWeight(sample, selector):
    pudirName, pufileName = selconf['puweightSource']

    pudir = ROOT.gROOT.GetDirectory(pudirName)

    if not pudir:
        pudir = ROOT.gROOT.mkdir(pudirName)
        logger.info('Loading PU weights from %s', pufileName)
        f = ROOT.TFile.Open(pufileName)
        for k in f.GetListOfKeys():
            if k.GetName().startswith('puweight_'):
                logger.info('Saving PU weights %s into ROOT/%s', k.GetName(), pudirName)
                pudir.cd()
                obj = k.ReadObj().Clone(k.GetName().replace('puweight_', ''))
                _garbage.append(obj)
        
        f.Close()

    for hist in pudir.GetList():
        if hist.GetName() in sample.fullname:
            logger.info('Using PU weights %s/%s for %s', pudirName, hist.GetName(), sample.name)
            selector.addOperator(ROOT.PUWeight(hist))
            break
    else:
        raise RuntimeError('Pileup profile for ' + sample.name + ' not defined')

def addIDSFWeight(sample, selector):
    logger.info('Adding photon ID scale factor (Spring16)')

    idsf = ROOT.IDSFWeight(ROOT.cPhotons, 'photonSF')
    idsf.addFactor(getFromFile(datadir + '/photon_id_sf16.root', 'EGamma_SF2D', newname = 'photonSF'))
    idsf.setVariable(ROOT.IDSFWeight.kEta, ROOT.IDSFWeight.kPt)
    selector.addOperator(idsf)
    selector.addOperator(ROOT.ConstantWeight(0.991, 'extraSF'))

def addElectronIDSFWeight(sample, selector):
    logger.info('Adding electron ID scale factor (ICHEP)')

    electronTightSF = getFromFile(datadir + '/egamma_electron_tight_SF_ichep.root', 'EGamma_SF2D', 'electronTightSF') # x: sc eta, y: pt
    electronTrackSF = getFromFile(datadir + '/egamma_gsf_tracking_SF_ichep.root', 'EGamma_SF2D', 'electronTrackSF') # x: sc eta, y: npv

    idsf = ROOT.IDSFWeight(ROOT.cElectrons, 'ElectronSF')
    idsf.addFactor(electronTightSF)
    idsf.setVariable(ROOT.IDSFWeight.kEta, ROOT.IDSFWeight.kPt)
    selector.addOperator(idsf)

    track = ROOT.IDSFWeight(ROOT.cElectrons, 'GsfTrackSF')
    track.addFactor(electronTrackSF)
    track.setVariable(ROOT.IDSFWeight.kEta, ROOT.IDSFWeight.kNpv)
    selector.addOperator(track)

def addMuonIDSFWeight(sample, selector):
    logger.info('Adding muon ID scale factor (ICHEP)')

    muonTightSF = getFromFile(datadir + '/scaleFactor_muon_tightid_12p9.root', 'scaleFactor_muon_tightid_RooCMSShape') # x: abs eta, y: pt
    muonTrackSF = getFromFile(datadir + '/muonpog_muon_tracking_SF_ichep.root', 'htrack2') # x: npv

    idsf = ROOT.IDSFWeight(ROOT.cMuons, 'MuonSF')
    idsf.addFactor(muonTightSF)
    idsf.setVariable(ROOT.IDSFWeight.kAbsEta, ROOT.IDSFWeight.kPt)
    selector.addOperator(idsf)

    track = ROOT.IDSFWeight(ROOT.cMuons, 'MuonTrackSF')
    track.addFactor(muonTrackSF)
    track.setVariable(ROOT.IDSFWeight.kNpv)
    selector.addOperator(track)

def addPDFVariation(sample, selector):
    if 'amcatnlo' in sample.fullname or 'madgraph' in sample.fullname: # ouh la la..
        logger.info('Adding PDF variation for %s', sample.name)
        selector.addOperator(ROOT.NNPDFVariation())

def addKfactor(sample, selector):
    """
    Apply the k-factor corrections.
    """

    sname = sample.name.replace('gj04', 'gj')

    # temporarily don't apply QCD k-factor until we redrive for nlo samples
    corr = getFromFile(datadir + '/kfactor.root', sname, newname = sname + '_kfactor')
    if not corr:
        raise RuntimeError('kfactor not found for ' + sample.name)

    qcd = ROOT.PhotonPtWeight(corr, 'QCDCorrection')
    if 'gj-' in sname:
        qcd.setPhotonType(ROOT.PhotonPtWeight.kPostShower)
    else:
        qcd.setPhotonType(ROOT.PhotonPtWeight.kParton)

    for variation in ['renUp', 'renDown', 'facUp', 'facDown', 'scaleUp', 'scaleDown']:
        vcorr = getFromFile(datadir + '/kfactor.root', sname + '_' + variation)
        if vcorr:
            logger.info('applying qcd var %s %s', variation, sample.name)
            qcd.addVariation('qcd' + variation, vcorr)

    selector.addOperator(qcd)

    corr = getFromFile(datadir + '/ewk_corr.root', sname, newname = sname + '_ewkcorr')
    if corr:
        logger.info('applying ewk %s', sample.name)
        ewk = ROOT.PhotonPtWeight(corr, 'EWKNLOCorrection')
        ewk.setPhotonType(ROOT.PhotonPtWeight.kParton)

        for variation in ['Up', 'Down']:
            vcorr = getFromFile(datadir + '/ewk_corr.root', sname + '_' + variation)
            if vcorr:
                logger.info('applying ewk var %s %s', variation, sample.name)
                ewk.addVariation('ewk' + variation, vcorr)

        selector.addOperator(ewk)

def addGenPhotonVeto(sample, selector):
    veto = ROOT.GenPhotonVeto()
    veto.setMinPt(130.)
    veto.setMinPartonDR(0.5)

    selector.addOperator(veto, 0)

def addPhotonRecoil(sample, selector):
    """Wrapper for diphoton samples to turn them into photon+dark photon
    samples by 'removing' one of the photons and adding it to the MET."""
    selector.addOperator(ROOT.PhotonRecoil())

def setSampleId(sample, selector):
    """Set the sample ID on TagAndProbeSelector."""

    if sample.data:
        selector.setSampleId(0)
    elif sample.name.startswith('dy'):
        selector.setSampleId(1)
    elif sample.name.startswith('tt'):
        selector.setSampleId(2)
    elif sample.name.startswith('wg'):
        selector.setSampleId(3)
    elif sample.name.startswith('gg'):
        selector.setSampleId(4)
    else:
        selector.setSampleId(99)

def modHfake(selector):
    """Append PhotonPtWeight with hadProxyWeight and set up the photon selections."""

    filename, suffix = selconf['hadronTFactorSource']

    hadproxyWeight = getFromFile(filename, 'tfactNom', 'tfactNom' + suffix)

    weight = ROOT.PhotonPtWeight(hadproxyWeight, 'hadProxyWeight')
    weight.setPhotonType(ROOT.PhotonPtWeight.kReco)
    selector.addOperator(weight)

    photonSel = selector.findOperator('PhotonSelection')

    setupPhotonSelection(photonSel, changes = selconf['hadronProxyDef'])
    setupPhotonSelection(photonSel, veto = True)

def modEfake(selector, selections = []):
    """Append PhotonPtWeight with eproxyWeight and set up the photon selections."""

    eproxyWeight = getFromFile(datadir + '/efake_data_ptalt.root', 'frate')

    weight = ROOT.PhotonPtWeight(eproxyWeight, 'egfakerate')
    weight.useErrors(True) # use errors of eleproxyWeight as syst. variation
    selector.addOperator(weight)

    photonSel = selector.findOperator('PhotonSelection')

    setupPhotonSelection(photonSel, changes = selections + ['-EVeto', '!CSafeVeto'])
    setupPhotonSelection(photonSel, veto = True)

def modEfakeLowPt(selector):
    """Append PhotonPtWeight and set up the photon selections."""

    eproxyWeight = ROOT.TF1('eproxyWeight', '0.0292 + 0.131 / (x - 12.8)', 0., 6500.)

    weight = ROOT.PhotonPtWeight(eproxyWeight, 'egfakerate')
    selector.addOperator(weight)

    photonSel = selector.findOperator('PhotonSelection')

    setupPhotonSelection(photonSel, changes = ['-EVeto', '!CSafeVeto'])
    setupPhotonSelection(photonSel, veto = True)


#######################
# MODIFIER GENERATORS #
#######################

def ptTruncator(minimum = 0., maximum = -1.):
    def addPtCut(sample, selector):
        truncator = ROOT.PhotonPtTruncator()
        truncator.setPtMin(minimum)
        if maximum > 0.:
            truncator.setPtMax(maximum)

        selector.addOperator(truncator, 0)

    return addPtCut

def htTruncator(minimum = 0., maximum = -1.):
    def addHtCut(sample, selector):
        truncator = ROOT.HtTruncator()
        truncator.setHtMin(minimum)
        if maximum > 0.:
            truncator.setHtMax(maximum)

        selector.addOperator(truncator, 0)

    return addHtCut


if needHelp:
    sys.argv.append('--help')
