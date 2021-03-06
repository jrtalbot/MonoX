#! /usr/bin/python

from CrombieTools.AnalysisTools.LimitTreeMaker import *

ltm = newLimitTreeMaker()

ltm.SetTreeName('events')
ltm.AddKeepBranch('met')
ltm.AddKeepBranch('genBos_pt')
ltm.AddKeepBranch('jet1Pt')
ltm.AddKeepBranch('n_cleanedjets', True)
ltm.AddKeepBranch('dPhi_j1j2')
ltm.AddKeepBranch('mt')
ltm.SetAllHistName('htotal')
ltm.SetOutputWeightBranch('scaleMC_w')
ltm.SetReportFrequency(20)

SetupFromEnv(ltm)
ltm.AddFile('data',str(ltm.GetInDirectory()) + 'monojet_Data.root',-1)

if __name__ == '__main__':
    ltm.SetOutFileName('MonoJetIncLimitsTrees.root')
    SetCuts(ltm,'monoJet_inc')
    ltm.MakeTrees()
