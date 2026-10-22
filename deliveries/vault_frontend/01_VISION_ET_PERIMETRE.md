# Vision et périmètre

The Vault répond à quatre questions : combien ai-je réellement, combien mon activité me rapporte-t-elle, qu'est-ce qui doit bientôt sortir et pourquoi ma situation est-elle tendue ? C'est un radar financier personnel. L'utilisateur décide ; Vault observe et rapporte.

L'utilisateur travaille en VTC, parfois très longtemps. Saisir une dépense doit être rapide, garder un brouillon ne doit jamais perdre son montant, et lire le bilan de la semaine ne doit pas demander d'interpréter un dashboard complexe.

## Règles produit

- Deux livres : professionnel et personnel. Le backend déduit le livre de la catégorie ; l'interface l'affiche.
- Revenus, dépenses, bénéfice et argent disponible sont quatre notions distinctes.
- Aucune écriture bancaire, aucun investissement conseillé automatiquement, aucun blocage de dépenses, aucune notification culpabilisante.
- Aucun montant inventé : une donnée absente reste absente. Un vrai zéro reste zéro. Une projection reste identifiée.
- Tous les calculs canoniques et décisions viennent du backend. PostgreSQL est la vérité structurée ; l'app collecte et affiche.
- Imperium conserve le pilotage et l'unique mission active. Vault ne crée pas sa propre liste de missions.
- La sadaqa est gérée dans The Path sur une base de bénéfice professionnel réel.
- Le registre des transactions est append-only. Corriger ou annuler conserve la trace originale.
- Montants en EUR en V1. La crypto est une contre-valeur EUR saisie manuellement.
- Android natif est la cible documentée ; une prévisualisation web éventuelle est un support de démonstration, pas un changement de cible produit.

## V1 complète et disponibilité

Construire les 12 écrans documentés. Une route codée peut rester inutilisable si un service OCR, un modèle local, une migration ou un job est désactivé. Afficher cet état. Pour une capacité sans contrat, préparer une interface désactivée ou un point d'intégration ; ne pas inventer une route ni un succès.

Ne pas ajouter de gestion d'entreprise multi-utilisateur, comptabilité fiscale certifiée, synchronisation bancaire, trading, automatisation Bolt, budgets imposés ou gamification de la dépense. Ils ne font pas partie de cette livraison.
