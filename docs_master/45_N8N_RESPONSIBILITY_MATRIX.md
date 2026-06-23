# 45 - N8N RESPONSIBILITY MATRIX

## 1. Objectif du document

Ce document fixe officiellement le rôle de `n8n` dans l'écosystème IMPERIUM.

Il complète les documents IA précédents, notamment :

- `30_AI_ROUTING_AND_SCORING_POLICY.md`
- `31_AI_TASKS_AND_RESULTS_CONTRACT.md`
- `32_WR_INTERACTIVE_WORKFLOW.md`
- `44_BRAIN_UNIFIED_LOGIC.md`

Décision centrale :

> n8n n'est pas le cerveau du système.  
> n8n n'est pas la source de vérité.  
> n8n n'est pas propriétaire des conversations utilisateur.  
> n8n est un orchestrateur de workflows externes, temporels, asynchrones ou multi-modèles.

---

## 2. Règle mère

```text
Backend = source de vérité, état métier, DB, sécurité, validation finale
Le [local model] = cerveau opérationnel, routing IA, discussion utilisateur, préparation des appels lourds
n8n = orchestration externe/asynchrone, appels multi-outils, pipelines IA lourds
App = interface utilisateur, validation humaine, popups, boutons
DB Imperium = stockage canonique
```

n8n ne doit jamais écrire directement dans PostgreSQL.

Tous les résultats produits par n8n doivent revenir au backend via un endpoint sécurisé.

```text
n8n → backend → validation → DB
```

Jamais :

```text
n8n → DB
```

---

## 3. Quand n8n est utile

n8n est utile lorsqu'au moins une condition est vraie :

1. Le workflow dépend d'un déclencheur externe.
2. Le workflow dépend d'un déclencheur temporel.
3. Le workflow doit surveiller une API externe.
4. Le workflow appelle plusieurs outils ou plusieurs modèles IA.
5. Le workflow est asynchrone ou long.
6. Le workflow doit récupérer, transformer ou enrichir des données avant retour backend.
7. Le workflow nécessite une orchestration technique plus qu'une décision métier.

Exemples valides :

```text
- scan hebdomadaire des événements VTC
- surveillance API transport / trafic
- OCR ticket de caisse
- appel du [OCR service] puis classification par le [local model]
- appel du [local model] puis du [high reasoning model]
- synchronisation mail entrant
- webhook externe
```

---

## 4. Quand n8n est inutile

n8n est inutile lorsque le backend peut gérer l'action simplement.

Exemples :

```text
- changer une bannière UI à une heure précise
- ouvrir une popup
- commencer une journée
- terminer une journée
- créer une mission
- changer l'état d'un item Path
- récupérer un dashboard
- afficher un rapport déjà calculé
- stocker une validation utilisateur
- gérer une conversation utilisateur courte ou longue
```

Ces actions appartiennent au backend/app, pas à n8n.

---

## 5. Weekly Review - WR

### 5.1 Décision officielle

Le WR interactif ne doit pas être piloté message par message par n8n.

La conversation reste entre :

```text
Utilisateur
↓
Popup WR
↓
Backend Imperium
↓
[local model]
↓
Backend Imperium
↓
Popup WR
```

n8n ne doit pas recevoir chaque message utilisateur.

Patch 2B implémente cette frontière côté backend :

- le backend stocke les sessions WR ;
- le backend stocke les messages WR ;
- le backend stocke les brouillons et rapports finaux WR ;
- le backend attache les résultats IA comme propositions ;
- aucun résultat IA ne devient canonique sans validation explicite utilisateur/backend.

---

### 5.2 Activation de la bannière WR

Chaque mardi à 20:00 Europe/Paris, la bannière WR passe d'un statut passif à un statut actif.

Décision :

```text
n8n inutile
Backend suffisant
```

Raison :

- c'est une règle temporelle simple ;
- aucun service externe n'est nécessaire ;
- aucun modèle IA n'est nécessaire ;
- la source de vérité doit rester côté backend.

---

### 5.3 Lancement du WR

Quand l'utilisateur clique sur `commencer le rapport hebdomadaire`, l'app ouvre la popup WR.

À ce moment :

```text
App → Backend
Backend crée/ouvre la session WR
Backend peut déclencher n8n pour la préparation initiale
```

n8n peut être utilisé pour préparer le contexte lourd :

```text
n8n récupère les données utiles
n8n appelle le [local model]
Le [local model] prépare et mâche le travail
n8n appelle le [high reasoning model]
Le [high reasoning model] produit une analyse profonde
n8n renvoie le résultat au backend
backend affiche le résumé initial dans la popup WR
```

---

### 5.4 Conversation WR

Après le résumé initial, la discussion se poursuit sans n8n.

```text
Utilisateur ↔ Popup WR ↔ Backend ↔ [local model]
```

Le [local model] peut :

- poser des questions ;
- demander des précisions ;
- reformuler ;
- construire le rapport final ;
- demander à l'utilisateur s'il veut ajouter autre chose ;
- intégrer les réponses utilisateur.

n8n ne doit pas être au milieu de cette conversation.

---

### 5.5 Appel du [high reasoning model] pendant la conversation WR

Si le [local model] estime qu'une analyse lourde est nécessaire, il ne doit pas appeler le [high reasoning model] directement de manière sauvage.

Flux propre :

```text
Le [local model] détecte un besoin d'analyse par le [high reasoning model]
↓
Backend crée une tâche IA
↓
n8n orchestre l'appel au [high reasoning model]
↓
n8n renvoie le résultat au backend
↓
Le [local model] reprend le résultat
↓
La popup affiche la suite
```

n8n reste orchestrateur. Le [local model] reste le cerveau conversationnel.

---

### 5.6 Validation finale du WR

Quand l'utilisateur est satisfait du rapport :

```text
Utilisateur valide dans l'app
↓
Le [local model] formalise le rapport final
↓
Backend reçoit le rapport final
↓
Backend enregistre dans la DB
```

n8n n'est pas nécessaire pour l'enregistrement final.

Décision :

```text
n8n ne stocke pas le rapport final WR.
Le backend stocke le rapport final WR validé.
```

---

## 6. Vector - scan hebdomadaire événements

### 6.1 Objectif

Chaque lundi à 03:00 Europe/Paris, IMPERIUM doit détecter les événements potentiellement utiles pour la rentabilité VTC.

Exemples :

```text
- spectacles
- concerts
- matchs de foot
- grands salons
- fermetures de routes
- travaux nocturnes
- événements générateurs de flux
```

Périmètre :

```text
30 km autour de la zone cible définie pour Vector
```

---

### 6.2 Rôle de n8n

n8n est utile ici.

Workflow :

```text
Trigger temporel lundi 03:00 Europe/Paris
↓
n8n lance un scan web
↓
n8n appelle le [web/fresh-data specialist] pour une recherche web structurée
↓
n8n transmet le résultat au [local model]
↓
Le [local model] classe les événements du plus impactant au moins impactant
↓
n8n renvoie le résultat au backend
↓
Backend enregistre le rapport dans la DB
↓
Vector utilise ces données
```

---

### 6.3 Rôle exact de Vector

Vector ne gère pas la fatigue, la pression, les objectifs personnels ou l'énergie.

Décision officielle :

```text
Vector = rentabilité VTC uniquement
Imperium = arbitrage global de la vie utilisateur
Pulse = santé, fatigue, récupération
Vault = finance
Path = exécution quotidienne
```

Vector doit répondre à des questions de rentabilité :

```text
- où aller ?
- quelle zone éviter ?
- quel événement peut générer de la demande ?
- quel incident transport peut créer une opportunité ?
- quelle route/travaux peuvent nuire à la rentabilité ?
```

---

## 7. Vector - surveillance temps réel pendant session VTC

### 7.1 Déclenchement

Quand l'utilisateur clique sur `commencer une session VTC` dans Vector, un workflow n8n peut se lancer.

Décision :

```text
n8n utile
```

---

### 7.2 Fonctionnement

Pendant la session VTC :

```text
n8n surveille les APIs externes utiles
↓
un changement d'état est détecté
↓
n8n appelle le [local model]
↓
Le [local model] classe l'importance du changement
↓
n8n renvoie le résultat au backend
↓
backend écrit le signal dans la DB
↓
Vector peut utiliser ce signal
```

Exemples de signaux :

```text
- perturbation RER
- station/gare impactée
- route fermée
- incident transport
- événement soudain
- problème majeur sur un axe rentable
```

---

### 7.3 Ce que n8n ne fait pas

n8n ne décide pas directement où l'utilisateur doit aller.

n8n ne remplace pas Vector.

n8n orchestre la récupération et la classification du signal.

La recommandation finale revient à :

```text
Backend + Vector + [local model] selon les règles métier
```

---

## 8. Routes fermées, travaux, circulation nocturne

Ces données sont traitées comme des événements Vector.

Décision :

```text
Même logique que le scan hebdomadaire des événements.
```

Workflow :

```text
n8n scan / récupère les données
↓
Le [web/fresh-data specialist] peut aider à structurer
↓
Le [local model] classe l'impact VTC
↓
backend stocke
↓
Vector exploite
```

---

## 9. Ticket de caisse / justificatif / dépense

### 9.1 Décision officielle

n8n est utile pour l'OCR et la classification initiale.

n8n ne reçoit jamais l'upload comme premier propriétaire canonique. Le backend possède l'enregistrement du fichier, la création de la tâche IA, le stockage du résultat et la création finale de la transaction.

Workflow officiel :

```text
Utilisateur prend une photo du ticket
↓
App envoie l'image au backend
↓
Backend crée un MediaItem / ai_task(vault.receipt_extract)
↓
Backend déclenche n8n ou expose la tâche pour n8n
↓
n8n appelle le [OCR service]
↓
Le [OCR service] extrait le texte et les champs possibles
↓
n8n appelle le [local model]
↓
Le [local model] classe les données
↓
n8n renvoie le résultat au backend via HMAC callback
↓
Backend stocke ai_result as pending_validation
↓
Backend pré-remplit la popup "ajouter une dépense"
↓
Utilisateur valide, modifie ou annule
↓
Backend crée vault_transaction only after validation
```

---

### 9.2 Sortie de n8n

La sortie attendue de n8n est une proposition structurée.

Exemple :

```json
{
  "type": "expense_candidate",
  "amount": "23.40",
  "currency": "EUR",
  "merchant": "TotalEnergies",
  "category": "fuel",
  "local_date": "2026-04-29",
  "confidence": 0.87,
  "raw_ocr_text": "...",
  "warnings": []
}
```

---

### 9.3 Limite de responsabilité

À partir du moment où n8n a renvoyé le résultat au backend :

```text
n8n sort du workflow
```

La validation utilisateur ne concerne plus n8n.

Le backend reste responsable de :

- l'enregistrement du fichier ;
- la création de `ai_task(vault.receipt_extract)` ;
- le stockage de `ai_result` ;
- le pré-remplissage de l'écran de validation ;
- la création finale de `vault_transaction` après validation utilisateur.

---

## 10. Audio / [transcription service]

Quand l'utilisateur relâche un bouton d'enregistrement audio, le flux peut être direct.

Décision actuelle :

```text
n8n inutile en V1
```

Workflow préféré :

```text
Utilisateur enregistre audio
↓
App/backend appelle le [transcription service]
↓
Le [transcription service] renvoie le texte
↓
Texte affiché dans la popup/chatbot
↓
Le [local model] traite si nécessaire
```

n8n pourra être réévalué plus tard seulement si le pipeline devient complexe :

```text
audio long
multi-fichiers
stockage externe
résumé automatique
routage multi-modèles
transcription différée
```

---

## 11. Début de journée / fin de journée

Décision :

```text
n8n inutile
```

Le backend suffit.

Exemples :

```text
- commencer journée
- finir journée
- écrire day.finished
- récupérer latest day review
- afficher dashboard
```

---

## 12. Fonctions backend-only

Les fonctions suivantes doivent rester backend/app-only en V1 :

```text
- changement d'état de bannière simple
- création de mission
- mission start/complete/fail
- Path item start/complete/skip/cancel
- daily plan create/activate/complete/cancel
- priority rules storage
- dashboard snapshot
- weekly report déterministe en lecture seule
- validation finale utilisateur
- stockage canonique en DB
```

n8n ne doit pas intervenir dans ces opérations simples.

---

## 13. Mail reçu

n8n peut être utile pour les mails entrants.

Exemple :

```text
mail reçu
↓
n8n détecte le mail
↓
n8n extrait les informations utiles
↓
n8n appelle le [local model] pour classification
↓
n8n renvoie le signal au backend
↓
backend stocke ou crée une action à traiter
```

Exemple :

```text
relance impôts
facture
amende
rendez-vous important
document administratif
```

Décision :

```text
n8n utile si l'intégration mail est externe.
Backend reste source de vérité.
Le [local model] classe et explique.
```

---

## 14. Webhooks externes

n8n reste utile pour les webhooks externes.

Exemples :

```text
- outil OCR
- outil audio
- service externe
- formulaire
- intégration future
- flux automatisé non natif dans l'app
```

Règle :

```text
Webhook externe → n8n → le [local model] / le [OCR service] / un [domain specialist] si besoin → backend → DB
```

---

## 15. Résultats n8n et stockage DB

n8n ne stocke pas directement.

n8n renvoie des résultats au backend.

Le backend décide :

```text
- accepter
- refuser
- normaliser
- associer à un user_id
- vérifier idempotency
- enregistrer en DB
- exposer à l'app
```

---

## 16. Modèle de responsabilité par cas

| Cas | n8n utile ? | Responsable principal | Pourquoi |
|---|---:|---|---|
| Bannière WR mardi à 20:00 Europe/Paris | Non | Backend | Règle temporelle simple |
| Démarrer WR | Partiellement | Backend + [local model] | n8n seulement pour préparation lourde |
| Conversation WR | Non | [local model] + Backend | Interaction utilisateur longue |
| Appel [high reasoning model] WR | Oui | n8n | Orchestration IA lourde |
| Validation finale WR | Non | Backend | Stockage canonique |
| Scan événements lundi 03:00 Europe/Paris | Oui | n8n | Web + IA + traitement asynchrone |
| Surveillance API session VTC | Oui | n8n | Écoute externe continue |
| Routes/travaux | Oui | n8n | Même famille que événements |
| Photo ticket | Oui | Backend + n8n | Backend possède l'upload et la tâche, n8n orchestre OCR + classification |
| Validation ticket | Non | Backend + utilisateur | Décision humaine finale |
| Audio court | Non | Backend/App + [transcription service] | Pipeline simple |
| Commencer journée | Non | Backend | Action métier simple |
| Finir journée | Non | Backend | Action métier simple |
| Dashboard | Non | Backend | Lecture DB |
| Weekly report déterministe | Non | Backend | Lecture calculée |
| Mail reçu | Oui | n8n | Déclencheur externe |
| Webhook externe | Oui | n8n | Orchestration externe |

---

## 17. Règle anti-usine-à-gaz

Si une fonction peut être faite proprement par le backend sans outil externe, elle ne doit pas passer par n8n.

```text
Backend d'abord.
n8n seulement quand il apporte une vraie valeur.
```

Valeur réelle de n8n :

```text
- connecter des outils
- surveiller des sources externes
- déclencher des workflows longs
- appeler plusieurs IA
- transformer des données
- exécuter des pipelines asynchrones
```

Pas une valeur réelle :

```text
- ajouter un détour
- faire une requête backend simple
- gérer une conversation utilisateur
- stocker une donnée métier
- remplacer la logique backend
```

---

## 18. Décision finale

n8n reste dans l'écosystème IMPERIUM, mais avec un rôle strict :

```text
n8n = orchestrateur externe et asynchrone
Le [local model] = intelligence opérationnelle
Backend = autorité, sécurité, état, DB
App = interaction utilisateur
```

n8n ne doit pas devenir un deuxième backend.

n8n ne doit pas devenir le cerveau.

n8n ne doit pas devenir propriétaire des conversations.

n8n est conservé parce qu'il apporte une vraie valeur sur :

```text
- IA multi-modèles
- OCR
- web/event scan
- APIs externes
- mails
- webhooks
- workflows longs
```

Tout le reste doit rester simple, direct, contrôlé par le backend.
