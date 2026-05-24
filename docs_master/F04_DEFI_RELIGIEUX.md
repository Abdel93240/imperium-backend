# Défi religieux quotidien (Pulse) — Architecture

> **Statut : SPEC / À implémenter plus tard.** Document d'architecture
> uniquement. Aucune implémentation lancée. À sortir le jour où la feature
> devient prioritaire.

---

## 1. Objectif

Afficher chaque jour un **défi religieux** dans un encadré du dashboard Pulse
(ex. « Le Prophète ﷺ a dit que celui qui répète telle formule 100 fois par jour
… »). Le défi doit être **sourcé, documenté, authentifié**, et affiché sans
aucun risque d'hallucination de l'IA.

---

## 2. Le principe directeur : PIOCHER, ne jamais GÉNÉRER

**Le risque à éliminer absolument** : sur du contenu religieux, une IA qui
génère au quotidien pourrait inventer un hadith ou attribuer une parole inexacte
au Prophète ﷺ. **Inacceptable.**

**La solution** : l'IA ne crée RIEN au quotidien. Chaque jour, le système
**pioche** un défi dans une base de données pré-validée. Tout est déjà écrit,
sourcé et vérifié en amont.

> Analogie : ce n'est pas « invente une citation » (risqué), c'est « tire une
> carte dans ce paquet de citations déjà vérifiées » (sûr).

**Conséquences :**
- Zéro hallucination possible au quotidien (rien n'est généré sur le moment).
- Zéro appel API quotidien (une simple lecture en base). Gratuit, instantané.

---

## 3. Structure de données

Table `defis_religieux` (ou équivalent dans le schéma Pulse existant). Chaque
entrée contient au minimum :

- **Texte du défi** (l'action à accomplir, ex. « Dire 100 fois telle formule »)
- **La parole / le hadith** concerné (arabe et/ou traduction)
- **Source précise** : recueil, numéro de hadith, **degré d'authenticité**
  (sahih, hasan, etc.)
- **Catégorie** (optionnel) : dhikr, prière, comportement, jeûne, etc.

> La traçabilité est obligatoire : chaque défi affiché doit pouvoir être remonté
> à sa source exacte.

---

## 4. Pioche quotidienne

- Le dashboard Pulse lit une entrée par jour dans `defis_religieux`.
- Stratégie de sélection à définir à l'implémentation : rotation séquentielle,
  aléatoire, ou aléatoire pondéré (éviter de re-piocher trop vite les mêmes).
- **Aucun appel IA.** Lecture en base uniquement.

---

## 5. Alimentation de la base : réutilise un mécanisme EXISTANT

**Point clé** : cette feature ne crée PAS son propre système d'alimentation.
Elle réutilise le **mécanisme générique d'enrichissement de l'IA déjà présent
dans Imperium** :

- Le bouton « **nourrir l'IA** » (présent un peu partout dans l'écosystème :
  on envoie quelque chose à l'IA, on en discute, ça enrichit la base / le profil
  utilisateur / les données métier comme les recettes batch cooking dans Pulse).
- Et/ou le **chatbot** capable de modifier toute la database **avec validation
  utilisateur**.

> ⚠️ À l'implémentation : se référer à la doc existante de ce mécanisme
> (« nourrir l'IA » + chatbot). Ne pas le redéfinir ici — cette spec se branche
> dessus, elle ne le réinvente pas. Le nom exact et le fonctionnement précis
> sont décrits dans leur propre documentation.

**Mode d'alimentation retenu** : ajout **manuel** par l'utilisateur, quand il le
décide. L'utilisateur entre un gros paquet de défis au départ, puis en rajoute
ponctuellement quand il le souhaite.

> Décision explicite : PAS d'auto-enrichissement automatique (pas de mission
> auto-créée par l'IA quand les défis deviennent redondants). L'enrichissement
> reste un acte volontaire de l'utilisateur.

---

## 6. Garde-fou non négociable : validation humaine

**Rien n'entre dans la base `defis_religieux` sans validation explicite de
l'utilisateur.** Ce principe est encore plus strict ici que pour les autres
features (ex. scanner nutritionnel), vu la nature du contenu (parole attribuée
au Prophète ﷺ).

Pour l'alimentation, ne PAS demander à l'IA de « générer des hadiths de mémoire »
(risque d'invention). Partir de **sources de référence fournies / choisies par
l'utilisateur**, que l'IA aide éventuellement à structurer **à partir d'un texte
fourni** (donc sans s'appuyer sur sa mémoire).

---

## 7. Responsabilité du contenu religieux

- **Le choix des recueils et des sources relève entièrement de l'utilisateur**
  (sa pratique, son école, ce en quoi il a confiance). Le système n'impose aucun
  jugement sur l'authenticité.
- Le rôle du système est **technique** : stocker chaque défi avec sa référence
  précise et garantir la traçabilité. Pas de validation théologique automatique.

---

## 8. Dépendances et intégrations

- **Dashboard Pulse** : affichage de l'encadré « Défi du jour ».
- **Mécanisme « nourrir l'IA » + chatbot** (existant) : alimentation de la base.
- **Base de données Pulse** : nouvelle table `defis_religieux` (ou extension du
  schéma existant).

---

## 9. Points ouverts à trancher à l'implémentation

- Stratégie de pioche (séquentielle / aléatoire / pondérée anti-répétition).
- Format exact de la table (champs, et lien éventuel avec le schéma existant).
- Sources de départ (fournies par l'utilisateur — à décider le jour venu).
- Faut-il marquer un défi comme « déjà fait aujourd'hui » / suivi de complétion
  (lien avec le système de suivi / missions Pulse) ?
- Gestion multilingue de l'affichage (arabe + traduction).
