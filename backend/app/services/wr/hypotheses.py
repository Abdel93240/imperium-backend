"""WR P1 — passe d'hypothèses (spec WR §3.6, §9 P1 ; carte V22 ACT-WR-12), slot cloud `wr.hypothesis_pass`.

Entrée : le digest figé de la session (déjà filtré par sa whitelist : jamais de brut, de conversation ni de
document médical). Le modèle rend des hypothèses systémiques cross-domaines, un agenda de 30 questions au
plus, chacune notée de 0 à 100 pour sa pertinence, et des demandes de forage. Le CODE sert les forages, au
plus `wr.drill_max`, chacun noté dans `drill_log`, sur des vues prédéfinies seulement :

- `rollups` : agrégats W1 par jour sur 4 semaines, domaines nommés dans la requête (tous sinon) ;
- `events` : nombre d'events par type sur 4 semaines, types contenant un mot de la requête (jamais le
  contenu) ;
- `memories` : indisponible tant que la mémoire vectorielle est éteinte.

Puis un second appel rend la sortie finale. Les références qui n'existent ni dans le digest ni dans les
forages sont retirées (aucune preuve inventée). Une passe par digest (`wr_hypotheses`). Rien n'est
présenté ni appliqué ici : la conversation (P2) s'en servira.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.event import Event
from app.models.wr import WrDigest, WrHypothesis, WrRollupDaily
from app.services.ai import cloud
from app.services.params import get_parameter

SLOT = "wr.hypothesis_pass"
DOMAINS = ("imperium", "vault", "vector", "pulse", "path")
SCOPES = ("rollups", "events", "memories")
DRILL_DAYS = 28
PARIS = ZoneInfo("Europe/Paris")
DRILL_ROWS = 60
MAX_AGENDA = 30  # plafond de sécurité : la pertinence (seuil de la conversation) fait le tri
MAX_HYPOTHESES = 8

SYSTEM = (
    "Tu prépares la Weekly Review d'un système personnel (Imperium) qui suit la vie d'une seule personne : "
    "missions et projets (imperium), argent (vault), activité VTC (vector), santé et corps (pulse), pratique "
    "religieuse (path). Tu reçois le digest figé de la semaine : items du docket (propositions, anomalies, "
    "contradictions), agrégats par domaine (rollups), anomalies de signaux, état du plan.\n"
    "Ta mission :\n"
    "- systemic_hypotheses : des hypothèses qui RELIENT plusieurs domaines (par exemple une fatigue qui pèse "
    "sur le chiffre VTC puis sur la pression financière). Chacune cite ses preuves dans evidence_refs et porte "
    "une confiance de 0 à 100. Une hypothèse sur un seul domaine n'a d'intérêt que si elle est forte.\n"
    "- agenda : les questions utiles à poser à l'utilisateur pendant la revue (30 au plus), chacune avec "
    "l'enjeu (stake_fr), ses références et sa pertinence (relevance, 0 à 100 : combien la réponse changerait "
    "ta compréhension de la semaine ou le plan de la suivante ; une curiosité vaut peu). Ne gonfle pas les "
    "notes : seules les questions assez pertinentes seront posées, une à une. Pas de question dont la "
    "réponse est déjà dans le digest.\n"
    "- drill_requests : ce que tu veux vérifier avant de conclure (scope rollups = agrégats par jour sur 4 "
    "semaines ; events = nombre d'events par type ; memories = mémoire de long terme).\n"
    "Règles :\n"
    "- Références permises : l'id d'un item du docket, « signal:<signal_code>@<local_date> » pour une anomalie, "
    "« rollup:<domaine du rollup> », ou « drill:<numéro> » pour un résultat de forage. Rien d'autre.\n"
    "- N'invente aucun fait : tout ce que tu affirmes vient du digest ou des forages. Si les données sont "
    "minces, propose peu d'hypothèses, avec une confiance basse, et dis-le dans les questions.\n"
    "- Domaines : imperium, vault, vector, pulse, path (finance = vault, rides = vector, missions = imperium).\n"
    "- Tu écris en français, tutoiement, phrases courtes."
)


@dataclass
class PassStats:
    calls: int = 0
    drills: int = 0
    refs_dropped: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    tokens: list = field(default_factory=list)  # (entrée, sortie) par appel


def output_schema(drill_max: int) -> dict:
    refs = {"type": "array", "items": {"type": "string"}, "maxItems": 10}
    return {
        "type": "object", "additionalProperties": False,
        "required": ["systemic_hypotheses", "agenda", "drill_requests"],
        "properties": {
            "systemic_hypotheses": {"type": "array", "maxItems": MAX_HYPOTHESES, "items": {
                "type": "object", "additionalProperties": False,
                "required": ["statement_fr", "domains", "evidence_refs", "confidence"],
                "properties": {"statement_fr": {"type": "string"},
                               "domains": {"type": "array", "items": {"type": "string", "enum": list(DOMAINS)}},
                               "evidence_refs": refs, "confidence": {"type": "integer"}}}},
            "agenda": {"type": "array", "maxItems": MAX_AGENDA, "items": {
                "type": "object", "additionalProperties": False, "required": ["question_fr", "stake_fr", "refs", "relevance"],
                "properties": {"question_fr": {"type": "string"}, "stake_fr": {"type": "string"}, "refs": refs,
                               "relevance": {"type": "integer"}}}},
            "drill_requests": {"type": "array", "maxItems": drill_max, "items": {
                "type": "object", "additionalProperties": False, "required": ["query", "scope", "reason_fr"],
                "properties": {"query": {"type": "string"}, "scope": {"type": "string", "enum": list(SCOPES)},
                               "reason_fr": {"type": "string"}}}},
        },
    }


def run_pass(db: Session, *, user: User, digest: WrDigest) -> tuple[WrHypothesis | None, PassStats]:
    """Passe d'hypothèses du digest ; None si le slot est éteint. Lève cloud.CloudError si l'appel échoue."""
    stats = PassStats()
    existing = db.scalar(select(WrHypothesis).where(WrHypothesis.digest_id == digest.id))
    if existing is not None:
        return existing, stats
    if cloud.slot_mode(db, SLOT) != "live":
        return None, stats
    drill_max = int(get_parameter(db, "wr.drill_max", default=6))
    digest_text = json.dumps(digest.digest, ensure_ascii=False)
    first = _call(db, digest, f"Digest de la semaine :\n{digest_text}", output_schema(drill_max), stats)
    drill_log: list[dict] = []
    results: list[dict] = []
    for index, request in enumerate(first.output.get("drill_requests", [])[:drill_max], start=1):
        served = _drill(db, user, digest, request)
        results.append({"ref": f"drill:{index}", "query": request.get("query"), "scope": request.get("scope"),
                        "result": served})
        drill_log.append({"query": request.get("query"), "scope": request.get("scope"),
                          "reason": request.get("reason_fr"), "chunks_returned": len(served.get("rows", []))})
    stats.drills = len(drill_log)
    final = first
    if results:
        final = _call(db, digest, (
            f"Digest de la semaine :\n{digest_text}\n\nTa première passe :\n"
            f"{json.dumps(first.output, ensure_ascii=False)}\n\nRésultats des forages :\n"
            f"{json.dumps(results, ensure_ascii=False)}\n\n"
            "Rends maintenant ta sortie finale en tenant compte des forages. drill_requests doit être vide."
        ), output_schema(0), stats)
    output = _clean(final.output, _known_refs(digest.digest, len(results)), stats)
    row = WrHypothesis(user_id=user.id, digest_id=digest.id, output=output, drill_log=drill_log,
                       model_used=final.model, prompt_tokens=_total(stats, 0), output_tokens=_total(stats, 1))
    db.add(row)
    db.flush()
    return row, stats


def hypothesis_on_digest_job(ctx, window) -> None:
    """Job `wr.hypothesis_on_digest` : passe d'hypothèses du digest qui vient d'être assemblé."""
    event = ctx.db.scalar(select(Event).where(Event.id == ctx.trigger_ref)) if ctx.trigger_ref else None
    digest_id = (event.payload or {}).get("digest_id") if event is not None else None
    digest = ctx.db.get(WrDigest, digest_id) if digest_id else None
    user = ctx.db.get(User, digest.user_id) if digest is not None else None
    if user is None:
        ctx.items_in = ctx.items_out = 0
        ctx.detail = {"skipped": "no_digest"}
        return
    row, stats = run_pass(ctx.db, user=user, digest=digest)
    ctx.items_in, ctx.items_out = 1, int(row is not None)
    ctx.detail = {"skipped": "slot_off"} if row is None else {
        "hypotheses_id": str(row.id), "calls": stats.calls, "drills": stats.drills,
        "refs_dropped": stats.refs_dropped}


def _call(db: Session, digest: WrDigest, prompt: str, schema: dict, stats: PassStats) -> cloud.CloudResult:
    result = cloud.structured(db, slot_code=SLOT, app_name="imperium", system=SYSTEM, user=prompt, schema=schema,
                              related_entity_type="wr_digest", related_entity_id=digest.id)
    stats.calls += 1
    stats.cost_usd += result.cost_usd or 0
    stats.latency_ms += result.latency_ms
    stats.tokens.append((result.input_tokens, result.output_tokens))
    return result


def _total(stats: PassStats, index: int) -> int | None:
    values = [pair[index] for pair in stats.tokens]
    return sum(values) if values and all(value is not None for value in values) else None


def _drill(db: Session, user: User, digest: WrDigest, request: dict) -> dict:
    words = re.findall(r"[a-z_]{3,}", str(request.get("query", "")).lower())
    first_day = digest.window_to - timedelta(days=DRILL_DAYS - 1)
    scope = request.get("scope")
    if scope == "rollups":
        query = select(WrRollupDaily.domain, WrRollupDaily.local_date, WrRollupDaily.metrics).where(
            WrRollupDaily.user_id == user.id, WrRollupDaily.local_date >= first_day,
            WrRollupDaily.local_date <= digest.window_to)
        domains = sorted(set(db.scalars(select(WrRollupDaily.domain).where(WrRollupDaily.user_id == user.id))))
        named = [domain for domain in domains if domain in words]
        if named:
            query = query.where(WrRollupDaily.domain.in_(named))
        rows = db.execute(query.order_by(WrRollupDaily.local_date, WrRollupDaily.domain).limit(DRILL_ROWS)).all()
        return {"rows": [{"domain": domain, "local_date": day.isoformat(), "metrics": metrics}
                         for domain, day, metrics in rows]}
    if scope == "events":
        conditions = [Event.event_type.contains(word) for word in words] or [Event.event_type.is_not(None)]
        rows = db.execute(
            select(Event.event_type, func.count(), func.min(Event.occurred_at), func.max(Event.occurred_at))
            .where(Event.user_id == user.id, or_(*conditions),
                   Event.occurred_at >= datetime.combine(first_day, time.min, tzinfo=PARIS),
                   Event.occurred_at < datetime.combine(digest.window_to + timedelta(days=1), time.min, tzinfo=PARIS))
            .group_by(Event.event_type).order_by(func.count().desc()).limit(DRILL_ROWS)
        ).all()
        return {"rows": [{"event_type": event_type, "count": count, "first": first.isoformat(),
                          "last": last.isoformat()} for event_type, count, first, last in rows]}
    return {"rows": [], "unavailable": "mémoire de long terme éteinte"}


def _known_refs(content: dict, drills: int) -> set[str]:
    refs = {f"drill:{index}" for index in range(1, drills + 1)}
    for entries in (content.get("docket") or {}).values():
        refs.update(str(entry.get("id")) for entry in entries)
    refs.update(f"signal:{row.get('signal_code')}@{row.get('local_date')}" for row in content.get("anomalies") or [])
    refs.update(f"rollup:{domain}" for domain in content.get("rollups") or {})
    return refs


def _clean(output: dict, known: set[str], stats: PassStats) -> dict:
    def keep(refs: list) -> list[str]:
        kept = [ref for ref in refs if ref in known]
        stats.refs_dropped += len(refs) - len(kept)
        return kept

    hypotheses = [{**item, "evidence_refs": keep(item.get("evidence_refs", [])),
                   "confidence": max(0, min(100, int(item.get("confidence", 0))))}
                  for item in output.get("systemic_hypotheses", [])[:MAX_HYPOTHESES]]
    agenda = [{**item, "refs": keep(item.get("refs", [])), "relevance": max(0, min(100, int(item.get("relevance", 50))))}
              for item in output.get("agenda", [])[:MAX_AGENDA]]
    return {"systemic_hypotheses": hypotheses, "agenda": agenda, "drill_requests": []}
