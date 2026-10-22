# Recette et tests à produire pour le frontend

Les scripts de cette livraison ont leurs tests pytest dans `backend/tests/test_vault_frontend_kit.py`. Ils vérifient export, exemples, contenu ZIP et serveur. Ils ne prouvent pas qu'une application Android a été générée ni qu'un backend déployé est disponible. Pour chaque nouvelle fonctionnalité/correction Python, conserver la règle utilisateur : test correspondant dans tests/, aucun test existant cassé.

## Scénarios indispensables

| Cas | Action | Résultat attendu |
|---|---|---|
| Premier lancement | Ouvrir sans relevé | « Aucun relevé », CTA, pas faux 0 € |
| Dépense décimale | Saisir 45,20 | amount_cents=4520, expense |
| Validation | Entrer zéro, négatif ou plus de deux décimales | Champ invalide, saisie conservée |
| Gain | Ajouter 125 € pro | income, catégorie référentiel, succès après serveur |
| Deux appuis | Soumettre deux fois | Une intention et même clé |
| Réseau perdu après envoi | Reprendre transaction | Même clé/corps, une seule écriture |
| Reprise sans idempotence | Créer échéance puis timeout | Résultat à vérifier, pas création automatique répétée |
| Catégorie | Suggestion inconnue/invalide | Choix manuel visible, pas auto-classement |
| Apprentissage échoue | Transaction réussie, confirm échoue | Transaction reste enregistrée, aucun renvoi de création |
| Pagination | Plus de 200 lignes | Suite correcte, pas total global de page |
| Livre | Catégorie inconnue | Non classée ; pas classification inventée |
| Bornes temporelles | Minuit et changement d'heure | Fuseau conservé, période sans doublon |
| Relevé | Banque négative et cash positif | Découvert accepté, total lisible |
| Crypto | Solde crypto important, cash faible | Crypto visible, score serveur inchangé localement |
| Transfert interne | Cash déposé en banque | Nouveau relevé, aucun revenu fictif |
| Pression | 0,20,21,40,41,60,61,80,81,100 | Labels/bornes exacts et score du serveur |
| Pression absente | Échec GET | Carte indisponible, pas score 0 |
| Correction de contexte | Report/handled/semaine exceptionnelle | Réponse recalculée, raison visible, révocation possible |
| Échéance | Déclarer payée récurrente | Une dépense et next_occurrence du serveur |
| Déjà payé | Deuxième mark-paid | 409 traité, pas deuxième transaction |
| Désactivation | DELETE échéance | Désactivée, pas « payée » sans paid_at |
| Correction transaction | Changer montant avec raison | Original conservé + inverse + corrigée |
| Annulation | Reverse puis recharger | Réponse conservée, aucun hard delete |
| Don Path | Essayer correction Vault | Redirection/erreur gérée, pas double don |
| OCR permission | Refuser caméra | Formulaire manuel utilisable |
| OCR fichier | Vide, >25 Mio, format refusé | Erreur claire, pas succès |
| OCR service KO | Upload renvoie failed | Message 10 s, retour, pas dépense |
| OCR total incertain | Montant absent | Validation bloquée jusqu'à correction |
| Pulse rien coché | Valider ticket avec stock_lines=[] | Une dépense, zéro ajout stock |
| Pulse sélection | Deux lignes cochées | Exactement lignes sélectionnées transmises |
| OCR répété | Même validation après timeout | Même clé, pas dépense en double |
| Bénéfice | Dernière semaine close différente de courante | Dates exactes, aucune extrapolation |
| Auth expire | Plusieurs cartes demandent refresh | Renouvellement centralisé, pas boucle |
| Déconnexion | Cache et brouillons sensibles | Isolation sécurisée, aucun token en log |
| Tablette | Portrait, paysage, clavier ouvert | Action et champs accessibles, aucun contenu caché |
| Accessibilité | TalkBack et grande police | Labels, ordre de lecture, pas couleur seule |
| Cache ancien | Réseau absent | Horodatage et statut offline visibles |
| App tuée | Relancer pendant pending | Brouillon restauré avec même clé |
| Dépendance absente | Voix/conseil non raccordé | Fonction indisponible annoncée, pas résultat simulé en mode réel |

## Recette de la bulle flottante

- Activation dans VAU-12 : explication puis permission système ; refus conserve toutes les fonctions de l'app.
- Déplacement, ouverture, fermeture et désactivation : panneau utilisable sans recouvrir durablement les commandes d'une autre app ; désactivation retire la bulle.
- Saisie gain/dépense : mêmes validations, catégories et portefeuille que VAU-02/03 ; double appui et timeout gardent la même Idempotency-Key.
- Hors réseau : pending visible, brouillon conservé ; aucun montant ajouté aux totaux confirmés.
- Reprise de l'app, rotation et révocation de permission : aucune deuxième transaction, aucun affichage automatique de données financières sur écran verrouillé.

En production, tester contre un environnement de test et des données fictives. Ne jamais déclencher de paiement/don réel pour une démonstration. Ne pas lancer des tests DB destructifs dans le workspace partagé sans vérifier leur isolation. Mode démo clairement marqué, aucun appel d'écriture réel.
