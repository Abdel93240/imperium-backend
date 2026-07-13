# VAGUE 33 — Vector advisory (le halo s'allume) — lot de 1

**Composition** : ACT-VEC-08 seul. La bascule shadow→advisory est une DÉCISION UTILISATEUR
sur le rapport de V32 (rollout gravé spec §10.7). Durée : 14 j.

```
id: ACT-VEC-08   nom_fr: Mode advisory (halo vert/rouge/blanc en course réelle)
domaine: vector   classe: ia_advisory   echelon_audace: 4   statut: NOT_CODED
bascule_exacte: vtc_assistant_mode='advisory'
prerequis_activation: [ACT-VEC-05 (≥14 j shadow), ACT-VEC-07 (rapport lu et tranché)]
protocole_terrain: sessions réelles : halo coloré consultatif ; abstention honnête sur
  donnée douteuse (jamais une couleur confiante sur du douteux) ; cas serrés COLORÉS
  (l'abstention n'est pas un confort) ; acceptations contre-halo marquées exploration ;
  14 j
critere_succes: le halo aide (ressenti terrain + marge loggée) ; zéro clignotement
  (upgrade-only) ; taux d'abstention raisonnable et expliqué (abstained_reason)
rollback: vtc_assistant_mode='shadow' (une variable — le pipeline continue de logger)
source: spec Vector §3.6/§3.7, §10.7
prompt_codex: « Basculer en advisory ; première session observée ; consigner date +
  ressenti + taux d'abstention. »
observations: PREMIÈRE IA-ML advisory embarquée du système — le rollback est indolore
  par construction, s'en servir au moindre doute (R7)
```
