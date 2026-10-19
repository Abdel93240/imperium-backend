"""W2 — découverte causale (spec WR §3.3, §4, §5 ; cartes V20 ACT-WR-10, V21 ACT-WR-11).

Frontière stricte : la sélection des events notables, la recherche des candidats et l'assemblage sont
du code ; seules les sondes (§5.1) et les verdicts pairés (§5.3) relèvent d'un modèle. Tant que
`real_ai_enabled` est faux, ces deux étapes sont FACTICES (dry-run) : sondes `generated_by=dry_run`,
verdicts `model_used=dry_run` tirés de façon déterministe, assemblage et item docket marqués
`dry_run`, aucun appel modèle. Le W2 réel (V21) n'est pas codé : avec `real_ai_enabled` vrai, le
worker échoue sans avancer son curseur.

1. Notables (`wr.notable_criteria`, éditable) : type notable, red flag, question de l'utilisateur,
   ou anomalie W4 >= `anomaly_min_band` le même jour de Paris dans le domaine de l'event. Un event
   déjà sondé n'est pas repris ; au plus `max_targets_per_run` par passage (red flags d'abord).
2. Candidats (code) : filtres durs (antériorité stricte, `wr.chain_window_days`, pas déjà la cause
   déclarée, events internes du WR exclus) ; canaux graph (même correlation_id) et metadata (même
   domaine ou même jour) ; canaux vectoriels éteints (pas d'embeddings en dry-run). Rerank
   composite canal × proximité temporelle ; `retained` pour les `wr.chain_topn` premiers.
3. Assemblage (code) : verdicts direct_cause|favoring_condition >= `wr.chain_min_confidence` →
   liens proposés (depth = depth de la cause + 1) ; plusieurs causes directes ou cycle → conflits.
   Avec au moins un lien : `chain_assemblies` (pending_validation) + item docket `chain_proposal`.
   Rien n'entre dans le graphe causal réel (E2) avant la Phase 5.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.auth import User
from app.models.event import Event
from app.models.toolbox import SignalValue
from app.models.wr import ChainAssembly, ChainCandidate, ChainPairVerdict, ChainProbe
from app.services.params import get_parameter
from app.services.wr import anomalies, docket

PARIS = ZoneInfo("Europe/Paris")
DRY_RUN = "dry_run"
VERDICTS = ("direct_cause", "favoring_condition", "correlation", "no_link")
LINK_VERDICTS = ("direct_cause", "favoring_condition")
DRY_RUN_PROBES = 3
POOL_LIMIT = 500
CHANNEL_WEIGHTS = {"graph": 1.0, "metadata": 0.6}
INTERNAL_PREFIXES = ("planning.factory.", "planning.wr_", "planning.docket.", "planning.plan.", "decision.",
                     "auth.", "login", "logout", "user.")
DOCKET_DOMAINS = {"finance": "vault", "rides": "vector", "mission": "imperium", "planning": "imperium",
                  "day": "imperium", "path": "path", "pulse": "pulse"}
DEFAULT_CRITERIA = {"event_types": [], "red_flag_event_types": [], "user_question_event_types": [],
                    "anomaly_min_band": "orange", "anomaly_domains": {}, "max_targets_per_run": 10}


class RealW2NotCodedError(RuntimeError):
    pass


@dataclass
class W2Stats:
    targets: int = 0
    probes: int = 0
    candidates: int = 0
    retained: int = 0
    verdicts: int = 0
    links: int = 0
    assemblies: int = 0
    reasons: dict = field(default_factory=dict)


def run_window(db: Session, *, user: User, window_from: datetime, window_to: datetime) -> W2Stats:
    if get_settings().real_ai_enabled:
        raise RealW2NotCodedError("W2 réel (sondes et verdicts par modèle) pas encore codé : carte V21.")
    criteria = {**DEFAULT_CRITERIA, **(get_parameter(db, "wr.notable_criteria", default={}) or {})}
    window_days = int(get_parameter(db, "wr.chain_window_days", default=90))
    top_n = int(get_parameter(db, "wr.chain_topn", default=10))
    min_confidence = int(get_parameter(db, "wr.chain_min_confidence", default=60))
    stats = W2Stats()
    for target, reasons in notable_events(db, user=user, window_from=window_from, window_to=window_to,
                                          criteria=criteria):
        stats.targets += 1
        for reason in reasons:
            stats.reasons[reason] = stats.reasons.get(reason, 0) + 1
        _probe(db, user, target, stats)
        retained = _candidates(db, user, target, window_days, top_n, stats)
        verdicts = [_dry_run_verdict(db, user, target, candidate) for candidate in retained]
        stats.verdicts += len(verdicts)
        _assemble(db, user, target, reasons, retained, verdicts, min_confidence, window_to, stats)
    db.flush()
    return stats


def notable_events(db: Session, *, user: User, window_from: datetime, window_to: datetime,
                   criteria: dict) -> list[tuple[Event, list[str]]]:
    events = db.scalars(
        select(Event).where(Event.user_id == user.id, Event.created_at > window_from, Event.created_at <= window_to)
        .order_by(Event.occurred_at)
    ).all()
    if not events:
        return []
    probed = set(db.scalars(select(ChainProbe.target_event_id).where(
        ChainProbe.target_event_id.in_([event.id for event in events]))))
    flagged = _flagged_days(db, user, events, criteria)
    selected: list[tuple[int, Event, list[str]]] = []
    for event in events:
        if event.id in probed:
            continue
        reasons = []
        if event.event_type in criteria["red_flag_event_types"]:
            reasons.append("red_flag")
        if event.event_type in criteria["user_question_event_types"]:
            reasons.append("user_question")
        if event.event_type in criteria["event_types"]:
            reasons.append("notable_type")
        domain = _anomaly_domain(event.event_type, criteria)
        if domain is not None and (domain, _local_date(event.occurred_at)) in flagged:
            reasons.append("anomaly_same_day")
        if reasons:
            rank = 0 if "red_flag" in reasons else 1 if "user_question" in reasons else 2
            selected.append((rank, event, reasons))
    selected.sort(key=lambda entry: (entry[0], entry[1].occurred_at))
    return [(event, reasons) for _, event, reasons in selected[: int(criteria["max_targets_per_run"])]]


def _flagged_days(db: Session, user: User, events: list[Event], criteria: dict) -> set[tuple[str, str]]:
    if not criteria["anomaly_domains"]:
        return set()
    first = min(event.occurred_at for event in events) - timedelta(days=1)
    last = max(event.occurred_at for event in events) + timedelta(days=1)
    rows = db.scalars(select(SignalValue).where(
        SignalValue.signal_code.like("wr.%"), SignalValue.measured_at >= first, SignalValue.measured_at <= last,
        SignalValue.detail["user_id"].astext == str(user.id))).all()
    return {
        (row.signal_code.split(".")[1], row.detail.get("local_date"))
        for row in rows if anomalies.band_at_least(row.band, criteria["anomaly_min_band"])
    }


def _anomaly_domain(event_type: str, criteria: dict) -> str | None:
    for domain, prefixes in criteria["anomaly_domains"].items():
        if any(event_type.startswith(prefix) for prefix in prefixes):
            return domain
    return None


def _probe(db: Session, user: User, target: Event, stats: W2Stats) -> None:
    for index in range(1, DRY_RUN_PROBES + 1):
        db.add(ChainProbe(user_id=user.id, target_event_id=target.id, probe_kind="causal_hypothesis",
                          probe_text=f"[dry_run] sonde {index}/{DRY_RUN_PROBES} : cause possible de {target.event_type}",
                          generated_by=DRY_RUN))
    stats.probes += DRY_RUN_PROBES


def _candidates(db: Session, user: User, target: Event, window_days: int, top_n: int,
                stats: W2Stats) -> list[tuple[ChainCandidate, Event]]:
    pool = db.scalars(
        select(Event).where(Event.user_id == user.id, Event.id != target.id,
                            Event.occurred_at < target.occurred_at,
                            Event.occurred_at >= target.occurred_at - timedelta(days=window_days))
        .order_by(Event.occurred_at.desc()).limit(POOL_LIMIT)
    ).all()
    scored: list[tuple[float, ChainCandidate, Event]] = []
    for candidate in pool:
        if candidate.event_type.startswith(INTERNAL_PREFIXES) or candidate.event_id == target.causation_id:
            continue
        channels = []
        if candidate.correlation_id == target.correlation_id:
            channels.append("graph")
        if (_family(candidate.event_type) == _family(target.event_type)
                or _local_date(candidate.occurred_at) == _local_date(target.occurred_at)):
            channels.append("metadata")
        if not channels:
            continue
        age_days = (target.occurred_at - candidate.occurred_at).total_seconds() / 86400
        proximity = max(1 - age_days / window_days, 0)
        score = round(min(sum(CHANNEL_WEIGHTS[channel] for channel in channels), 1.0) * proximity, 4)
        row = ChainCandidate(user_id=user.id, target_event_id=target.id, candidate_event_id=candidate.id,
                             channels=channels, passed_hard_filters=True, rerank_score=score, retained=False)
        db.add(row)
        scored.append((score, row, candidate))
    scored.sort(key=lambda entry: (-entry[0], entry[2].occurred_at))
    retained = []
    for _score, row, candidate in scored[:top_n]:
        row.retained = True
        retained.append((row, candidate))
    db.flush()
    stats.candidates += len(scored)
    stats.retained += len(retained)
    return retained


def _dry_run_verdict(db: Session, user: User, target: Event,
                     pair: tuple[ChainCandidate, Event]) -> ChainPairVerdict:
    candidate, _event = pair
    digest = int(hashlib.sha256(f"{target.id}:{candidate.candidate_event_id}".encode()).hexdigest()[:8], 16)
    verdict = ChainPairVerdict(
        user_id=user.id, candidate_id=candidate.id, verdict=VERDICTS[digest % len(VERDICTS)],
        mechanism_fr="[dry_run] mécanisme factice", confidence=40 + digest % 61, model_used=DRY_RUN, valid=True,
    )
    db.add(verdict)
    return verdict


def _assemble(db: Session, user: User, target: Event, reasons: list[str],
              retained: list[tuple[ChainCandidate, Event]], verdicts: list[ChainPairVerdict],
              min_confidence: int, now: datetime, stats: W2Stats) -> None:
    links, conflicts = [], []
    for (candidate, cause), verdict in zip(retained, verdicts, strict=True):
        if verdict.verdict not in LINK_VERDICTS or verdict.confidence < min_confidence:
            continue
        links.append({"cause_event_id": str(cause.id), "cause_event_type": cause.event_type,
                      "verdict": verdict.verdict, "mechanism_fr": verdict.mechanism_fr,
                      "confidence": verdict.confidence, "depth": (cause.depth or 0) + 1,
                      "channels": list(candidate.channels)})
        if cause.causation_id is not None and cause.causation_id == target.event_id:
            conflicts.append({"kind": "cycle", "cause_event_id": str(cause.id)})
    direct = [link["cause_event_id"] for link in links if link["verdict"] == "direct_cause"]
    if len(direct) > 1:
        conflicts.append({"kind": "double_parent", "cause_event_ids": direct})
    if not links:
        return
    assembly = ChainAssembly(user_id=user.id, target_event_id=target.id, proposed_links=links,
                             conflicts=conflicts, status="pending_validation", dry_run=True)
    db.add(assembly)
    db.flush()
    local_date = _local_date(target.occurred_at)
    item = docket.create_item(
        db, current_user=user, item_type="chain_proposal",
        domain=DOCKET_DOMAINS.get(_family(target.event_type), "wr"),
        title_fr=f"[essai] Causes proposées pour {target.event_type} du {local_date}",
        payload={"target_event_id": str(target.id), "target_event_type": target.event_type, "reasons": reasons,
                 "links": links, "conflicts": conflicts, "dry_run": True},
        evidence_refs={"target_event_id": str(target.id), "assembly_id": str(assembly.id)},
        impact_estimate=3, source_worker="w2", now=now,  # sans confiance : jamais auto-accepté
    )
    assembly.docket_item_id = item.id
    stats.links += len(links)
    stats.assemblies += 1


def mirror_decision(db: Session, *, docket_item_id, decision: str) -> None:
    """Statut de l'assemblage = miroir de la décision du docket (archivé = refusé, report = inchangé)."""
    status = {"validated": "validated", "refused": "refused", "archived": "refused"}.get(decision)
    if status is None:
        return
    for assembly in db.scalars(select(ChainAssembly).where(ChainAssembly.docket_item_id == docket_item_id)):
        assembly.status = status


def _family(event_type: str) -> str:
    return event_type.split(".", 1)[0]


def _local_date(moment: datetime) -> str:
    return moment.astimezone(PARIS).date().isoformat()
