---
name: paper-summariser
description: Summarize research papers. Use whenever the user asks to "summarize," "condense," "give me the gist," "TL;DR," "recap," "boil down," or wants key points/takeaways extracted from a long text, upload, or set of documents — including when they paste a long passage and ask what it says or means. Also use for multi-document summarization (e.g. summarizing several files or search results into one synthesis) and for producing summaries at a specific length, format, or reading level.
---

# Summarizer

A skill for producing accurate, appropriately-scoped summaries of text — single documents, multiple documents, transcripts, or conversation threads.

## Core principle

A good summary is judged by two things in tension: **fidelity** (it doesn't distort, invent, or drop anything essential) and **compression** (it's meaningfully shorter and easier to consume than the original). Optimize for both. When forced to choose, fidelity wins — never sacrifice accuracy for brevity.

## Step 1: Determine scope and output before writing anything

Don't start summarizing until you know:

1. **Length/format target.** Did the user specify one ("summarize in 3 bullets," "one paragraph," "executive summary")? If not, default to roughly 10–15% of the original length, capped at a reasonable maximum (a few paragraphs for most documents). Err shorter for casual requests ("TL;DR this email"), longer for requests that signal thoroughness ("summarize this report for my team").
2. **Audience/purpose, if inferable.** A summary for "catching my boss up" emphasizes decisions and action items; a summary for "do I need to read this" emphasizes relevance and novelty; a summary for research purposes emphasizes findings and methodology. If genuinely ambiguous and the stakes of guessing wrong are low, pick the most reasonable default and proceed rather than asking — state the assumption briefly.
3. **Source location.** If the user references an uploaded file, check whether its content is already visible in context. If not, read it from disk — see the `file-reading` skill for routing by file type (pdf, docx, csv, etc.) before doing anything else. Don't summarize from a filename alone.
4. **Single vs. multi-document.** If multiple sources are involved, decide up front whether the user wants (a) one synthesized summary that integrates all sources, or (b) separate per-document summaries. Default to (a) unless the sources are unrelated or the user is comparing them, in which case structure the output by source or by theme — ask only if truly unclear.

## Step 2: Read the whole source before summarizing

Don't summarize from a partial read, the first page, or an assumption about structure. For long documents:
- Read start to finish (or use extraction tools for very long/scanned files per `file-reading`/`pdf-reading` skills).
- Note structure as you go: is this argumentative (thesis + evidence), narrative (events in sequence), reference (facts/data), or transactional (decisions/action items, e.g. meeting notes or email threads)? The structure should shape the summary's structure — don't force a narrative summary onto a decision log or vice versa.

## Step 3: Identify what actually matters

Before drafting, mentally sort content into:
- **Must include**: central claims/thesis, key decisions, numbers that drive the conclusion, action items, anything the document itself flags as important (headers, "in summary," "the key finding is").
- **Include if space allows**: supporting evidence, examples, context/background.
- **Omit**: repetition, tangents, boilerplate, illustrative detail that doesn't change the takeaway.

For multi-document synthesis, also note: where sources agree, where they conflict (flag conflicts explicitly — don't quietly pick one version), and what's unique to each source.

## Step 4: Write the summary

- **Own words, not compressed quotation.** Paraphrase throughout. Reproducing sentences with a few words changed is not summarizing — it's copying, and it's also a copyright problem (see below). A summary should read as if someone who deeply understood the source explained it fresh, not as if someone highlighted and trimmed it.
- **Lead with the point.** Put the main conclusion, decision, or finding first — don't make the reader wait for it, even if the source builds up to it.
- **Match structure to content type**: prose paragraph(s) for narrative/argumentative material; bullets for lists, action items, or discrete facts; a short table only if the user asked for one or the source is inherently tabular data.
- **Preserve important nuance.** If the source hedges ("preliminary results suggest," "in most but not all cases"), the summary should hedge too. Flattening uncertainty into false confidence is a fidelity failure.
- **Attribute when synthesizing multiple sources**: "The report finds X; the follow-up memo revises this to Y" rather than blending them into one unsourced claim.
- **Don't editorialize.** Don't add opinions, evaluations, or claims not present in the source unless the user explicitly asked for analysis on top of the summary — those are two different deliverables.

## Step 5: Check before returning

- Would someone who read only your summary come away with a materially correct understanding of the source? Re-read the original's key points against your draft.
- Is anything in the summary that isn't actually in the source? Remove it — never fill gaps with plausible-sounding inference.
- Is it actually shorter and easier to consume than the original, or did it just reorganize the same length of text?
- Does it match the length/format the user asked for?

## Copyright note

Summaries must be genuine paraphrase, substantially shorter than and reworded from the original — not lightly-edited excerpts. Avoid direct quotation except for rare, short (under ~15 words) phrases where exact wording matters (e.g. a legal term, a precise figure, a named commitment), and never reproduce song lyrics, poems, or other verbatim creative text. Don't mirror the source's paragraph-by-paragraph structure or sentence patterns — a true summary is a rewrite, not a trim.

## Output delivery

- If the summary is the whole answer and reasonably short, respond inline in the conversation — no need to create a file.
- If the user asked for a saved/downloadable summary, or the source set is large enough that the summary itself is a substantial document (e.g. summarizing a dozen reports into one briefing), create a markdown file per standard file-creation conventions.
- Never fabricate a "summary" of a file you were not actually able to read — if a source couldn't be accessed, say so rather than guessing at its contents.