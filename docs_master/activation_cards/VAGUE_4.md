# VAGUE 4 — Vault boucle complète

**Composition** : ACT-VLT-06, ACT-VLT-09, ACT-VLT-10, ACT-VLT-08. Ferme la boucle
finance : objectifs quotidiens, profit hebdo, base sadaqa, alertes. Durée : 7 j
(un cycle hebdo complet + notifiant).

```
id: ACT-VLT-06    nom_fr: Objectifs journaliers minimum/comfortable/optimal
domaine: vault    classe: det_lecture   echelon_audace: 1   statut: NOT_CODED
bascule_exacte: flag vault_daily_targets_enabled=true (exposés dans la réponse pressure)
prerequis_activation: [ACT-VLT-05, ACT-VLT-04]
protocole_terrain: 3 cibles affichées chaque matin ; warning si minimum > capacité
  réaliste ; 2-3 j
critere_succes: cibles arithmétiquement justes (obligations/jours restants/capacité) et
  actionnables
rollback: flag=false
source: doc 11 §349-409, GAP_vault gap n°5
prompt_codex: « Activer les targets ; smoke : 3 cibles + warning sur fixture ; consigner. »
observations: consommé plus tard par le plan (doc 52 §8.2 CAT 2), jamais par la sélection
  quotidienne (Q7)
```

```
id: ACT-VLT-09    nom_fr: Profit hebdo business (job lundi 00:30)
domaine: vault    classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: UPDATE job_definitions SET enabled=true WHERE code='weekly_profit_0030';
prerequis_activation: [ACT-SYS-06, ACT-VLT-02]
protocole_terrain: lundi : ligne weekly_finance_summaries écrite ; comparer au calcul
  manuel ; observer 2 lundis
critere_succes: 2 calculs consécutifs exacts (business seul, séparé du personnel)
rollback: job disabled (lignes écrites conservées)
source: doc 42 §11/§16, FINDINGS Q9/DV-3, F2-16, N8N_INVENTORY §B (job runner, PAS n8n)
prompt_codex: « Activer weekly_profit ; smoke : run manuel sur semaine fixture ;
  consigner. »
observations: Q9 (qui crée la table) résolu de fait par la mini-passe Vault ; PAS un event
  (doc 77 : les faits notables = profit_target.set/reached/missed, V2 catalogue)
```

```
id: ACT-VLT-10    nom_fr: Base sadaqa exposée à Path (weekly_business_profit)
domaine: vault    classe: det_lecture   echelon_audace: 1   statut: NOT_CODED
bascule_exacte: flag sadaqa_basis_enabled=true (contrat de lecture Path → profit hebdo)
prerequis_activation: [ACT-VLT-09]
protocole_terrain: Path lit la base et affiche le montant suggéré ; 2-3 j
critere_succes: base lue = dernier profit hebdo réel ; aucun lien finance automatique
  (l'accomplissement sadaqa reste DÉCLARÉ, doc 77 worship.sadaqa.given)
rollback: flag=false
source: doc 41 §9.2/§16.2, doc 11 §531-560, GAP_vault gap n°7
prompt_codex: « Activer le contrat de lecture ; smoke : GET base = profit fixture ;
  consigner. »
observations: —
```

```
id: ACT-VLT-08    nom_fr: Alertes échéances (7 jours / overdue)
domaine: vault    classe: notifiant   echelon_audace: 3   statut: NOT_CODED
bascule_exacte: UPDATE job_definitions SET enabled=true WHERE code='vault_alerts_daily';
prerequis_activation: [ACT-VLT-04, ACT-SYS-07]
protocole_terrain: échéance à J-7 → notification ; overdue → notification ; 7 j
critere_succes: chaque échéance réelle notifiée UNE fois, au bon moment, zéro bruit
rollback: job disabled
source: doc 42 §382-388, GAP_vault gap n°3
prompt_codex: « Activer vault_alerts ; smoke : fixture J-7 → notify() ; consigner. »
observations: premier NOTIFIANT métier après la notification de test V1 — surveiller le
  taux de bruit (R7)
```
