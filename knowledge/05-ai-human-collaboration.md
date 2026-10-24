# AI and human agents on the same call

An AI agent should not try to finish every call. It should finish the
routine ones, and for the rest, get the call to a person who can carry on
exactly where it stopped.

**When to hand off.** Four signals are enough for a first version: the
caller asks for a person; the topic is sensitive (fraud, a death in the
family, legal or medical matters); the caller is angry or getting angrier;
or speech recognition keeps failing. Each is cheap to detect and expensive
to ignore.

**What to pass on.** Who the caller is and how that was checked, what they
want, the details already given, what the AI already did, what is still
open, how the mood has moved, and a short summary with personal data
masked. If any of that is missing, the human has to ask again, and the
caller notices.

**How to transfer.** Bring the human in first, introduce them, then let the
AI drop. If nobody picks up, keep the caller with the AI and offer a
callback instead of leaving them in silence.

**Handing back.** Once the human has dealt with the sensitive part, the AI
can finish the routine remainder, with the same context, without asking
for anything twice.

**Measuring it.** Resolution and containment show outcome; handle time and
transfers show efficiency; cost per resolved call shows economics; the
share of steps done by the AI shows automation. Report them per type of
call, because a fraud call and a "where is my order" call should never be
averaged into one story.
