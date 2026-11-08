# Failure Audit

Analysis of the offline-baseline top 10 and bottom 10 promos against the raw
screenplay text. The offline baseline selects deterministic 20-60 second
windows — it does NOT use LLM judgment, so failures here demonstrate why the
LLM stage is essential.

## Top 10 Failures

### 1. Dramatic on paper, static on screen

**#5 `ep08_offline_01`** (Ep 8, 00:00–00:21, 21.5s)

> Hook: "Medium close-up of Juliana seated at a rustic wooden table beside a
> daylight-lit window…"

This is a warm, quiet scene of Juliana reading her mother's herbalism book
while Alexander brings her yarrow flowers. Dialogue: "Some of the pages are
ruined. Careful." / "Mother spent years writing this." / "Good for wounds.
Fever, too." No confrontation, no threat, no urgency. It reads as tender
on the page but would be unwatchable as a cold-viewer promo — two people
discussing dried herbs in a cabin.

**Type:** Quiet intimate scene with no visual hook.

---

### 2. Cliffhanger actually resolves one line later

**#1 `ep17_offline_05`** (Ep 17, 00:07–00:27.7, 20.7s)

> Cliffhanger: "As long as I draw breath…"

The very next event (28.0s) is Alexander kneeling before Juliana and
completing the sentence: "…no one will hurt you again." Followed by "You
cannot promise that" / "I just did." The tension is fully resolved within
4 seconds of the clip ending. A real promo should cut BEFORE the answer.

**Type:** Cliffhanger resolves immediately.

---

### 3. Hook inferred from a boring stage direction

**#4 `ep35_offline_04`** (Ep 35, 00:09–00:30.8, 21.8s)

> Hook: "Close-up on her trembling, weathered hands gripping a mossy stone
> bolt set into the wall…"

The opening is an elderly woman unlocking a stone door and walking through
snow. No confrontation, no shocking line, no physical violence. On screen
this would look like a slow establishing shot of someone arriving at a cabin.
A scrolling viewer would keep scrolling.

**Type:** Hook inferred from a stage direction that is actually visually boring.

---

### 4. Needs lore a cold viewer lacks

**#3 `ep02_offline_02`** (Ep 2, 00:00–00:20.7, 20.7s)

> Hook: "I cannot marry you, Juliana."

This line is strong in isolation, but it opens at the very start of Episode 2
where a new suitor (not Gerald from Episode 1) rejects Juliana. A cold viewer
seeing this promo cannot distinguish this from the altar scene. The context
of who this man is and why his rejection matters requires knowing Episode 1.
The cliffhanger (pendant insert shot) is purely visual and unresolved on
screen.

**Type:** Standalone clarity is poor without Episode 1 context.

---

### 5. Duration borderline and snapped awkwardly

**#2 `ep15_offline_03`** (Ep 15, 00:03.5–00:26.8, 23.3s)

> Cliffhanger: "High-angle two-shot as Juliana rushes forward and drops
> directly onto her knees in the cold mud before the thug."

This is an action line, not dialogue. The clip is well-chosen content-wise
(violent confrontation), but the end point is an ACTION description of
Juliana kneeling in mud. On screen, this could be a powerful image — or
it could read as an odd freeze frame if the next beat is the actual dramatic
moment. The flag `possible_resolution_after_clip` correctly identifies that
the script continues with what may resolve the tension.

**Type:** Awkward event-boundary snapping; cliffhanger is an action beat.

---

## Bottom 10 Failures

### 6. Exposition with no emotional escalation

**#250 `ep48_offline_05`** (Ep 48, 00:07.8–00:30.8, 23.0s)

> Hook: "Catherine glides across the chamber past a roaring stone hearth,
> picking up an ornate silver hand mirror…"

A villain picking up a mirror and looking at her own reflection. This is
scene-setting description with no hook, no confrontation, and no reason for
a viewer to stop scrolling. On video it is someone walking across a room.

**Type:** Pure exposition, no dramatic content.

---

### 7. Spoils a major twist

**#249 `ep28_offline_05`** (Ep 28, 00:03.2–00:26.7, 23.5s)

> Hook: "Catherine plants her embroidered shoe deliberately atop the fallen
> book."

This segment reveals the Dowager Duchess's poisoning plot and Catherine's
involvement — a late-series twist. Posting this as a promo would spoil the
mystery that drives episodes 20-30.

**Type:** Spoils a major twist.

---

## What the evaluation cannot show

The tool only sees screenplay text. It cannot verify:
- Whether a written action translates to compelling video
- Whether actors deliver lines with the energy the parentheticals suggest
- Whether the blocking, lighting, and score make a moment stop-scrolling
- Whether real viewers on TikTok/Instagram would actually stop, watch, and
  click through

### How Kuku would measure real success

1. **Editor acceptance rate**: What fraction of the top-10 picks does a human
   editor approve without modification?
2. **Edits per accepted promo**: How many timestamp shifts or segment changes
   does the editor make?
3. **Time saved per show**: Compare review minutes with the tool versus manual
   full-episode watching.
4. **Platform metrics** (post-deployment): 3-second view rate, completion rate,
   install/signup conversion from posted promos.
5. **A/B test**: Tool-picked promos versus editor-picked promos on the same
   show, holding creative and ad spend comparable.
