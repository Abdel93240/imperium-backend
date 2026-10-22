# 06 — Hors ligne, voix, permissions et confidentialité

## File locale

Le client peut conserver des brouillons de session, gain, dépense, dépose,
retour, offre et note vocale. Un brouillon n'est jamais une écriture canonique.
Chaque entrée locale porte : id local, type, cible, body, date de création,
clé d'idempotence si supportée, version lue si nécessaire, statut et dernier échec.
États : `pending`, `syncing`, `synced`, `failed`, `conflict`, `cancelled`.
Ce modèle de file est interne au client, pas une nouvelle enveloppe API.

Reprise réseau : authentifier, relire l'état canonique, synchroniser les actions
dépendantes dans l'ordre, remplacer les références locales par l'id serveur
confirmé. Un démarrage en attente doit aboutir avant ses écritures ; une clôture
attend les écritures précédentes. Ne pas rejouer à l'aveugle une mutation sans
idempotence déclarée : lire d'abord son résultat et résoudre le conflit.

Afficher le nombre d'actions en attente et leur date. Autoriser édition/annulation
uniquement pour les actions encore locales. Après acceptation backend, l'action
se corrige par le contrat métier disponible. Une annulation locale après timeout
n'annule pas forcément une opération déjà reçue par le serveur.

## Cache

Dernière session, KPIs et conseil peuvent être affichés avec timestamp et
mention « Dernier état connu ». Pas de nouveau scoring local, pas de faux signal
live, pas de clôture annoncée définitive sans confirmation. Les valeurs en attente
ne sont pas ajoutées silencieusement aux totaux officiels. Une prévisualisation,
si utile, doit être nommée « Estimation locale en attente ».

## Voix

Voix courte : accès à la dictée Android si disponible, utilisée seulement pour
remplir un champ avec confirmation ; doc 30 autorise ce chemin court. Voix longue :
enregistrement explicite, temporaire et protégé, puis pipeline backend utilisant
`transcription_service`. Un modèle de raisonnement principal n'est pas le moteur
de transcription. Le contrat Vector dédié manque dans ce snapshot : conserver
un brouillon ou désactiver l'envoi, ne pas simuler « Commande exécutée ».

États utiles : permission demandée, enregistrement, arrêt, relecture/suppression,
en attente d'envoi, transcription en cours, transcription à vérifier, action à
confirmer, confirmée. Ne pas passer de l'audio à une transaction sans validation.
Pas d'écoute permanente implicite. Le futur détecteur de son d'offre est une
capacité distincte à valider et à autoriser explicitement.

## Permissions progressives

| Permission/capacité | Quand demander | Refus ou indisponibilité |
|---|---|---|
| Localisation active | Dépose préremplie ou mode conduite automatique | Zone saisie manuellement, mode conduite manuel |
| Microphone | Premier enregistrement/dictée explicite | Champ texte à l'arrêt |
| Fichier image | Action capture depuis sélecteur système | Saisie de l'offre manuelle |
| Notifications | Explication préalable d'un usage disponible | États visibles dans l'app |
| Superposition/capture écran | Seulement quand la chaîne future est implémentée | Pas de contournement, fonction non disponible |

Ne pas demander des permissions de fond pour une fonctionnalité future. Le mode
conduite peut être forcé manuellement si le GPS est refusé. Les détails des APIs
Android et des politiques de plateforme devront être vérifiés à l'implémentation,
ce dossier n'affirme pas leur compatibilité actuelle sur chaque tablette.

## Données et journaux

Pas de vraie donnée utilisateur dans les fixtures. Géolocalisation, captures,
voix, adresses de clients et historique VTC sont sensibles : collecte minimale,
pas d'analytics tiers imposés, pas de tokens ni contenu brut dans les logs.
Les durées de conservation réelles dépendent de la politique backend doc 10 ;
le frontend doit supprimer ses fichiers temporaires devenus inutiles et laisser
l'utilisateur effacer les brouillons locaux. Ne pas prétendre effacer le ledger
ou l'historique serveur si aucun contrat de suppression n'existe.

La capture doit rester volontaire ou autorisée, jamais contourner une protection.
Ne pas déduire une fin de course, une acceptation ou une dépose depuis une simple
position GPS. Un résultat OCR reste une extraction à contrôler.
