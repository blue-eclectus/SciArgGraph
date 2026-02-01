# Scientific Argument Graph Ontology

A lean ontology for representing scientific arguments as directed graphs, designed for clear Bayesian network conversion.

## Design Principles

1. **Propositions are central** — All claims are truth-valued
2. **Reified links** — Support/undermine relationships are first-class nodes, enabling joint premises and undercutting
3. **Flexible composition** — How multiple links combine is a CPT generation concern, not baked into the ontology
4. **Custom CPTs as override** — Parameters provide defaults; explicit CPTs take precedence

---

## Structural Constraints

### Acyclicity Requirement

The argument graph must be a directed acyclic graph (DAG). This is required for Bayesian network conversion—cyclic dependencies have no consistent probabilistic interpretation.

**Validation:** Implementations should check for cycles before BN conversion and report diagnostic information identifying the cycle.

### Resolving Apparent Cycles

Scientific prose sometimes suggests circular support ("A supports B, and B supports A"). These typically reflect one of several patterns that can be modeled acyclically:

**Evidential vs. explanatory relations:**
"The data supports the theory" (evidential) and "the theory explains the data" (explanatory) are different relations. Only evidential support belongs in the argument graph. If extraction produces both directions, retain only the evidential edge (typically: observations → claims, not claims → observations).

**Mutual consistency vs. mutual support:**
"A and B are consistent with each other" does not mean they support each other. Consistency is the *absence* of contradiction, not the presence of bidirectional support. If A and B genuinely reinforce each other, consider whether they share a common cause:
```
# Instead of: A ↔ B (cyclic)
# Model as:  H → A and H → B (common hypothesis)
#            with A and B as observable consequences
```
---

## Node Types

### Proposition

The base node type representing any truth-valued claim.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique identifier |
| `content` | string | yes | Natural language statement |
| `base_rate` | [0,1] | no | P(true \| no active incoming links); default 0.5 |
| `cpt` | CPT | no | Custom CPT (overrides default generation) |
| `textual_basis` | TextualBasis | no | Source text grounding this element (see Text Grounding) |
| `duplicate_of` | string | no | ID of canonical node this duplicates (for tree representation of DAGs) |
| `explicitness` | string | no | How directly stated: `explicit`, `implicit`, or `inferred` |
| `auxiliary` | boolean | no | True if this proposition serves as a supporting premise in a joint link; default false. See below. |

**Auxiliary propositions:**

An auxiliary proposition is one that completes a joint inference—typically background knowledge or an unstated assumption needed to bridge from evidence to conclusion. For example, in "The study found aerosols contain virus" → "Aerosol transmission occurs," the inference implicitly relies on "Aerosolized virus remains infectious." This bridging claim is an auxiliary.

Auxiliaries are:
- Marked with `auxiliary: true` in the schema
- Visualized with dashed edges connecting them to their joint link
- Often (but not always) marked as `explicitness: inferred` since they weren't stated in the source text

The `auxiliary` field is purely for visualization and documentation—it has no effect on Bayesian network conversion. Auxiliaries are structurally just propositions participating in multi-source links.

### Conclusion

The final claim of an argument thread. Like Proposition, but represents the ultimate point being argued for. Conclusions should not have outgoing Links (they don't support other claims). Useful for visualization and argument individuation.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique identifier |
| `content` | string | yes | Natural language statement of the conclusion |
| `base_rate` | [0,1] | no | P(true \| no active incoming links); default 0.5 |
| `argument_id` | string | no | Identifier linking this conclusion to its argument thread |
| `cpt` | CPT | no | Custom CPT (overrides default generation) |
| `textual_basis` | TextualBasis | no | Source text grounding this element (see Text Grounding) |
| `duplicate_of` | string | no | ID of canonical node this duplicates (for tree representation of DAGs) |

**When to use Conclusion vs Proposition:**
- Conclusion nodes mark the terminal claims of argument threads—what the argument is ultimately trying to establish
- Proposition nodes are intermediate claims or assumptions that support conclusions
- A graph can have multiple Conclusions representing related claims being argued together
- Conclusions have no outgoing Links; if a claim supports other claims, it's better modeled as a Proposition

### Datum

Extends Proposition. Represents a reported finding—what was observed or measured, not necessarily ground truth.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique identifier |
| `content` | string | yes | Natural language statement of what was reported |
| `base_rate` | [0,1] | no | Prior probability that the reported finding is accurate; reflects source reliability. Default 0.5 |
| `source` | string | yes | Provenance (citation, dataset, observation method) |
| `cpt` | CPT | no | Custom CPT (overrides default generation) |
| `textual_basis` | TextualBasis | no | Source text grounding this element (see Text Grounding) |
| `duplicate_of` | string | no | ID of canonical node this duplicates (for tree representation of DAGs) |

**When to use Datum vs Proposition:**
- Datum nodes represent reported findings; their `base_rate` captures source reliability
- Proposition nodes represent claims inferred from the graph structure
- A Datum says "this was reported"—its `base_rate` captures how much to trust the source
- The Link from Datum to Proposition captures inferential uncertainty (does the finding support the claim?)

**Datum base_rate as source reliability:**

The `base_rate` of a Datum encodes prior trust in the source's accuracy. A low base_rate means the Datum is likely false (the report is inaccurate), so downstream links are unlikely to activate (see Bayesian Network Conversion). This naturally attenuates the influence of low-quality sources without additional parameters.

### Link

Reified support or undermine relationship. First-class node enabling:
- Joint premises (multiple sources required together)
- Undercutting (targeting another Link rather than a Proposition)
- Auxiliary claims (background assumptions as joint sources)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique identifier |
| `source_ids` | [node IDs] | yes | One or more source nodes (joint if multiple) |
| `target_id` | node ID | yes | Target node (Proposition or Link) |
| `polarity` | string | yes | `"supports"` or `"undermines"` |
| `strength` | [0,1] | no | How much the evidence shifts belief in the target (0=no effect, 1=decisive); default 0.8 |
| `cpt` | CPT | no | Custom CPT (overrides default generation) |
| `textual_basis` | TextualBasis | no | Source text grounding this element (see Text Grounding) |
| `explicitness` | string | no | How directly the relation was stated: `explicit`, `implicit`, or `inferred` |

**Link patterns:**

| source_ids | target | polarity | Meaning |
|------------|--------|----------|---------|
| [A] | X (Proposition) | supports | A supports X |
| [A, B] | X (Proposition) | supports | A and B jointly support X |
| [A] | X (Proposition) | undermines | A rebuts X |
| [A] | L (Link) | undermines | A undercuts L (attacks the inference) |
| [A, B] | L (Link) | undermines | A and B jointly undercut L |

---

## Text Grounding

These fields provide traceability from structured graph elements back to source text.

### TextualBasis

Captures the source text that grounds a node or Link.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | yes | Verbatim quote from source text |
| `location` | string | no | Where in the source document (e.g., "Results, paragraph 3", "p. 12", "Abstract") |

**Example:**
```yaml
textual_basis:
  text: "The RCT demonstrated a 40% improvement in primary outcomes (p < 0.01)"
  location: "Results, paragraph 3"
```

For nodes, `textual_basis` captures where the claim or finding was stated. For Links, it captures the text expressing or implying the support/undermine relationship.

### Explicitness

Indicates how directly a claim or relationship was stated in the source text. Applies to both Propositions and Links.

| Value | Meaning |
|-------|---------|
| `explicit` | Directly stated in text |
| `implicit` | Not explicitly stated, but signaled by discourse markers, context, or structure. A careful reader would pick it up. |
| `inferred` | No textual signal. Reconstructed by the analyst based on domain knowledge or logical necessity. |

Note: `explicitness` is metadata about textual grounding, not about argument strength. An implicit link can still have high `strength` if the inference is solid.

---

## Bayesian Network Conversion

### Graph Structure

The argument graph maps to a Bayesian network as follows:

- **Proposition/Conclusion/Datum nodes** → BN nodes with binary states {true, false}
- **Link nodes** → BN nodes with binary states {active, inactive}

**Edge structure in BN:**
- Each Link node has edges FROM its source nodes
- Each Link node has an edge TO its target node
- Undercutting Links create edges TO the Link they target (U → L)

### CPT Generation Summary

These are suggested formulas used when generating CPTs from node parameters. They provide reasonable defaults for common patterns. When these don't fit your domain, use a custom `cpt` field to override (see CPT Object Format below).

| Pattern | Formula |
|---------|---------|
| Single support | `P = β + s(1-β)` |
| Single undermine | `P = β(1-s)` |
| Joint support (multi-source link) | `P = β + s(1-β)` only when ALL sources true, else `P = β` |
| Independent supports (noisy-OR) | `P = 1 - (1-β)∏(1-sᵢ)` |
| Independent undermines | `P = β × ∏(1-sⱼ)` |
| Mixed (supports + undermines) | `P = [supports result] × ∏(1-sⱼ)` |

Where β = target's `base_rate`, s = link's `strength`.

### CPT Generation for Links

Links activate deterministically based on their sources:

```
P(L=active | sources) = 1    if all sources true
                      = 0    otherwise
```

**CPT table for Link with sources [A, B]:**

| A | B | P(L=active) |
|---|---|-------------|
| false | false | 0 |
| true | false | 0 |
| false | true | 0 |
| true | true | 1 |

The link's `strength` parameter does not affect activation—it determines how much an active link shifts the target's probability (see Default CPT Generation for Propositions).

**Implementation note on numerical stability:**

The semantic CPT assigns P(L=active | some source false) = 0. Implementations may substitute a small epsilon to avoid numerical issues with exact zeros in log-space computations.

**Design note on multi-source links:**

Multi-source links enforce **joint necessity**—all sources must be true for the link to fire. This is intentional: multi-source links model premises that only work together (e.g., "virus present in aerosols" AND "aerosolized virus is infectious" → "aerosol transmission occurs").

For **independent/disjunctive support** ("any of A, B, or C supports X"), use separate single-source links to the same target. The noisy-OR composition at the target handles accumulation naturally.

### Default CPT Generation for Propositions

**Terminology:**
- `L=active`: Link successfully carries evidential force
- `L=inactive`: Link does not carry force (sources false, inference invalid, or fully defeated)

**Base rate interpretation:**

`base_rate` (β) is the **conditional probability** P(X=true | all incoming links inactive). This is not necessarily the marginal prior P(X=true)—the marginal depends on the probability distribution over link states.

**Canonical form (supports only):**

Using noisy-OR with leak:
```
P(X=false | L₁...Lₙ) = (1-β) × ∏ᵢ (1 - sᵢ)^𝟙[Lᵢ=active]
P(X=true | L₁...Lₙ)  = 1 - P(X=false | L₁...Lₙ)
```

Where sᵢ is the strength of supporting link Lᵢ and 𝟙[·] is the indicator function (1 if condition holds, 0 otherwise).

The intuition is that each active supporting link independently has a chance sᵢ to "activate" the proposition. The base rate β acts as a leak—the proposition can be true even with no active support.

**Equivalent forms (single active link):**

For a single active supporting link with strength s, the formula simplifies to:
```
P(X=true | L=active) = 1 - (1-β)(1-s)
                     = β + (1-β)s
```

Both forms yield identical results. Examples in this spec use the second form (e.g., `0.3 + 0.7×0.8` where β=0.3 and s=0.8) for transparency about how base rate and strength combine.

**Adding undermining links (rebutting):**

Undermining links targeting the Proposition apply multiplicatively after support:
```
P(X=true | supports, undermines) = P(X=true | supports) × ∏ⱼ (1 - sⱼ)^𝟙[Uⱼ=active]
```

Where sⱼ is the strength of undermining link Uⱼ.

**Modeling note:** This "supports-then-undermines" composition is a reasonable default, but not the only option. Alternatives include:
- Simultaneous weighting in a single formula
- Log-odds space where undermines contribute negative evidence

The ontology does not mandate a composition—use custom CPTs when alternatives better fit the domain.

**Boundedness guarantee:**

The default composition always yields valid probabilities:
- All terms (β, sᵢ, sⱼ) are in [0,1]
- Products of [0,1] terms remain in [0,1]
- With many active supports: P(X=true) → 1 (asymptotic, never exceeds 1)
- With many active undermines: P(X=true) → 0 (asymptotic, never negative)

**Independence assumption and correlated evidence:**

The noisy-OR composition assumes that supporting links are conditionally independent—each has an independent chance to activate the proposition. This assumption breaks down when evidence sources share common vulnerabilities:

- Studies from the same lab or using the same methodology
- Findings derived from the same underlying dataset
- Arguments that rely on shared assumptions

When sources share common causes of failure, treating them as if they were independent leads to overconfidence in the target proposition.

**Solution: Shared undercutters.**

Model the common vulnerability as a proposition that undercuts all affected links:

```yaml
nodes:
  - type: Proposition
    id: method_flawed
    content: "Lab X's methodology is flawed"
    base_rate: 0.2

  - type: Link
    id: U1
    source_ids: [method_flawed]
    target_id: L1    # Link from Study 1
    polarity: undermines

  - type: Link
    id: U2
    source_ids: [method_flawed]
    target_id: L2    # Link from Study 2
    polarity: undermines
```

If `method_flawed` is true, both links are undercut together—the evidence fails as a unit. If false, both proceed independently. This captures the correlation structure without requiring new parameters: the base rate of the shared vulnerability controls the degree of correlation.

For more complex correlation structures, use a custom CPT on the target proposition.

### Handling Undercutting

When Links target another Link (undercutting), they reduce the probability that the target Link activates, rather than directly affecting a Proposition.

**Single undercutter:**
```
P(L=active | sources all true, U=active)   = 1 - sᵤ
P(L=active | sources all true, U=inactive) = 1
```

Where sᵤ is the undercutter's strength.

**Multiple undercutters (default composition):**

Undercutters combine multiplicatively:
```
P(L=active | sources all true, U₁...Uₘ) = ∏ⱼ (1 - sⱼ)^𝟙[Uⱼ=active]
```

Each active undercutter independently reduces activation probability; multiple undercutters can drive it toward zero but never negative.

**BN structure for undercutting:**

Undercutting Links become **parents** of the Link they target in the Bayesian network:
```
Sources ──→ L ──→ Target
             ↑
U.sources → U
```

The CPT for L conditions on both its sources AND any undercutting Links. This is not an external adjustment—U is a proper parent node of L.

Undercutting thus attacks the *inference*, not the conclusion. Even if L is fully defeated, the target Proposition might still be true via other Links or its base rate.

### CPT Object Format

The `cpt` field accepts two formats: **tabular** (universal) and **parametric** (compact).

#### Tabular Format

Explicit probability table keyed by parent assignments.

```yaml
cpt:
  type: table
  parents: [A, B]           # Ordered list of parent node IDs
  rows:
    "false,false": 0.1      # P(node=true | A=false, B=false)
    "true,false": 0.4       # P(node=true | A=true, B=false)  
    "false,true": 0.3       # P(node=true | A=false, B=true)
    "true,true": 0.9        # P(node=true | A=true, B=true)
```

Keys are comma-separated parent states in `parents` order. Values are P(node=true). P(node=false) is implicit: 1 - P(node=true).

For Link nodes, use `active`/`inactive` instead of `true`/`false` for clarity:
```yaml
cpt:
  type: table
  parents: [L1, L2]
  rows:
    "inactive,inactive": 0.1
    "active,inactive": 0.5
    "inactive,active": 0.4
    "active,active": 0.95
```

#### Parametric Formats

Compact specification for common CPT patterns.

**Noisy-OR** (default for Propositions with supporting links):
```yaml
cpt:
  type: noisy_or
  leak: 0.1                 # P(true | all parents inactive)
  weights:                  # Per-parent activation strengths
    L1: 0.7
    L2: 0.6
```
Formula: P(false) = (1 - leak) × ∏ᵢ (1 - wᵢ)^𝟙[parentᵢ=active]

**Noisy-AND** (for conjunction-dominant cases):
```yaml
cpt:
  type: noisy_and
  base: 0.9                 # P(true | all parents true)
  weights:                  # Per-parent necessity
    A: 0.8
    B: 0.7
```
Formula: P(true) = base × ∏ᵢ (1 - wᵢ × 𝟙[parentᵢ=false])

**Logistic** (for learned/calibrated models):
```yaml
cpt:
  type: logistic
  bias: -1.0                # Intercept (log-odds)
  weights:                  # Per-parent log-odds contributions
    L1: 2.0
    L2: 1.5
```
Formula: P(true) = σ(bias + Σᵢ wᵢ × 𝟙[parentᵢ=active]), where σ is the sigmoid function.

#### Precedence Rules

1. If `cpt` field present → use it exactly (replaces generated CPT)
2. Otherwise → generate from node parameters using default rules

Custom CPTs allow:
- Complex conditional dependencies
- Empirically calibrated probabilities  
- Non-standard composition functions
- k-of-n thresholds and other aggregation schemes

---

## Examples

### Simple Support

```yaml
nodes:
  - type: Proposition
    id: H1
    content: "Drug X is effective"
    base_rate: 0.3

  - type: Datum
    id: D1
    content: "RCT showed 40% improvement"
    source: "Smith et al. 2024"
    base_rate: 0.85           # High-reliability source

  - type: Link
    id: L1
    source_ids: [D1]
    target_id: H1
    polarity: supports
    strength: 0.8
```

**Graph structure:**
```
D1 → L1 → H1
```

### Joint Support

```yaml
nodes:
  - type: Proposition
    id: H1
    content: "Aerosol transmission occurs"
    base_rate: 0.1

  - type: Proposition
    id: P1
    content: "Virus is present in aerosols"
    base_rate: 0.5

  - type: Proposition
    id: P2
    content: "Aerosolized virus remains infectious"
    base_rate: 0.5

  - type: Link
    id: L1
    source_ids: [P1, P2]    # Joint: both required
    target_id: H1
    polarity: supports
    strength: 0.85
```

**Graph structure:**
```
P1 ─┐
    ├─→ L1 ─→ H1
P2 ─┘
```

### Undercutting

```yaml
nodes:
  - type: Proposition
    id: H1
    content: "Drug X is effective"
    base_rate: 0.3

  - type: Datum
    id: D1
    content: "RCT showed positive result"
    source: "Smith et al. 2024"
    base_rate: 0.85           # High-reliability source

  - type: Proposition
    id: U1
    content: "Study had major methodological flaws"
    base_rate: 0.1

  - type: Link
    id: L1
    source_ids: [D1]
    target_id: H1
    polarity: supports
    strength: 0.8

  - type: Link
    id: L2
    source_ids: [U1]
    target_id: L1           # Targets the link, not H1
    polarity: undermines
    strength: 0.8
```

**Graph structure:**
```
D1 → L1 → H1
      ↑
U1 → L2
```

### Rebutting

```yaml
nodes:
  - type: Proposition
    id: H1
    content: "Drug X is effective"
    base_rate: 0.3

  - type: Datum
    id: D1
    content: "RCT showed positive result"
    source: "Smith et al. 2024"
    base_rate: 0.85           # High-reliability source

  - type: Datum
    id: D2
    content: "Replication study showed no effect"
    source: "Jones et al. 2025"
    base_rate: 0.85           # High-reliability source

  - type: Link
    id: L1
    source_ids: [D1]
    target_id: H1
    polarity: supports
    strength: 0.8

  - type: Link
    id: L2
    source_ids: [D2]
    target_id: H1           # Targets H1 directly
    polarity: undermines
    strength: 0.6
```

**Graph structure:**
```
D1 → L1 → H1 ← L2 ← D2
```

### Negative Results and Absence of Evidence

Negative findings ("no effect observed," "hypothesis not supported") are typically represented as a Datum node stating the negative result, connected via an undermining Link to the hypothesis:

```yaml
nodes:
  - type: Datum
    id: D1
    content: "Well-powered RCT found no significant effect of Drug X"
    source: "Jones et al. 2024"
    base_rate: 0.85

  - type: Link
    id: L1
    source_ids: [D1]
    target_id: H1  # "Drug X is effective"
    polarity: undermines
    strength: 0.7
```

**"No evidence for X"** (literature summary) is represented structurally: a Proposition with no supporting links and an appropriately low `base_rate` will have low posterior probability.

**"A does not support B"** (disputed inference) is modeled as an undercutter targeting the Link from A to B, not as a direct relationship between A and B.
