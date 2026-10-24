# 02 — Catalogue fonctionnel

Légende : **API** = route présente dans le dépôt ; **UI seule** = représentation sans écriture ; **à venir** = contrat absent. API ne garantit pas l'activation de l'environnement.

| Domaine | Fonctions attendues | État et règle d'interface |
|---|---|---|
| Accueil | date hégirienne, prochaine prière/compte à rebours, cinq statuts, jeûne, sadaqa, ghusl, adhkar, reprise Coran, qibla, bannières | API `dashboard` ; le compte à rebours absent sur un jour historique reste absent |
| Prières | cinq prières obligatoires, horaires, source MAWAQIT ou calcul, marquer accompli/non marqué, effacer, date/heure, note, correction avec version | API `prayers` ; aucune confirmation implicite ; statuts neutres |
| Jeûne | type lundi/jeudi, jours blancs, Ramadan, personnel, temporaire ; démarrer, finir, rompre, annuler une erreur ; historique et fenêtre suhoor/iftar | API `fasts`, `fasting/state` ; confirmation explicite ; Pulse lit la contrainte backend |
| Sadaqa | bénéfice hebdomadaire Vault, %, marge, cible, report, restant, dons, destination, portefeuille, annulation, reprise transfert Vault | API `sadaqa/*` ; résultat et état `vault_status` visibles ; montants backend seuls font foi |
| Ghusl | activer un besoin, afficher mission/replan, marquer terminé, conserver état et date | API `ghusl/*` ; jamais déclenché par supposition |
| Adresses ghusl | ajouter, modifier, supprimer, adresse par défaut, coordonnées facultatives appariées | API `ghusl-addresses` ; localisation seulement avec permission |
| Adhkar | suggestions, routines (8 actives max), compteur +1, incrément voix validé, reset avec compte attendu, édition/archivage | API `adhkar/*` ; pas d'incrément silencieux |
| Coran | point de reprise page/sourate/juz, objectif journalier, plans, khatm, confirmation de recul | API `quran/*` ; aucune progression inférée |
| Invocations | bibliothèque personnelle par situation, matin/soir, favoris, coche du jour, arabe + traduction + source + audio HTTPS facultatif | API `invocations/*` ; contenu saisi/validé par l'utilisateur, pas de source IA implicite |
| Mosquées | liste, saisie manuelle, mosquée de référence unique, détail horaires/qualité/qibla, décalages adhan/iqama | API `mosques/*` ; recherche MAWAQIT et sync réseau à venir |
| Calendrier | date hégirienne, jours blancs, Ramadan, fêtes, prévisions J/J+1, confirmation observation, événements personnels | API `calendar/*` ; distinguer prédit et confirmé |
| Réglages | méthode de calcul, madhhab, ville/coordonnées, pourcentage et marge sadaqa, routines | API `settings`, `sadaqa/settings` ; afficher valeurs retournées et version |
| Habitudes historiques | habitudes et check-ins Path anciens, détail et statistiques | API `today`, `habits`, `check-ins`, `stats/summary` ; zone secondaire, ne pas les confondre avec les domaines structurés |
| Rappels, voix, IA | rappels, transcription et conseils spécifiques | à venir ; aucun appel direct à n8n ou modèle externe |

## Priorité de production V1

1. Auth, tableau de bord et états réseau.
2. Prières, jeûne, sadaqa et ghusl.
3. Adhkar, Coran, invocations.
4. Mosquées, réglages et calendrier.
5. Habitudes historiques seulement si leur usage reste souhaité ; elles ne remplacent pas les écrans métier Path.
