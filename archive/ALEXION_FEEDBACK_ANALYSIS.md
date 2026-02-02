# Alexion WD-204 Feedback Analysis

## Feedback Validity Assessment

### Issue 1: Two Arms vs Within-Subject Titration ✅ VALID

**Problem:** The Alexion protocol has dose titration (15mg → 30mg on Day 29) but is being modeled as two parallel arms.

**Evidence from USDM output:**
```json
"arms": [
  {"name": "ALXN1840 15 mg/day", "description": "...for a treatment period of approximately 28 days"},
  {"name": "ALXN1840 30 mg/day", "description": "Following the 15 mg/day period, participants are titrated up to 30 mg/day on Day 29"}
]
```

**Root Cause:** 
1. The LLM prompt in `studydesign/prompts.py` explicitly shows an example with two separate arms for different doses
2. No post-processing to detect titration language ("titrated up", "following", "after Day X")
3. Study cells created as arms × epochs (parallel), not sequential dose epochs

**Fix Required:** 
- Update prompt to distinguish between parallel arms vs sequential dose epochs
- Add titration detection in post-processing
- Model as: 1 arm with dose-epoch sub-phases + required traversal constraint

---

### Issue 2: Daily Repetition Not Machine-Enforced ✅ VALID

**Problem:** Activities like meals, urine, feces are scheduled across multi-day encounter ranges but don't encode "every day" semantics.

**Root Cause:**
- Repetition patterns extracted as library objects but not bound to specific activity instances
- No detection of "Days -4 to -1" = "daily for 4 days"
- Missing `repetition.type = DAILY` bound to ScheduledActivityInstance

**Fix Required:**
- Enhance repetition binding (builds on Fix C from previous work)
- Detect multi-day ranges and infer daily repetition
- Add `expectedOccurrences` count

---

### Issue 3: Analysis Windows Not Explicit ✅ VALID

**Problem:** Endpoints reference "baseline Days −4 through −1", "accumulation", "steady-state" but these aren't computable phases.

**Root Cause:**
- Visit windows extracted but not linked to analysis phases
- No "AnalysisWindow" concept separate from visit scheduling
- Endpoint algorithms don't reference window IDs

**Fix Required:**
- Add `AnalysisWindow` schema type with:
  - windowType (baseline, accumulation, steady_state, treatment)
  - startDay, endDay relative to anchor
  - linkedEndpointIds
- Emit as extension attribute

---

### Issue 4: Daily Anchor for 24-Hour Collections ✅ VALID

**Problem:** For studies with daily collections (urine, feces), need 24-hour boundary definition.

**Root Cause:**
- Time anchors focused on minute-level (PK/PD) not day boundaries
- No "collection day" anchor type

**Fix Required:**
- Add `COLLECTION_DAY` anchor type
- Define 24-hour window (e.g., "07:00 to 07:00 next day")
- Bind to daily collection activities

---

## Implementation Plan

### Priority Order (Alexion-focused)

1. **Fix Prompt & Titration Detection** - Highest impact
   - Update `studydesign/prompts.py` to distinguish titration
   - Add post-processing in `studydesign/extractor.py`
   - Create titration traversal constraint

2. **Daily Repetition Binding**
   - Enhance `repetition_extractor.py` with day-range detection
   - Bind to activity instances via ActivityBinding

3. **Analysis Windows**
   - Add `AnalysisWindow` to `execution/schema.py`
   - Create `analysis_window_extractor.py`
   - Link to endpoints

4. **Daily Anchor**
   - Add `COLLECTION_DAY` to AnchorType enum
   - Detect 24-hour collection patterns

---

## Test Cases

```python
# Test 1: Titration as sequential epochs
def test_titration_single_arm():
    """30 mg dose should not appear as separate arm"""
    assert len(usdm['studyDesigns'][0]['arms']) == 1
    epochs = [e for e in usdm['studyDesigns'][0]['epochs'] if 'mg' in e.get('name', '')]
    assert any('15' in e['name'] for e in epochs)
    assert any('30' in e['name'] for e in epochs)

# Test 2: Required traversal for titration
def test_titration_traversal():
    """Must pass through 15mg before 30mg"""
    constraints = get_extension('x-executionModel-traversalConstraints')
    seq = constraints[0]['requiredSequence']
    assert seq.index('15mg_epoch') < seq.index('30mg_epoch')

# Test 3: Daily repetition bound
def test_daily_collection_repetition():
    """Feces collection should have DAILY repetition"""
    bindings = get_extension('x-executionModel-activityBindings')
    feces = next(b for b in bindings if 'feces' in b['activityName'].lower())
    assert feces['repetitionId'] is not None
    
# Test 4: Analysis windows exist
def test_analysis_windows():
    """Baseline window should exist"""
    windows = get_extension('x-executionModel-analysisWindows')
    baseline = next(w for w in windows if w['windowType'] == 'baseline')
    assert baseline['startDay'] == -4
    assert baseline['endDay'] == -1
```
