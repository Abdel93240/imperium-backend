# Imperium — Brief des maquettes à générer (V1)

Date : 2026-10-16. Suite de la revue `Imperium_Revue_UI_2026-10-15_v1` (19 maquettes).
Chaque écran ci-dessous est soit absent du paquet, soit à retoucher. Le contenu vient des
docs d'architecture (`docs_master`) et des décisions du 2026-10-15. Les renvois `doc NN §x`
servent à vérifier, pas à recopier dans l'image.

## 0. Règles communes (identiques au paquet de revue)

- Support : Galaxy Tab S8, portrait, dimensions fluides (spec de revue §01, docs 59, 63, 65 à jour).
- Style : fond presque noir, doré champagne légèrement chaud, cadres absents ou très fins,
  séparateurs discrets, icônes simples. Titres Cormorant Garamond, corps Inter, nombres,
  heures et terminal en JetBrains Mono.
- Logo Imperium original et icône IA commune (celle de Conseils IA). Pas de nouveau logo.
- Tutoiement partout, jamais de vouvoiement (doc 65 §2.2).
- Navigation gauche : Dashboard, Opérations, Historique, Réglages (« Historique » aussi en titre de page, jamais « Hall of Fame »).
- Fenêtres : même gabarit que les maquettes 09 à 19 (titre serif, croix en haut à droite,
  boutons Annuler en contour gris / action principale en contour doré, action destructive
  en rouge).
- Pastilles d'état : vert = disponible/autorisé, orange = dégradé/partiel, rouge =
  indisponible/erreur, gris = non vérifié. Dans les lignes, « Non autorisée » est ROUGE
  (même couleur que la légende, point UI-29).
- Données illustratives seulement.

---

## A. Retouches de maquettes existantes

### A1. Maquette 15 — Réglages (refonte des sections)

Ordre proposé des sections :

1. **Bulle flottante** (remplace « Widget et bulle ») : un seul interrupteur « Bulle
   flottante » + bouton « Gérer la bulle › » (→ B6). Supprimer l'interrupteur « Widget » et
   le bouton « Gérer le widget » : il n'y a plus de widgets d'accueil (doc 63 §10).
2. **Notifications** : interrupteur général + « Gérer les notifications › » (→ B7).
3. **Routine du matin** : interrupteur « Popup du matin » + heure (ex. `06:30`, sélecteur
   d'heure) (doc 43 §15).
4. **Replanification** : « Après une mission échouée » → réglage par niveau d'urgence
   (défaut : replanifier si la mission est urgente, demander sinon) ; « Délai minimum
   entre deux replanifications » : `5 min` (doc 43 §15), automatiques et manuelles.
5. **Comportement de l'IA** : Strict / **Équilibré** (sélectionné par défaut) / Souple.
6. **Priorités personnelles** : inchangé (→ maquette 17).
7. **Intelligence artificielle** :
   - « Nourrir l'IA › » : UNE seule entrée (maquette 16). Elle ouvre la liste des éléments
     transmis ; le bouton « Importer » est dans cette liste (doc 70 §7) ;
   - « Logs de l'IA › » (→ B12) ;
   - « Conservation de l'historique du chat » : `90 jours` (choix).
8. **Connexion et autorisations** : inchangé (→ maquette 19).
9. **Paramètres avancés ›** (→ B8).

En-tête : la flèche › à droite de « Serveur : connecté · IA : disponible » ouvre la
fenêtre « Connexion à Imperium » (maquette 19, partie gauche).

Pas de liste d'appareils de confiance : un seul appareil (doc 63 §13.5).

### A2. Maquette 12 — Routines

- Menu Fréquence = liste fermée : Chaque jour / Chaque semaine / Toutes les 2 semaines /
  Chaque mois. Pas d'option « Autre », pas de récurrence personnalisée (doc 71 §4).
- Retirer l'aide « Exemples : deux fois par semaine, toutes les deux semaines… ».
- Pas de champ Jour ni Heure : l'IA place les routines ; un jour ou une heure forcés
  passent par le chatbot et ne s'affichent pas (doc 71 §4.1). Le reste du formulaire
  est inchangé (Nom, Fréquence, Durée estimée, Priorité, Notes, Active).
- « Supprimer » ouvre la confirmation B2.

### A3. Maquettes 09, 11, 17 — Suppressions

Tous les boutons « Supprimer » (projet, mission, routine) ouvrent la confirmation B2.
Rien d'autre à changer (les priorités ne se suppriment plus, voir A7).

### A4. Maquette 05 — Transaction (et bulle Vault plus tard)

Ajouter un champ **Catégorie** (menu) sous le libellé, PRÉREMPLI dès que le libellé est
saisi ou lu par l'OCR : d'abord par la table des libellés connus, sinon par l'IA locale
(doc 42 §7.0). À côté, une étiquette non modifiable « Business » ou « Perso », déduite de
la catégorie. Le champ reste modifiable avant « Enregistrer ». Montrer un état « catégorie
proposée par l'IA » (petite icône IA commune) distinct d'un état « reconnu ».

### A6. Tutoiement (maquettes 15, 17, 19 et toutes les nouvelles)

Corriger les textes au vouvoiement, par exemple :
- 15 : « Votre liste, dans votre ordre. » → « Ta liste, dans ton ordre. »
- 19 : « Utiliser votre position » → « Utiliser ta position ».
- Vérifier aussi la 17 et tous les sous-titres des nouveaux écrans.

### A7. Maquette 17 — Priorités personnelles

Exactement 4 lignes : Religieux, Business, Finances, Santé (doc 52 §3). Seules actions :
monter / descendre. Retirer « Ajouter », « Renommer », « Supprimer » et la petite fenêtre
de nom. Sous-titre : « Ton ordre décide du poids de chaque domaine dans le plan. »
Aperçu dans Réglages (maquette 15) : « 01 Religieux · 02 Business · 03 Finances · 04 Santé ».

### A8. Maquettes 01 et 03 — Missions annexes

Décision 2026-10-16 (doc 53 §3.1) : les « sous-missions » des maquettes sont les
**missions annexes** du doc 53, livrées en V1 en version allégée.

- Titre du bloc : « Missions annexes » (au lieu de « Sous-missions facultatives »),
  mention « Facultatives » conservée.
- Changer l'exemple : une séance de sport ne porte jamais d'annexes (doc 53 §5.1).
  Mission actuelle « Travail VTC » (longue, peu prenante), annexes indépendantes et
  courtes : « Appeler Yacine », « Confirmer RDV dentiste », « Vérifier prix garage »,
  « Répondre à Marie », « Réserver contrôle technique ».
- Maquette 01 : le bloc n'apparaît que si la mission porte des annexes (prévoir aussi
  la carte sans bloc, ex. Séance de sport).
- Maquette 03, « Fait » : « Missions annexes réalisées » à cocher, même mise en page ;
  « Pas fait » : inchangé (menu Raison + Détails, le menu préremplit le texte).

### A9. Maquettes 01 et 02 — Bouton « Replanifier » pendant le délai

Décision 2026-10-16 (doc 43 §3.3) : le délai de 5 min s'applique aussi au replan
manuel. Ajouter l'état grisé du bouton « Replanifier la journée » (maquette 01) et
du bouton « Replanifier » (maquette 02), avec le texte « Disponible dans 3 min »
(JetBrains Mono pour le nombre). Pas de fenêtre d'erreur : le bouton se réactive seul.

### A5. Maquettes 13 et 14 — Historique

Remplacer le titre « Hall of Fame » par « Historique » ; la barre de navigation dit déjà
« Historique ». Le mot « Hall of Fame » ne doit apparaître nulle part (doc 43 §7 : pas de
cadrage trophée / gamification).

Bloc Régularité (doc 43 §6.1) : le chiffre « 82 / 100 » dépend de la période choisie ;
« +14 points sur la période » se lit « par rapport à la période précédente ». La courbe
est quotidienne, sans lissage : elle doit paraître plus irrégulière que sur la maquette.

---

## B. Nouveaux écrans

### B1. Résultat de la replanification (`IMP.REPLAN.VALIDATE`)

Ouvert après le bouton « Replanifier » de la maquette 02, et après « Replanification
complète » depuis la bulle (doc 59 §12.6, doc 63 §10.2).

- Pendant le calcul : l'écran de chargement standard existant (celui du démarrage de
  journée).
- Fenêtre plein écran en deux colonnes :
  - **Gauche — « Nouvelle planification »** : liste des missions de la journée dans le
    même style que le Programme du jour (heure, titre, durée). Les missions déplacées,
    ajoutées ou retirées portent un petit badge (Déplacée / Nouvelle / Retirée).
    En tête : la raison saisie (ex. « Fatigue — … »).
  - **Droite — chatbot** : le terminal (même rendu que la maquette 06 : JetBrains Mono,
    repères `> IMPERIUM` / `> VOUS`, champ, micro, envoyer). L'IA y explique ses choix ;
    l'utilisateur demande des corrections, la colonne de gauche se met à jour.
- Bas : **Annuler** (contour gris) / **Accepter** (contour doré). Pas de bouton
  « Modifier » : on corrige en parlant au chatbot.
- Sur Tab S8 portrait, si deux colonnes ne tiennent pas : plan en haut, terminal en
  dessous (à trancher visuellement).

### B2. Confirmation de suppression (fenêtre réutilisable)

Petite fenêtre centrée sur fond assombri (doc 67 : aucune action destructive sans
confirmation).

- Titre : « Supprimer <nom> ? »
- Une ligne d'explication selon le cas (doc 71, effets d'une suppression) :
  - projet : « Ses missions à venir seront annulées ; l'historique est conservé. »
  - routine : « Elle ne sera plus planifiée ; l'historique est conservé. »
  - mission : « Elle sera retirée du plan. »
  - élément de Nourrir l'IA : voir B10.
- Boutons : **Annuler** (gris) / **Supprimer** (rouge).
- Une seule maquette générique (variante projet), les autres textes en annexe.

### B3. Justificatif — caméra

Ouvert par « Importer un justificatif » (maquette 05). Même mécanique que Vault (doc 59 §13.4).

- Aperçu caméra plein écran, cadre de guidage du ticket, bouton déclencheur rond.
- En bas : accès « Galerie » (→ B4) et « Annuler ».
- Mention discrète : « L'image est envoyée au service OCR. »

### B4. Justificatif — choisir une photo déjà prise

Grille de photos de la galerie, sélection d'une image, bouton « Utiliser cette photo »,
« Annuler ».

### B5. Analyse OCR et échec (variante de l'écran de chargement)

- Analyse : l'écran de chargement standard existant, texte « Lecture du justificatif… ».
- Échec : MÊME écran, le texte devient le message d'erreur (en rouge discret), ex.
  « Échec de la lecture : image trop floue ». Il reste affiché **10 secondes** (le temps de
  le lire ou de le recopier dans le chatbot), puis retour automatique au formulaire de
  transaction. Montrer les deux états côte à côte.
- Succès : retour au formulaire de la maquette 05, champs préremplis et modifiables.

### B6. Gérer la bulle (Imperium)

Fenêtre ouverte depuis Réglages → Bulle flottante (doc 63 §10).

- Interrupteur « Bulle flottante » (mission en cours).
- État de l'autorisation Android « Afficher par-dessus les autres apps » avec pastille et
  bouton « Autoriser » / « Gérer ». Quand on active la bulle sans l'autorisation : texte
  d'explication puis renvoi vers les réglages Android.
- Aperçu : la bulle et son panneau (reprendre la maquette 18) avec la liste fixe des
  actions : Terminer, Échouer, Demander une replanification complète de la journée.
- Boutons : Fermer.

Hors Imperium (pour plus tard, pas dans ce lot) : bulle Vault (panneau d'ajout de
transaction, reprendre le formulaire de la maquette 05) et bulles raccourcis Path, Pulse,
Vector (simple icône, un tap ouvre l'app).

### B7. Gérer les notifications

Fenêtre ouverte depuis Réglages → Notifications (doc 43 §15, doc 65 §8.5, doc 76 Q24).

- Mention : « Les notifications arrivent sur cette tablette (notifications Android). »
  Pas de choix de canal.
- Interrupteurs :
  - Check-in du matin ;
  - Weekly Review ;
  - Rappels de mission ;
  - **Alertes rouges** (urgentes, ex. solde insuffisant pour une dépense à venir) —
    désactivable, avec une ligne d'avertissement sous l'interrupteur quand il est éteint.
- Boutons : Fermer.

### B8. Paramètres avancés (doc 73)

Fenêtre-menu, puis un sous-panneau par entrée. Ton technique, mêmes composants que les
autres fenêtres.

**B8.0 Menu** — quatre lignes avec › :
- Vectorisation — « Ouvre la console de calibration (Tower) » ;
- Modèles par rôle ;
- Seuils de score /200 ;
- Clés API.

**B8.1 Modèles par rôle** — tableau : rôle → modèle actuel → bouton « Modifier ».
Rôles (doc 30 §3) : `local_executor` (Qwen3.6-27B), `first_cloud_tier` (Claude Sonnet 5),
`high_reasoning` (Claude Opus 5.5), `sustained_long_context` (Claude Fable 5.1),
`health_specialist`, `finance_specialist`, `web_fresh_data` (GPT-5.6 Sol),
`high_reasoning_safeguard` (GPT-6 Astra), `ocr_service`, `transcription_service`,
`embedding_service`. Bouton « Mettre à jour le catalogue » en haut.
Petite fenêtre « Modifier le modèle — <rôle> » : Accès (menu fournisseur : OpenRouter,
OpenAI, Anthropic, Google…), Modèle (menu, ou champ de recherche pour OpenRouter), Effort
(menu, masqué si le modèle ne le gère pas), Annuler / Valider. On ne peut pas ajouter ni
renommer un rôle.

**B8.2 Seuils de score /200** (doc 30 §5.6) — tableau éditable :
`0–99` IA locale · `100–139` premier niveau cloud · `140–179` raisonnement poussé ·
`180–200` mécanique critique. Les bornes sont des champs numériques ; une ligne
d'explication sous le tableau ; Annuler / Enregistrer.

**B8.3 Clés API** — une ligne par fournisseur : nom, pastille « Clé enregistrée ✓ » ou
« Manquante », boutons « Remplacer » / « Supprimer ». « Remplacer » ouvre un champ masqué
en écriture seule + Enregistrer. La clé n'est JAMAIS réaffichée.

**B8.4 Console de calibration (page HTML sur la Tower)** — optionnel, ce n'est pas un
écran de l'app : champs Taille des chunks (400), Top-K (8), Seuil de similarité (0,75),
Quantization (Q8 ▾), Température (0,7) ; champ « Sujet de test » + bouton « Lancer le
test » ; zone Résultat avec les extraits retrouvés puis la réponse du modèle (doc 73 D.6).

### B9. Configurer la connexion (doc 63 §13.5)

Ouvert par « Configurer la connexion › » (maquette 19, gauche). Sert aussi d'écran de
connexion au premier lancement.

- Adresse du serveur + bouton « Tester » (pastille de résultat).
- Clé maître : champ masqué (icône œil), jamais mémorisé.
- Nom de l'appareil : prérempli avec le modèle (« Galaxy Tab S8 »).
- Bouton principal « Se connecter » ; états : connexion en cours, erreur (« Clé maître
  invalide »), connecté.
- Pas d'email/mot de passe, pas de liste d'appareils.

### B10. Nourrir l'IA — sous-écrans (maquette 16)

Tous ouverts depuis la fiche d'un élément dans « Éléments transmis ».

- **Sources** (aussi ouvert par « Voir les sources › » dans le terminal) : liste ou
  vignettes des fichiers d'origine (nom, type, taille, date) ; un tap ouvre l'aperçu.
  Lecture seule.
- **Informations retenues** : le texte final que l'IA a enregistré (ce qui est entré en
  mémoire), en lecture seule, avec la destination (Mémoire / Projet « … ») et la date.
  Mention : « Pour corriger, parle au chatbot. »
- **Conversation** : relecture du terminal de cette session (rendu maquette 06), lecture
  seule.
- **Élément « Erreur de lecture »** : la fiche montre le message d'erreur et deux boutons :
  « Réessayer » et « Ouvrir le chatbot ».
- **Élément « À valider »** : un tap rouvre la conversation dans le terminal pour terminer
  la validation.
- **Élément « À analyser »** : fiche avec l'état d'attente, sans action.
- **Supprimer…** : confirmation B2, texte « Supprimer « <nom> » ? Les sources et les
  informations retenues seront supprimées ensemble. » Après « Supprimer », le terminal
  s'ouvre avec la demande et l'IA effectue puis confirme la suppression ; « Annuler » ne
  change rien (doc 70 §4).

### B11. Logs de l'IA (doc 72 §8)

Ouvert depuis Réglages → Intelligence artificielle → Logs de l'IA.

- Gauche : petit explorateur de fichiers limité aux dossiers de logs de l'IA, triés du plus
  récent au plus ancien, noms explicites (ex. `2026-10-16 · Weekly Review`,
  `2026-10-15 · Nourrir l'IA · Exemples de courses Bolt`).
- Droite : terminal d'affichage (JetBrains Mono) avec le contenu du log sélectionné.
- Lecture seule : aucun bouton de modification. Mention : « Pour corriger une extraction,
  parle au chatbot. »

---

## C. Pas de maquette nécessaire

- « Terminer la journée » : termine la journée directement en V1, sans fenêtre (doc 59 §12.5).
  Une mission non faite dont l'échéance est dépassée passe en standby et déclenche la
  bannière « Intervention requise » existante (maquette 01) ; « Examiner » ouvre le
  terminal (maquette 06). Pas de nouvel écran (doc 43 §5.4).
- Chevrons du Programme du jour : ouvrent les notes de la mission (maquette 10).
- Densité du Dashboard (doc 65 §3.3) : pas de défilement de page ; maquette 01 conforme.
  Seul le Programme du jour défile en interne ; titres 1 ligne, description 3 lignes.
- Chevrons des Projets en attente : ouvrent « Gérer les projets » avec ce projet déplié
  (maquette 09).
- Activation des projets : par le classement (2 premiers actifs), pas de bouton
  Activer/Désactiver en V1 (doc 71 §3.3).
- Nourrir l'IA : résumé et destination dans la conversation, création de projet confirmée
  en texte (doc 70 §7).

## D. Encore ouvert

- ~~Historique ou Hall of Fame~~ → RÉSOLU : « Historique » partout (voir A5).
- ~~Sous-missions de la maquette 03~~ → RÉSOLU : missions annexes V1 allégées (voir A8).
- ~~Champs de la transaction~~ → RÉSOLU (doc 42 §7.0) : voir A4.
