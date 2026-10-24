# 01 — Vision et périmètre

The Path aide une seule personne à pratiquer avec moins de friction : voir la prochaine prière, confirmer ce qu'elle a fait, suivre le jeûne, la sadaqa, le Coran et les invocations. L'utilisateur conduit souvent ; les gestes utiles doivent être rapides, lisibles, utilisables à la voix seulement après validation explicite. Aucune fonction ne prononce de jugement religieux.

## Règles absolues

- Aucun acte religieux n'est déclaré accompli automatiquement, à partir du GPS, de l'heure, d'une notification ou d'une inférence IA.
- L'intention de jeûner, le besoin de ghusl et tout état de pratique viennent de l'utilisateur.
- Messages neutres, sans reproche ni pression. Notifications discrètes et configurables quand le backend les permettra.
- Le backend est la vérité ; le cache local est daté et marqué. n8n orchestre, il ne devient pas une API mobile.
- Une seule mission Imperium peut être active ; The Path peut demander une replanification, jamais créer une seconde mission localement.
- The Path possède les paramètres de sadaqa et les dons ; The Vault fournit le bénéfice réel et reçoit la dépense confirmée. Aucun montant n'est inventé par le client.
- Données religieuses très privées. Aucune télémétrie qui contient prière, mosquée, localisation ou texte libre.

## Périmètre de génération

**V1 raccordable :** tableau de bord, cinq prières, jeûne, sadaqa, ghusl et adresses, adhkar, Coran, invocations, mosquées enregistrées et détail, réglages, calendrier hégirien et événements personnels, habitudes/check-ins historiques. Les routes correspondantes existent dans le snapshot API.

**UX préparée mais non raccordée :** recherche/synchronisation réseau MAWAQIT, rappels configurables, privacy gate dédié, transcription vocale Path de bout en bout, score Path et guidance IA spécialisée. Montrer une explication ou un état désactivé, sans simuler une écriture.

**V2/V3 :** pratiques facultatives avancées, éventuels contenus religieux enrichis, sources calendaires externes. Garder ces évolutions hors du parcours principal V1.

## Critère de réussite

En moins de quelques gestes, l'utilisateur voit les horaires avec leur source, enregistre explicitement une prière, un jeûne ou un don, et comprend si cette action a été confirmée par le serveur. Il peut corriger un état sans perdre l'historique canonique. Une tablette affiche deux colonnes là où cela réduit les allers-retours.
