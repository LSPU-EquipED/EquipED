/** Edited display copy keyed by the exact archived note; unknown notes stay intact. */
const limitations: Record<string, { label: string; text: string }> = {
  'One run per condition; ordinary generation variability was not measured.': {
    label: 'Single run',
    text: 'Each condition was tested once; generation variability was not measured.',
  },
  'The expected scores came from an artificial score-increase rule, not independent faculty scoring.':
    {
      label: 'Reference scores',
      text: 'Targets used an artificial score-increase rule rather than independent faculty scoring.',
    },
  'A later identical-input Base run matched v7 on SLM 4 (MAE 0.30).': {
    label: 'Repeat evaluation',
    text: 'A later base run with identical input matched the fine-tuned result on SLM 4 (MAE 0.30).',
  },
  'Training-document checks and historical held-out checks are combined here; this is not proof of generalization.':
    {
      label: 'Mixed inputs',
      text: 'Training-document and historical held-out checks are combined; these results do not prove generalization.',
    },
  'Four comparisons cover three source inputs. The repeated Capstone input is listed twice, not treated as two independent SLMs.':
    {
      label: 'Repeated input',
      text: 'Four comparisons cover three source inputs. The two Capstone runs use the same SLM.',
    },
  'Reasoning assessments are audit observations, not a scored human-review study.': {
    label: 'Reasoning review',
    text: 'Audit observations were not part of a formally scored human-review study.',
  },
  'SLM 3 and SLM 4 cannot be assumed unseen for every adapter version.': {
    label: 'Held-out status',
    text: 'SLMs 3 and 4 may overlap with training for some models.',
  },
  'A lower error against a synthetic reference does not establish better rubric interpretation.': {
    label: 'Interpretation',
    text: 'Lower scoring error against synthetic references does not prove better rubric reasoning.',
  },
  'One run per condition; generation variability was not measured. No repairs or fallback responses occurred in these paired comparisons.':
    {
      label: 'Single run',
      text: 'Each condition was tested once, without measuring generation variability. No responses required repair or fallback.',
    },
  'Both models received identical initial prompts and complete extracted source packets. All eight held-out comparisons are retained, including worse and unchanged scores.':
    {
      label: 'Comparison coverage',
      text: 'Both models received identical prompts and complete extracted inputs. All eight held-out comparisons are included, including worse and unchanged scores.',
    },
  'Exact quotation grounding is a mechanical substring check against the cited source chunk. It does not certify evidence relevance, completeness, or reasoning quality.':
    {
      label: 'Grounding scope',
      text: 'Grounding checks exact text matches in cited chunks; it does not establish evidence relevance, completeness, or reasoning quality.',
    },
  'Targets are provisional AI-authored, user-reviewed references, not independent faculty scores. Several versus pervasive rubric levels remain qualitative.':
    {
      label: 'Reference scores',
      text: 'Targets are provisional, AI-authored and user-reviewed, rather than independent faculty scores. “Several” and “pervasive” remain qualitative rubric distinctions.',
    },
  'Held-out topics and names differ from training, but share a synthetic template. This does not establish generalization to real SLMs. These documents are now evaluated benchmarks.':
    {
      label: 'Generalization',
      text: 'Held-out inputs use different topics and names but share the training template. They are now evaluated benchmarks and do not prove generalization to real SLMs.',
    },
  'GAD-01 and GAD-03 scoring improved on this small set; GAD-02 and GAD-04 worsened, and GAD-05 stayed unchanged. Overall held-out MAE did not improve.':
    {
      label: 'Scoring outcomes',
      text: 'GAD-01 and GAD-03 improved; GAD-02 and GAD-04 worsened; GAD-05 was unchanged. Overall held-out MAE did not improve on this small set.',
    },
};

export function presentArchiveLimitation(note: string) {
  return (
    limitations[note] ?? {
      label: 'Study limitation',
      text: note
        .replace(/\badapters\b/gi, 'fine-tuned models')
        .replace(/\badapter\b/gi, 'fine-tuned model'),
    }
  );
}
