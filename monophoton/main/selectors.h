#ifndef selectors_h
#define selectors_h

#include "operators.h"

#include "TTree.h"
#include "TFile.h"
#include "TString.h"
#include "TF1.h"

#include <vector>
#include <chrono>

typedef std::chrono::high_resolution_clock Clock;

class EventSelectorBase {
public:
  EventSelectorBase(char const* name) : name_(name) {}
  virtual ~EventSelectorBase() {}

  void addOperator(Operator*, unsigned idx = -1);
  unsigned size() const { return operators_.size(); }
  Operator* getOperator(unsigned iO) const { return operators_.at(iO); }
  Operator* findOperator(char const* name) const;

  void initialize(char const* outputPath, panda::EventBase& event, bool isMC);
  void finalize();
  virtual void selectEvent(panda::EventBase&) = 0;

  TString const& name() const { return name_; }

  void setUseTimers(bool b) { useTimers_ = b; }

protected:
  virtual void bookOutEvent_(panda::EventBase& event, bool isMC) = 0;
  virtual void setupSkim_(panda::EventBase& event, bool isMC) {}
  virtual void addOutput_(TFile*& outputFile) {}

  TString name_;
  TTree* skimOut_{0};
  TTree* cutsOut_{0};

  std::vector<Operator*> operators_;

  double inWeight_{1.};

  bool useTimers_{false};
  std::vector<Clock::duration> timers_;
};

class EventSelector : public EventSelectorBase {
public:
  EventSelector(char const* name) : EventSelectorBase(name) {}
  ~EventSelector() {}

  void selectEvent(panda::EventBase&) override;

  void setPartialBlinding(unsigned prescale, unsigned minRun = 0) { blindPrescale_ = prescale; blindMinRun_ = minRun; }

 protected:
  void setupSkim_(panda::EventBase& event, bool isMC) override;

  panda::EventMonophoton outEvent_;

  unsigned blindPrescale_{1};
  unsigned blindMinRun_{0};
};

class ZeeEventSelector : public EventSelector {
  // Special event selector for Zee events where one input event can yield multiple output events
 public:
  ZeeEventSelector(char const* name);
  ~ZeeEventSelector();

  void selectEvent(panda::EventBase&) override;

  class EEPairSelection : public PhotonSelection {
  public:
    EEPairSelection(char const* name = "EEPairSelection");
    std::vector<std::pair<unsigned, unsigned>> const& getEEPairs() const { return eePairs_; }

  protected:
    bool pass(panda::EventMonophoton const&, panda::EventMonophoton&) override;
    
    std::vector<std::pair<unsigned, unsigned>> eePairs_;
  };

 protected:
  std::vector<Operator*>::iterator eePairSel_;
};

class WlnuSelector : public EventSelector {
  // Special event selector that considers only non-electron decays of W
 public:
  WlnuSelector(char const* name) : EventSelector(name) {}

  void selectEvent(panda::EventBase&) override;
};

class WenuSelector : public EventSelector {
  // Special event selector that considers only electron decays of W
 public:
  WenuSelector(char const* name) : EventSelector(name) {}

  void selectEvent(panda::EventBase&) override;
};

class NormalizingSelector : public EventSelector {
  // Special event selector that normalizes the output to a given total sumW at the end
 public:
  NormalizingSelector(char const* name) : EventSelector(name) {}
  ~NormalizingSelector() {}

  void setNormalization(double norm, char const* normCut) { norm_ = norm; normCut_ = normCut; }

 protected:
  void addOutput_(TFile*& outputFile) override;

  double norm_{1.};
  TString normCut_{""};
};

class SmearingSelector : public EventSelector {
  // Generates nSample events per input event with smeared MET according to a model.
  // Technically there are statistics issues here, but we'll ignore it for now.
 public:
  SmearingSelector(char const* name) : EventSelector(name) {}
  ~SmearingSelector() {}

  void selectEvent(panda::EventBase&) override;

  void setNSamples(unsigned n) { nSamples_ = n; }
  void setFunction(TF1* func) { func_ = func; }

 protected:
  unsigned nSamples_{1};
  TF1* func_{0};
};

#endif
