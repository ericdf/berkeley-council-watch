# Member pages

`members/<name>.html` and `members/index.html` show, for each member of the Council seated in
December 2024 and for the body as a whole, what the annotated agendas record: the items each member
brought, their vote on each item's final motion, the motions they made, and roll-call attendance.
They are built by `councilwatch/member_site.py` from `data/generated/council-time/` (`items.json`,
`attendance.json`, `members.json`) and the reviewed files below.

**Counts by kind, never a score.** Each kind of count stands alone and is never added to another.
Every total is shown beside the median and range across the nine members, so a figure is always read
against the Council's own norm. The pages describe; the Berkeley Decision Project argues.

## Items a member brought: five roles

The From line of an annotated agenda names the members behind an item and, usually, a role. The
pages keep the roles apart:

| Role | Rule |
|---|---|
| Lead author | The only author or co-author named; or, among several, the one whose name appears in the item's Contact line |
| Joint author | One of several authors or co-authors, where the Contact line names none of them or more than one |
| Co-sponsor, on the agenda as posted | Named as a co-sponsor in the From line |
| Co-sponsor, added at the meeting | The Action records the member as added, and the transcript shows the addition at the meeting (`cosponsors.json`, finding `at_meeting`) |
| Co-sponsor, added later; when is not stated | The Action records the member as added, and the transcript does not show when |
| Named, role not printed | Named in the From line with no role |

The Clerk never prints which author led. The Contact line is the evidence used, and where it does
not settle the question every author is a joint author: listing order is not used.

**Comparisons use items on City business.** The members index and the total row on each member's
page leave out routine items (the `routine` thread: relinquishments of office funds, donations,
commemorations, appointments, excused absences) and count positions on state, federal and
international matters (the `external` thread) in a column of their own. Each member's page still
lists every item, routine ones included, by subject. Without this, a member who authors many
relinquishments or support letters would read as a prolific author of City business.

## Votes

The vote counted is the one on each item's final motion, as printed. "All Ayes" is kept as its own
column: the Clerk prints no names with it, and who was present at that moment is not recorded.
Consent calendar items have no vote of their own. A recusal printed inside another list is counted as
a recusal (the archive's L2 record does this and notes it).

The divided-votes grid lists every motion, other than procedural ones, on which a named member voted
no or abstained, including competing and substitute motions on items whose final vote was unanimous.

**Substitute motions.** The annotated agenda rarely prints the word. A failed motion followed by the
one that decided the item is shown as competing, unless `data/review/council-time/motions.json`
records that the transcript confirms it was a substitute, with a quotation the generator must find
in that transcript.

## Attendance

From the annotated agenda: absent at roll call, and the time of any later arrival. A member who left
early is not recorded, and the record gives no reasons.

## Reviewed inputs

In `data/review/council-time/`:

- `threads.json` → `items`: the subject of each member-authored item the Council did not hear (most
  were adopted on consent). Items the Council heard take the thread of their transcript segment.
  `routine` covers relinquishments of office funds, donations, commemorations, appointments and
  excused absences. `external` covers positions on state, federal and international matters.
- `motions.json`: competing motions the transcript confirms were substitutes.
- `cosponsors.json`: for each co-sponsor addition the Action records, what the transcript shows:
  `at_meeting` (the addition is heard at the meeting), `thanked_only` (an author thanks the member,
  which does not show when they joined), or `not_found`. A quotation and its timestamp or line is
  required for the first two and checked against the transcript by the generator.
