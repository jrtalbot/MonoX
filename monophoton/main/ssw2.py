#!/usr/bin/env python

import sys
import os

thisdir = os.path.dirname(os.path.realpath(__file__))
basedir = os.path.dirname(thisdir)
sys.path.append(basedir)
from datasets import allsamples
import main.selectors as selectors
import main.plotconfig as plotconfig
import config
from subprocess import Popen, PIPE
import shutil
from glob import glob

defaults = {
    'monoph': selectors.candidate,
    'signalRaw': selectors.signalRaw,
    'efake': selectors.eleProxy,
    'hfake': selectors.hadProxy,
    'hfakeUp': selectors.hadProxyUp,
    'hfakeDown': selectors.hadProxyDown,
    'purity': selectors.purity,
    'purityUp': selectors.purityUp,
    'purityDown': selectors.purityDown,
    'lowmt': selectors.lowmt,
    'lowmtEfake': selectors.lowmtEleProxy,
    'gjets': selectors.gjets,
    'dimu': selectors.dimuon,
    'monomu': selectors.monomuon,
    'monomuHfake': selectors.monomuonHadProxy,
    'diel': selectors.dielectron,
    'monoel': selectors.monoelectron,
    'monoelHfake': selectors.monoelectronHadProxy,
    'elmu': selectors.oppflavor,
    'eefake': selectors.zee,
    'wenu': selectors.wenuall
}

data_15 = []
data_sph = ['monoph', 'efake', 'hfake', 'hfakeUp', 'hfakeDown', 'purity', 'purityUp', 'purityDown', 'lowmt', 'lowmtEfake', 'gjets']
data_smu = ['dimu', 'monomu', 'monomuHfake', 'elmu']
data_sel = ['diel', 'monoel', 'monoelHfake', 'eefake']
mc_cand = ['monoph']
mc_qcd = ['hfake', 'hfakeUp', 'hfakeDown', 'purity', 'purityUp', 'purityDown', 'gjets'] 
mc_sig = ['monoph', 'signalRaw']
mc_lep = ['monomu', 'monoel']
mc_dilep = ['dimu', 'diel', 'elmu']
mc_vgcand = [(region, selectors.kfactor(defaults[region])) for region in mc_cand]
mc_vglep = [(region, selectors.kfactor(defaults[region])) for region in mc_lep]
mc_vgdilep = [(region, selectors.kfactor(defaults[region])) for region in mc_dilep]
#mc_gj = [('raw', selectors.kfactor(defaults['monoph'])), ('monoph', selectors.kfactor(selectors.gjSmeared)), ('purity', selectors.kfactor(selectors.purity))]
mc_gj = [('raw', selectors.kfactor(defaults['monoph'])), ('monoph', selectors.kfactor(defaults['monoph'])), ('purity', selectors.kfactor(selectors.purity))]
mc_wlnu = [(region, selectors.wlnu(defaults[region])) for region in mc_cand] + ['wenu']
mc_lowmt = ['lowmt']
mc_vglowmt = [(region, selectors.kfactor(defaults[region])) for region in mc_lowmt]

sphLumi = allsamples['sph-16b2'].lumi + allsamples['sph-16b2s'].lumi
haloNorms = [ 8.7 * allsamples[sph].lumi / sphLumi for sph in ['sph-16b2', 'sph-16b2s'] ]

selectors = {
    # Data 2016
    'sph-16b2-n': data_sph,
    'sph-16c2-n': data_sph,
    'sph-16d2-n': data_sph,
    'sph-16b2': data_sph + [('halo', selectors.haloMIP(haloNorms[0]))
                            ,('haloUp', selectors.haloCSC(haloNorms[0]))
                            ,('haloDown', selectors.haloSieie(haloNorms[0]))
                             ],
    'sph-16b2s': data_sph + [('halo', selectors.haloMIP(4*haloNorms[1]))
                            ,('haloUp', selectors.haloCSC(4*haloNorms[1]))
                            ,('haloDown', selectors.haloSieie(4*haloNorms[1]))
                             ],
    'sph-16c2': data_sph,
    # 'sph-16d2': data_sph,
    'smu-16b2': data_smu,
    'smu-16c2': data_smu,
    # 'smu-16d2': data_smu,
    'sel-16b2': data_sel,
    'sel-16c2': data_sel,
    # 'sel-16d2': data_sel,
    # Data 2015 rereco
    'sph-15d': data_15,
    'smu-15d': data_15,
    'sel-15d': data_15,
    # Data 2015 prompt reco
    'sph-d3': data_15,
    'sph-d4': data_15,
    'smu-d3': data_15,
    'smu-d4': data_15,
    'sel-d3': data_15,
    'sel-d4': data_15,
    # MC for signal region
    'znng-130': mc_vgcand + mc_vglowmt,
    'wnlg-130': mc_vgcand + mc_vglep + mc_vglowmt,
    'zg': mc_cand + mc_lep + mc_dilep + mc_lowmt,
    # 'wg': mc_cand + mc_lep + mc_lowmt,
    'wglo': mc_cand + mc_lep + mc_lowmt,
    'gj-40': mc_gj + mc_qcd + mc_lowmt,
    'gj-100': mc_gj + mc_qcd + mc_lowmt,
    'gj-200': mc_gj + mc_qcd + mc_lowmt,
    'gj-400': mc_gj + mc_qcd + mc_lowmt,
    'gj-600': mc_gj + mc_qcd + mc_lowmt,
    'gj04-40': mc_gj + mc_qcd + mc_lowmt,
    'gj04-100': mc_gj + mc_qcd + mc_lowmt,
    'gj04-200': mc_gj + mc_qcd + mc_lowmt,
    'gj04-400': mc_gj + mc_qcd + mc_lowmt,
    'gj04-600': mc_gj + mc_qcd + mc_lowmt,
    'gg-80': mc_cand + mc_qcd + mc_lowmt,
    'tg': mc_cand + mc_lep + mc_lowmt, 
    'ttg': mc_cand + mc_lep + mc_dilep + mc_lowmt,
    'tg': mc_cand + mc_lep,
    'wwg': mc_cand + mc_lep + mc_dilep + mc_lowmt,
    'ww': mc_cand + mc_lep + mc_dilep + mc_lowmt,
    'wz': mc_cand + mc_lep + mc_dilep + mc_lowmt,
    'zz': mc_cand + mc_lep + mc_dilep + mc_lowmt,
    'tt': mc_cand + mc_lep + mc_dilep,
    # 'zllg-130': mc_vgcand + mc_vglep + mc_vgdilep,
    'wlnu': mc_wlnu + mc_lep,
    'wlnu-100': mc_wlnu + mc_lep,
    'wlnu-200': mc_wlnu + mc_lep, 
    'wlnu-400': mc_wlnu + mc_lep, 
    # 'wlnu-600': mc_wlnu + mc_lep, 
    'wlnu-800': mc_wlnu + mc_lep,
    'wlnu-1200': mc_wlnu + mc_lep,
    'wlnu-2500': mc_wlnu + mc_lep,
    'dy-50': mc_cand + mc_lep + mc_dilep,
    'dy-50-100': mc_cand + mc_lep + mc_dilep,
    'dy-50-200': mc_cand + mc_lep + mc_dilep,
    'dy-50-400': mc_cand + mc_lep + mc_dilep,
    'dy-50-600': mc_cand + mc_lep + mc_dilep,
    'qcd-200': mc_cand + mc_qcd,
    'qcd-300': mc_cand + mc_qcd,
    'qcd-500': mc_cand + mc_qcd,
    'qcd-700': mc_cand + mc_qcd,
    'qcd-1000': mc_cand + mc_qcd,
    'qcd-1500': mc_cand + mc_qcd,
    'qcd-2000': mc_cand + mc_qcd
}

# all the rest are mc_sig
for sname in allsamples.names():
    if sname not in selectors:
        selectors[sname] = mc_sig

def processSampleNames(_inputNames, _selectorKeys, _plotConfig = ''):
    snames = []

    if _plotConfig:
        # if a plot config is specified, use the samples for that
        snames = plotconfig.getConfig(_plotConfig).samples()

    else:
        snames = _inputNames

    # handle special group names
    if 'all' in snames:
        snames.remove('all')
        snames = _selectorKeys
    elif 'dmfs' in snames:
        snames.remove('dmfs')
        snames += [key for key in _selectorKeys if key.startswith('dm') and key[3:5] == 'fs']
    elif 'dm' in snames:
        snames.remove('dm')
        snames += [key for key in _selectorKeys if key.startswith('dm')]
    elif 'add' in snames:
        snames.remove('add')
        snames += [key for key in _selectorKeys if key.startswith('add')]
    if 'fs' in snames:
        snames.remove('fs')
        snames += [key for key in _selectorKeys if 'fs' in key]

    # filter out empty samples
    tmp = [name for name in snames if allsamples[name].sumw != 0.]
    snames = tmp

    return snames

if __name__ == '__main__':

    from argparse import ArgumentParser
    
    argParser = ArgumentParser(description = 'Plot and count')
    argParser.add_argument('snames', metavar = 'SAMPLE', nargs = '*', help = 'Sample names to skim.')
    argParser.add_argument('--list', '-L', action = 'store_true', dest = 'list', help = 'List of samples.')
    argParser.add_argument('--plot-config', '-p', metavar = 'PLOTCONFIG', dest = 'plotConfig', default = '', help = 'Run on samples used in PLOTCONFIG.')
    argParser.add_argument('--nero-input', '-n', action = 'store_true', dest = 'neroInput', help = 'Specify that input is Nero instead of simpletree.')
    argParser.add_argument('--nentries', '-N', metavar = 'N', dest = 'nentries', type = int, default = -1, help = 'Maximum number of entries.')
    argParser.add_argument('--files', '-f', metavar = 'nStart nEnd', dest = 'files', nargs = 2, type = int, default = [], help = 'Range of files to run on.')
    
    args = argParser.parse_args()
    sys.argv = []

    import ROOT

    ROOT.gSystem.Load(config.libsimpletree)
    ROOT.gSystem.AddIncludePath('-I' + config.dataformats + '/interface')
    ROOT.gSystem.AddIncludePath('-I' + config.dataformats + '/tools')

    if args.neroInput:
        ROOT.gSystem.Load(config.libnerocore)
    ROOT.gSystem.AddIncludePath('-I' + config.nerocorepath + '/interface')

    ROOT.gROOT.LoadMacro(thisdir + '/Skimmer.cc+')

    snames = processSampleNames(args.snames, selectors.keys(), args.plotConfig)

    if args.list:
        print ' '.join(sorted(snames))
        # for sname in sorted(snames):
            # print sname
        sys.exit(0)
    
    skimmer = ROOT.Skimmer()
    
    if not os.path.exists(config.skimDir):
        os.makedirs(config.skimDir)

    if args.files:
        nStart = args.files[0]
        nEnd = args.files[1]
    else:
        nStart = 1000000
        nEnd = -1

    for sname in snames:
        sample = allsamples[sname]
        print 'Starting sample %s (%d/%d)' % (sname, snames.index(sname) + 1, len(snames))
    
        skimmer.reset()
    
        if args.neroInput:
            tree = ROOT.TChain('nero/events')
        else:
            tree = ROOT.TChain('events')

        if os.path.exists(config.photonSkimDir + '/' + sname + '.root'):
            print 'Reading', sname, 'from', config.photonSkimDir
            tree.Add(config.photonSkimDir + '/' + sname + '.root')

        else:
            if sample.data:
                sourceDir = config.dataNtuplesDir + sample.book + '/' + sample.fullname
            else:
                sourceDir = config.ntuplesDir + sample.book + '/' + sample.fullname

            print 'Reading', sname, 'from', sourceDir

            if args.neroInput:
                lsCmd = ['/afs/cern.ch/project/eos/installation/0.3.84-aquamarine/bin/eos.select', 'ls', sourceDir + '/*.root']
                listFiles = Popen(lsCmd, stdout=PIPE, stderr=PIPE)
                
                # (lout, lerr) = listFiles.communicate()
                # print lout, '\n'
                # print lerr, '\n'
                
                filesList = listFiles.stdout
                pathPrefix = 'root:://eoscms/'
            else:
                filesList = sorted(glob(sourceDir + '/*.root'))
                pathPrefix = ''
                
            for iF, File in enumerate(filesList):
                if iF < nStart:
                    continue
                if iF > nEnd:
                    break
                File = File.strip(' \n')
                print File
                
                if args.neroInput:
                    tree.Add(pathPrefix + sourceDir + '/' + File)
                else:
                    tree.Add(File)

        print tree.GetEntries()
        if tree.GetEntries() == 0:
            print 'Tree has no entries. Skipping.'
            continue

        selnames = []
        for selconf in selectors[sname]:
            if type(selconf) == str:
                rname = selconf
                gen = defaults[rname]
            else:
                rname, gen = selconf

            selnames.append(rname)
            selector = gen(sample, rname)
            skimmer.addSelector(selector)

        if nEnd > 0:
            sname = sname + '_' + str(nStart) + '-' + str(nEnd)
            tmpDir = '/tmp/ballen'
            if not os.path.exists(tmpDir):
                os.makedirs(tmpDir)
            skimmer.run(tree, tmpDir, sname, args.nentries, args.neroInput)
            for selname in selnames:
                if os.path.exists(config.skimDir + '/' + sname + '_' + selname + '.root'):
                    os.remove(config.skimDir + '/' + sname + '_' + selname + '.root')
                shutil.move(tmpDir + '/' + sname + '_' + selname + '.root', config.skimDir)
        else:
            skimmer.run(tree, config.skimDir, sname, args.nentries, args.neroInput)
