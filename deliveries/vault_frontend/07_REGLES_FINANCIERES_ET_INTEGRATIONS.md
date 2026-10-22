# Règles financières et intégrations

## Deux livres et bénéfice

Le serveur possède `vault.category_map`, consulté via GET categories. Les catégories vtc/bolt/uber etc. peuvent correspondre aux gains pro ; carburant, entretien, plateformes, assurance pro aux dépenses pro ; loyer, courses et sadaqa au personnel. La liste exacte et ses clés viennent du serveur. Une catégorie personnalisée non référencée n'acquiert pas automatiquement un livre.

Bénéfice professionnel = revenus pro − dépenses pro. Solde personnel = revenus perso − dépenses perso. Net du registre = total_income_cents − total_expense_cents de la période. Ce net global n'est ni le bénéfice pro ni le wallet réel. `weekly_business_profit` est la base canonique hebdomadaire pour Path. Ne pas refaire les formules à partir d'une liste paginée.

Le backend connaît les écritures inverses ; le frontend ne doit pas reclasser une annulation de dépense comme nouveau revenu commercial. Les résumés métier restent autoritaires. L'historique conserve les opérations originales et leurs corrections.

## Wallet

Dernier relevé = déclaration de soldes à une date. Prévu = relevé + mouvements retenus depuis selon backend. Afficher les deux, avec leurs dates. Les autres portefeuilles retournés à part ne sont pas ajoutés au total cash/banque/crypto. L'invite au-delà de 5 % d'écart vient de check_suggested et ne bloque pas l'app.

Liquidité de pression = cash + banque ; **crypto exclue**. Le total wallet peut inclure crypto pour visibilité, mais cela ne rend pas la situation sûre. La banque peut être à découvert. Aucun taux de change crypto récupéré ou estimé par l'interface V1.

Transfert interne cash → banque : actualiser les relevés. Aucun type transfer V1 ; ne pas créer un gain artificiel puis une dépense artificielle. Toute synchronisation bancaire est reportée.

## Pression

| Code API | Label UI | Plage |
|---|---|---|
| safe | Très faible | 0–20 |
| stable | Faible | 21–40 |
| attention | Modérée | 41–60 |
| pressure | Forte | 61–80 |
| critical | Critique | 81–100 |

Le backend calcule la formule du doc 11, publie snapshot et facteurs. Le frontend représente ce résultat ; il ne modifie pas un score pour le rendre plus encourageant. Minimum/confortable/optimal sont des sorties de calcul, pas trois missions actives. La pression informe le contexte de planification ; ne pas ajouter un moteur de priorités Daily dans Vault ni un raccourci qui force une mission VTC.

## Échéances et corrections

Une échéance n'est pas une dépense déjà payée. `mark-paid` fait la conversion de manière atomique avec la prochaine occurrence si applicable. DELETE désactive l'échéance, sans effacer le ledger. `handled` sur la pression exclut une obligation du calcul, sans remplacer l'enregistrement de paiement. Une semaine exceptionnelle désigne un lundi et modifie le contexte de calcul serveur ; montrer la raison et l'historique.

## Sadaqa / The Path

Path lit le profit hebdomadaire réel. Ses réglages (pourcentage et marge) restent chez Path ; Vault les affiche seulement. Donation confirmée dans Path → le service backend écrit la dépense Vault avec source path_sadaqa. Ne pas poster une deuxième dépense depuis l'écran Vault. Une correction ou annulation de don se fait depuis Path ; ne pas exposer de destination privée dans la note Vault. Le score de pression n'est pas une base de calcul sadaqa. Vault peut afficher « Ouvrir The Path » ; sans contrat de cible sadaqa exporté, ne pas inventer la cible due.

## Pulse et Vector

Ticket validé : une dépense Vault + lignes stock Pulse sélectionnées, écrites par le backend ; pas de communication directe entre apps. Session Vector : revenu/dépense déjà inscrits par son service backend apparaissent dans Vault ; l'interface ne recopie pas le total de session. Si une ligne est gérée par un module d'origine, respecter ses refus/corrections propres.

## Orchestration et tables

Tables concernées en lecture contractuelle : imperium_vault_transactions, weekly_finance_summaries, upcoming_expenses, pressure_snapshots, vault_wallet_snapshots, user_category_memory, extractions de reçus et corrections de pression. Aucune connexion SQL depuis le frontend. pgvector n'est pas une caisse. n8n orchestre les workflows externes ; les calculs CRUD déterministes existants utilisent les services backend. Le job weekly_profit est prévu lundi 00:30 UTC et peut être désactivé : computed_at est indispensable. Aucun changement de table par ce dossier.
