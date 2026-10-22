# Bulle flottante de saisie rapide — V1

Source : `sources/docs_master/63_FRONTEND_ARCHITECTURE_V1.md`, section 10. La décision utilisateur prévoit une bulle Vault déplaçable au-dessus des autres apps, sur le principe de la bulle Bolt. Ce n'est ni un widget d'écran d'accueil, ni une notification de conversation Android Bubbles.

## Activation et fonctionnement

Dans VAU-12, ajouter une préférence **locale à l'appareil** « Bulle de saisie rapide ». Expliquer son utilité avant de demander la permission `SYSTEM_ALERT_WINDOW` (« Afficher par-dessus les autres apps »). Aucun appel PATCH `/api/vault/settings` : les réglages métier serveur restent en lecture seule. Le refus et la révocation de permission laissent toute l'app utilisable. Désactiver retire la bulle et le panneau. L'implémentation Android devra respecter les contraintes de service et d'arrière-plan de sa version cible.

Un appui ouvre un panneau court : Gain / Dépense, montant, libellé, catégorie préremplie et modifiable, portefeuille, bouton de confirmation. Le livre pro/perso est déduit du référentiel serveur. Réutiliser les modèles, validations, brouillons et repository des écrans VAU-02/03, avec possibilité d'ouvrir le formulaire complet. La date par défaut est celle de la saisie explicite ; montrer la date du brouillon lors d'une reprise tardive.

## Autorité et réseau

Le panneau lit l'état à l'ouverture ; aucun rafraîchissement périodique dédié. L'envoi utilise `POST /api/imperium/vault/transactions` et la même `Idempotency-Key` stable que l'intention enregistrée. Afficher `pending` jusqu'à confirmation backend. Un double appui, une fermeture du panneau ou une reprise dans l'app ne crée pas une nouvelle intention. Hors réseau, garder le brouillon et son état ; ne pas changer les chiffres canoniques.

Les suggestions de catégorie utilisent le parcours serveur existant : table/mémoire, puis rôle local pour libellé inconnu selon disponibilité. Aucun moteur financier dans la bulle. Les commandes vocales suivent les limites du document 06 ; ne pas promettre un pipeline connecté absent.

## Présentation et confidentialité

La bulle reste discrète, déplaçable et refermable, avec cible accessible et libellé TalkBack. Aucun solde permanent sur la bulle. Masquer les informations sensibles quand l'appareil est verrouillé. Conserver les brouillons dans le stockage sécurisé commun, pas dans un second registre. Pour un chauffeur occupé, privilégier la saisie courte et la vérification à l'arrêt.

Cette surface transversale complète les 12 écrans existants. Elle n'ajoute aucune table ni route backend et appartient au périmètre V1 documenté.
