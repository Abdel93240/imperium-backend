# 03 — Écrans et parcours

Navigation : entrée principale `PAT-01`; accès de premier niveau à Culte `PAT-12`, Mosquées `PAT-09`, Adresses `PAT-10` et Réglages `PAT-11`. Sur téléphone : navigation compacte et feuilles. Sur tablette : rail et panneau de détail, sans dupliquer un formulaire ouvert. Les ID stables viennent du document 41 §19.

| Écran | Contenu et actions | États indispensables |
|---|---|---|
| PAT-01 Dashboard | prochain horaire, cinq lignes prière, date hégirienne, qibla, bannières, cartes jeûne/sadaqa/ghusl/adhkar/Coran ; actions rapides | chargement, vide, cache daté, source horaires, erreur partielle, mise à jour après mutation |
| PAT-02 Prayer Mark | nom, horaire/source, statut neutre, heure effective facultative, note, boutons Accomplie / Non marquée / Effacer | confirmation explicite, changement avec `base_version`, conflit et état serveur, rappel adhkar optionnel |
| PAT-03 Sadaqa Donation | cible/restant, euros→centimes, destination, date, note, portefeuille, option Vault ; confirmation et reçu | donation enregistrée, transfert Vault `recorded/pending/not_requested`, retry distinct, annulation confirmée |
| PAT-04 Ghusl Required | état, début, prochaine prière, mission/replan, bouton Activer ou Terminé | état déjà actif, replan `pending/requested/no_open_day/replan_in_progress/failed`, conflit |
| PAT-05 Fasting Action | type, horaires suhoor/iftar, Démarrer, Finir, Rompre, Annuler erreur, historique | aucun jeûne, actif, terminé, rompu ; dialogue de confirmation pour rupture/annulation |
| PAT-06 Adhkar Counter | routine, gros +1, cible et compteur, éventuellement arabe/traduction si contenu vérifié, reset | retour confirmé, pending visuel, conflit de reset, limite 8 routines actives ; PAT-06b config |
| PAT-07 Quran Progress | page actuelle, reprise, objectif, plan, saisie page/sourate/juz via PAT-07b, khatm | page 1–604, recul confirmé, conflit version, khatm seulement si disponible |
| PAT-08 Mosque Detail | cinq horaires, source principale, cache MAWAQIT/qualité/date, horaires calculés, qibla, référence | `fresh/stale/expired/missing`, message fallback, aucune fausse synchronisation |
| PAT-09 Mosques | liste, une référence, ajout PAT-09b, édition, suppression, décalages | vide, coordonnées par paire, conflit version, GPS facultatif |
| PAT-10 Ghusl Addresses | liste, ajout PAT-10b, défaut, édition, suppression | vide, permission GPS refusée, conflit version |
| PAT-11 Settings | méthode, madhhab, ville, liens sadaqa %, mosquées, adresses, routines, objectif Coran | valeurs supportées du serveur, changement sadaqa différé, conflit de version |
| PAT-12 Worship | onglets Coran, Invocations, Dhikr, Routines, Favoris ; invocations du jour matin/soir et par situation | texte arabe RTL, traduction/source, audio absent, contenu vide, favori/coche confirmé |

## Parcours obligatoires

1. **Prière :** ouvrir PAT-01 → toucher une ligne → PAT-02 → choisir le statut → envoyer avec clé d'idempotence → remplacer la ligne depuis la réponse. Si déjà marqué, joindre la version lue. Un 409 ouvre le statut actuel et propose une nouvelle action.
2. **Jeûne :** choisir type → confirmer Démarrer → afficher fenêtre et bannière depuis `fasting/state`. Finir, rompre et annuler sont des actions distinctes. Ne jamais déduire l'intention d'un jour blanc.
3. **Don :** saisir un montant positif → confirmer → lire `donation`, `week` et warnings. Si Vault est `pending`, afficher une reprise ; ne pas créer soi-même une transaction Vault. L'annulation affiche son impact de contrepassation.
4. **Ghusl :** Activer → afficher l'état `required` même si la replanification Imperium est encore en attente → Terminé avec l'ID de cet état.
5. **Coran :** ouvrir le dernier point → choisir exactement page, sourate ou juz → confirmer une régression si demandée par le backend → ne proposer Khatm que lorsque `khatm_available`.
6. **Calendrier :** afficher J et J+1 pour un événement prédit ; après confirmation utilisateur, recharger les événements et ne laisser que la date confirmée.
7. **Mosquée :** définir explicitement la référence ; la liste ne modifie jamais la référence par proximité GPS. Détail : source et fraîcheur visibles en permanence.

Chaque écran a un bouton retour cohérent, des libellés d'action distincts, un état vide utile et une sauvegarde de brouillon non canonique lors d'une interruption.
