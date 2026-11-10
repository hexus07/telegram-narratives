# Annotation guidelines

## General principles

- **The role is determined by the text, not by the channel's position.** In an anti-migrant post, migrants are Antagonist; in a pro-migrant post, they are Innocent.
- **Explicit framing in the text.** What matters is the role that the text assigns to the entity, directly or through its wording, not the reader's general impression.
- **Granularity.** Instead of evaluating the post as a whole or the general attitude towards an entity, the role is linked to a specific entity within the text.

## 1. Entities

### 1.1 Which entities to annotate

- Only central named entities: persons, organizations, states, and groups (including those derived from names and place names) that the text presents as acting or affected. At most three main roles are taken from the dominant narrative.
- A role is assigned only at the first mention of an entity in the post, if a role applies. This follows the SemEval rule (Mahmoud et al., 2025).
- Secondary mentions, places without action, and news background are not annotated.

### 1.2 Normalization

1. **Country + sector:** everything that belongs to a country is normalized to:
   - `<country>-gov`: leaders, offices, officials, agencies, police, courts;
   - `<country>-people`: citizens, civilians, local residents, "natives";
   - `<country>-mil`: armed forces, national guards, strikes without a stated perpetrator (e.g. "a Ukrainian drone"), and **epithets for the military** such as "militants", "neo-Nazis", "invaders", "occupiers" when the text refers to soldiers.
2. **Specification in brackets** is added if it adds context, up to two mentions:
   - `Ukraine-gov (Zelensky)` — yes;
   - `Netherlands-gov (Defence Minister, Foreign Minister, Prime Minister, Dutch government)` — no, since the description adds no specification and only describes the group.
3. **Soldiers** are coded as `-gov`, even when presented as victims (e.g., soldiers' bodies). The role is then Innocent.
4. **Non-state actors** are recorded using a fixed list of names (`migrants`, `far-right`, `media`, `EU`, `NATO`, `Mexican drug cartels`, …). A new name is added to the list once and then used unchanged.
5. **Migrant groups** of any origin ("Syrian asylum seekers", "Tajik settlers") → `<country>-migrants`.
6. **Country names** use one English form: `Ukraine`, `Russia`, `US`, `UK`.
7. **All mentions and epithets of one actor** ("Zelensky", "Kiev regime", "gauleiter") are merged into one entity.

## 2. Roles

- The role is determined by the function the text assigns to the entity: who acts, who is harmed, who saves, who is to blame.
- One of three main roles is chosen:
  - **Protagonist:** an entity presented positively (protector, hero, peacemaker).
  - **Antagonist:** an entity presented as a threat, perpetrator, or enemy.
  - **Innocent:** an entity presented as a victim or affected party.
- If none applies, `none` is used: the entity is mentioned but has no role in the narrative.

## 3. Narratives

### 3.1 What counts as a narrative

- A narrative is present when the text assigns agency, causality, or moral evaluation to entities.
- The truthfulness of a fact is not a criterion. Disinformation is not marked separately.
- Quotes by officials, experts, or media are coded as the narrative of the post if the channel relays them without disputing them.
- **Quote of the opposing side:** if a post cites another side's narrative in order to expose or refute it, the criticism is coded, not the quoted narrative.

### 3.2 Recording narratives

1. **Record all narratives** of each post (multi-label). This is the main field for analysis.
2. **Mark one narrative as dominant:** the narrative that expresses the main idea of the text; if the main claim of the post cannot be determined, the first narrative in the text is chosen.