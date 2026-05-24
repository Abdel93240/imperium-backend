# Scanner de composition produit (Pulse) — Architecture

> **Statut : SPEC / À implémenter plus tard.** Document d'architecture
> uniquement. Aucune implémentation lancée. À sortir le jour où la feature
> devient prioritaire.

---

## 1. Objectif

Capturer la **composition réelle** d'un produit alimentaire ou d'un complément
au moment de l'ajout au stock, par photo de l'étiquette. Remplacer un nom
générique (« jambon de poulet », « complément à base de shilajit ») par une
fiche produit précise : valeurs nutritionnelles réelles, liste d'ingrédients,
et le cas échéant forme moléculaire / dosage.

**Principe directeur** : deux produits avec le même nom ne sont pas le même
produit. La donnée précise est la fondation de tout calcul santé fiable en aval.

---

## 2. Le problème résolu

- Deux marques de « jambon de poulet » → macros différentes (protéines,
  glucides, lipides). Un suivi basé sur le nom est faux.
- Compléments alimentaires : même nom, dosages et formes moléculaires
  différents (ex. magnésium bisglycinate vs oxyde, shilajit pur vs dosé). La
  forme change l'effet et l'assimilation.
- Sans composition réelle, l'IA santé calcule sur des moyennes génériques =
  imprécis.

---

## 3. Périmètre (Phase 1 = capture uniquement)

**Ce que fait la feature :** capturer + structurer + stocker la composition
réelle. **Suivi factuel précis, rien de plus à ce stade.**

**Ce qu'elle ne fait PAS (volontairement) en Phase 1 :**
- Pas de recommandation de dosage / conseil santé (réservé à GPT-5.5 dans
  l'écosystème Pulse, avec sa prudence déjà éprouvée, et toujours en orientant
  vers des professionnels de santé).
- Pas de comparaison entre produits (phase ultérieure possible).

> Raison : on construit la donnée solide d'abord. Comparaison et reco
> deviennent triviales une fois la donnée précise en place ; l'inverse est faux.

---

## 4. Ergonomie : UN bouton + confirmation

- **Un seul bouton** « Scanner produit / Ajouter au stock ». L'utilisateur ne
  choisit PAS s'il scanne les ingrédients ou les valeurs nutritionnelles — sur
  un emballage réel les deux sont souvent côte à côte.
- L'utilisateur prend la/les photo(s) de l'étiquette.
- **L'IA (Gemini) identifie elle-même** ce qu'elle voit : liste d'ingrédients
  (pattern : liste séquentielle) et/ou tableau nutritionnel (pattern : tableau
  clé/valeur/unité, parfois deux colonnes « pour 100g » / « par portion »).
- **Étape de confirmation OBLIGATOIRE** : l'IA affiche ce qu'elle a compris
  (ex. « protéines 22g/100g, glucides 1g/100g, forme : magnésium bisglycinate »)
  et demande validation AVANT d'enregistrer.

> Justification de la confirmation : ce sont des données santé qui se propagent
> dans tout l'écosystème. Une erreur OCR (22g au lieu de 2,2g, confusion
> 100g/portion) serait silencieuse et fausserait tous les calculs en aval. La
> validation humaine coûte 3 secondes et garde la base fiable.

---

## 5. Pipeline technique

Réutilise le **pattern existant du scanner de tickets de caisse** (photo →
OCR/IA → IA locale → stock structuré). C'est une extension, pas une nouvelle
infra.

```
Photo étiquette
   → Gemini (multimodal : OCR + structuration)
   → sortie JSON structuré
   → confirmation utilisateur
   → IA locale enregistre la fiche produit dans le stock
```

**Point technique clé** : la robustesse ne vient PAS de l'OCR brut mais du
**prompt qui impose une sortie structurée**. Demander explicitement à Gemini un
JSON du type :
```json
{
  "ingredients": ["...", "..."],
  "nutrition": {
    "proteines": {"valeur": 22, "unite": "g", "base": "100g"},
    "glucides":  {"valeur": 1,  "unite": "g", "base": "100g"},
    "...": {}
  },
  "forme_moleculaire": "magnésium bisglycinate",
  "dosage_par_unite": {"valeur": 500, "unite": "mg"}
}
```
plutôt que du texte libre. C'est ce qui sépare un scan exploitable d'une bouillie
de texte.

> ⚠️ À vérifier à l'implémentation : capacité réelle de Gemini à structurer
> correctement un tableau nutritionnel courbé/multilingue. A priori bon
> (multimodal), mais à tester sur de vrais emballages.

---

## 6. Confidentialité (donnée santé)

- Les **données personnelles restent dans l'écosystème** (Pulse / IA locale).
- Les appels externes (Gemini pour l'OCR, GPT-5.5 pour le raisonnement santé)
  reçoivent du **contexte anonymisé**, redonné à chaque appel. Pas de stockage
  d'identité côté tiers.

---

## 7. Le cercle vertueux santé (vision d'ensemble)

```
Scan composition précise (cette feature)
   → l'IA Pulse pré-mâche le travail (suivi factuel, mise en forme)
   → consultation d'un professionnel de santé
   → diagnostic / recommandation du pro
   → ré-injection du diagnostic dans l'IA pour l'alimenter
   → suivi encore plus précis
```

Cette feature est la **brique d'entrée de données** de ce cycle. L'IA prépare,
le professionnel décide, et la décision réalimente le système.

---

## 8. Dépendances et intégrations

- **Pattern scanner existant** (tickets de caisse → stock). À étendre.
- **Gemini** : OCR + structuration multimodale.
- **IA locale** : enregistrement de la fiche produit dans le stock.
- **Écosystème Pulse** : consomme la donnée pour le suivi santé (et appels
  GPT-5.5 anonymisés pour le raisonnement).
- **Stock nourriture existant** : la fiche produit enrichit le stock déjà géré.

---

## 9. Points ouverts à trancher à l'implémentation

- Format exact de la fiche produit en base (réutiliser/étendre le schéma stock
  existant ?).
- Gestion des compléments où la forme moléculaire n'est pas sur l'étiquette
  principale (l'IA pose-t-elle une question ? cherche-t-elle ailleurs ?).
- Comment lier une fiche produit « composition » à un article de stock existant
  (même produit racheté = même fiche, ou nouvelle fiche par lot ?).
- Que faire quand l'utilisateur corrige la lecture de l'IA à l'étape de
  confirmation (apprentissage ? simple correction ponctuelle ?).
- Tester la fiabilité de Gemini sur tableaux nutritionnels réels avant de
  généraliser.

---

## 10. Phasage (le jour venu)

1. **Capture + structuration + confirmation** (cette spec) : photo → Gemini →
   JSON → validation → stock.
2. **Comparaison de produits** (ultérieur) : exploiter la donnée pour comparer
   qualité / macros / rapport qualité-prix.
3. **Aide à la décision santé** (ultérieur, prudent) : via GPT-5.5, toujours en
   orientation vers des professionnels, jamais en diagnostic autonome.
