"""SanctionsIndex — read-only, in-RAM recall structure built once from the list.

Holds:
  * every entity flattened into searchable NameVariants (primary + aliases)
  * an exact normalised-name -> entity_id map        (S0)
  * a phonetic-key -> [variant idx] blocking index   (S1 recall)
  * a wallet-address -> entity_id set                 (crypto S0)
  * token IDF weights                                 (rare-token feature)

Designed to be shared read-only across screening processes.
"""
from __future__ import annotations
import collections
import math
import pathlib
import pandas as pd

from ..domain.models import SanctionedEntity, NameVariant
from ..domain.enums import EntitySchema
from ..normalization import norm, tokens, phon, norm_id


def _split(field: str) -> list[str]:
    if not field:
        return []
    return [p.strip() for p in str(field).split(";") if p.strip()]


class SanctionsIndex:
    def __init__(self, entities: list[SanctionedEntity]):
        """Build all in-RAM lookup structures from a flat entity list.

        Iterates once over all entities and their name variants to populate the
        exact map, phonetic blocking index, wallet set, and IDF weights.
        """
        self.entities = entities
        self.entity_by_id: dict[str, SanctionedEntity] = {e.id: e for e in entities}

        self.variants: list[NameVariant] = []
        self.entity_variants: dict[str, list[NameVariant]] = collections.defaultdict(list)
        self.exact: dict[str, str] = {}                       # variant_norm -> entity_id
        self.block: dict[str, list[int]] = collections.defaultdict(list)
        self.wallets: dict[str, str] = {}                     # addr.lower() -> entity_id
        self.id_index: dict[str, str] = {}                    # norm_id -> entity_id
        df: collections.Counter = collections.Counter()       # token document frequency

        for e in entities:
            for raw_id in e.identifiers:                      # exact-ID lookup (passport/national)
                key = norm_id(raw_id)
                if len(key) >= 5:                             # ignore tiny/ambiguous ids
                    self.id_index.setdefault(key, e.id)
            names = [(e.name, True)] + [(a, False) for a in e.aliases]
            seen_tokens_for_entity: set[str] = set()
            for raw, is_primary in names:
                raw = raw.strip()
                if not raw:
                    continue
                vnorm = norm(raw)
                idx = len(self.variants)
                v = NameVariant(entity_id=e.id, schema=e.schema_,
                                variant_norm=vnorm, variant_raw=raw,
                                is_primary=is_primary)
                self.variants.append(v)
                self.entity_variants[e.id].append(v)
                self.exact.setdefault(vnorm, e.id)
                for t in set(tokens(vnorm)):
                    self.block[phon(t)].append(idx)
                    seen_tokens_for_entity.add(t)
                if e.schema_ is EntitySchema.CRYPTO_WALLET:
                    self.wallets[raw.lower()] = e.id
            for t in seen_tokens_for_entity:
                df[t] += 1

        n = max(1, len(entities))
        self.idf: dict[str, float] = {t: math.log(1 + n / c) for t, c in df.items()}
        self._default_idf = math.log(1 + n)

    # ---- factory -------------------------------------------------------
    @classmethod
    def from_parquet(cls, path: str | pathlib.Path) -> "SanctionsIndex":
        """Load the index from the consolidated sanctions parquet file."""
        df = pd.read_parquet(path)
        entities = [
            SanctionedEntity(
                id=r.id,
                schema=EntitySchema.coerce(r.schema),
                name=r.name,
                aliases=_split(r.aliases),
                countries=_split(r.countries),
                programs=_split(getattr(r, "sanctions", "")),
                dob=(getattr(r, "birth_date", "") or None),
                identifiers=_split(getattr(r, "identifiers", "")),
                first_seen=getattr(r, "first_seen", None),
            )
            for r in df.itertuples()
        ]
        return cls(entities)

    @classmethod
    def from_db(cls, engine, dataset: str = "sanctions") -> "SanctionsIndex":
        """Build the index from the live Postgres tables (opensanctions_target +
        crypto_wallet) instead of the parquet snapshot. Lazy-imports the DB layer so the
        parquet path never requires sqlalchemy."""
        from .. import db          # local import: keeps sqlalchemy optional
        entities = db.load_entities(engine, dataset) + db.load_wallet_entities(engine)
        return cls(entities)

    # ---- lookups -------------------------------------------------------
    @property
    def default_idf(self) -> float:
        """Max IDF (an unseen / globally-unique token). Used to normalise rarity."""
        return self._default_idf

    def idf_of(self, token: str) -> float:
        """IDF weight for a token; defaults to the max-IDF for unseen tokens."""
        return self.idf.get(token, self._default_idf)

    def exact_entity(self, query_norm: str) -> str | None:
        """Exact normalised-name lookup; returns entity_id or None."""
        return self.exact.get(query_norm)

    def wallet_entity(self, address: str) -> str | None:
        """Case-insensitive wallet address lookup; returns entity_id or None."""
        return self.wallets.get((address or "").lower())

    def id_entity(self, identifier: str) -> str | None:
        """Exact passport/national-ID lookup; returns entity_id or None."""
        key = norm_id(identifier)
        return self.id_index.get(key) if len(key) >= 5 else None

    def recall(self, query_norm: str, max_candidates: int = 200) -> list[str]:
        """Return candidate entity_ids ranked by shared-token IDF mass.

        Weighting by IDF means an entity that shares a RARE query token (e.g.
        "Qadhafi") outranks one that merely shares a common token ("Mohammed").
        That keeps the candidate set small and relevant, so we can cap it low
        without dropping real matches — and it directly fights false positives.
        """
        qtok = set(tokens(query_norm))
        if not qtok:
            return []
        hits: collections.Counter = collections.Counter()
        for t in qtok:
            w = self.idf_of(t)
            for vidx in self.block.get(phon(t), ()):
                hits[self.variants[vidx].entity_id] += w
        return [eid for eid, _ in hits.most_common(max_candidates)]

    @property
    def n_entities(self) -> int:
        return len(self.entities)

    @property
    def n_variants(self) -> int:
        return len(self.variants)
