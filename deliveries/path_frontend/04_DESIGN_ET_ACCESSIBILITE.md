# 04 — Design, tablette et accessibilité

Suivre les tokens `59_DESIGN_SYSTEM_V1_DRAFT.md`, `60_DESIGN_SYSTEM_TOKENS_KT.md` et les composants `61`–`62`. The Path conserve la cohérence visuelle du système commun ; aucune palette ou typographie religieuse inventée écran par écran.

- **Téléphone :** cartes lisibles, une action principale par vue, boutons grands et espacés. Barre/onglets selon la navigation commune.
- **Tablette :** rail de navigation, tableau de bord à deux colonnes, liste à gauche et détail à droite pour mosquées, invocations et réglages. Les formulaires restent courts.
- **En conduite :** ne demander aucune saisie longue ; préférer une lecture rapide et différer les actions complexes. Les actions vocales exigent affichage de la transcription et confirmation avant écriture.
- **Hiérarchie :** prochaine prière et état personnel en haut ; source des horaires toujours visible ; sadaqa en euros et semaines explicites ; bannière ghusl claire sans dramatisation.
- **États :** live, cache avec date, stale, pending, syncing, synced, failed, conflict. Ces libellés servent aussi aux lecteurs d'écran.
- **Accessibilité :** cibles tactiles ≥ 48 dp, police dynamique, contraste lisible, focus logique, TalkBack décrivant statut + action. Ne jamais coder le statut uniquement par couleur.
- **Arabe :** alignement et direction RTL du texte arabe, mais boutons français dans l'ordre de lecture français ; police adaptée, vocalisation conservée si fournie. Traduction et source séparées. Pas de texte sacré fabriqué par placeholder.
- **Temps :** `Europe/Paris` pour les jours de suivi et les horaires affichés ; l'heure effective conserve son fuseau. Compte à rebours mis à jour localement à partir du timestamp serveur sans inventer de nouvel horaire.
- **Qibla :** valeur en degrés donnée par le backend ; la boussole dépend d'un capteur disponible et d'une permission adéquate. Afficher le nombre ou une indication statique si le capteur est absent.
