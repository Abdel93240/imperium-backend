# 08 — Vision complète des évolutions

Ce document couvre les fonctions attendues à terme. Il ne crée ni endpoint ni
activation. Ces extensions restent hors navigation du socle tant que les
contrats et capacités nécessaires ne sont pas livrés. Les annexes Vector sont
incluses pour conserver le détail de la vision, avec leurs limites historiques.

## Contexte opérationnel et scoring enrichi

Objectif : disposer côté serveur d'un contexte déjà préparé avant l'arrivée
d'une offre. Sources prévues : événements/sorties, trains/perturbations, vols et
terminaux avec délai de débarquement, trafic/fermetures, météo/demande, historique
de zones et majorations observées. La décision de juin priorise selon récurrence
× impact économique, pas uniquement selon difficulté d'implémentation.

Côté interface : une bannière opérationnelle transitoire à la fois, datée,
dismissible, source/confiance disponibles. Détail à l'arrêt avec zone, fenêtre,
impact et signaux manquants. Les recommandations peuvent à terme rester, bouger,
revenir vers Paris, attendre une course programmée ou éviter une zone. Les enums
actuellement exposées restent stay_here/move_to_zone/abstain.

Ne pas afficher trafic « fluide », train « perturbé » ou demande « forte » faute
de donnée. Les providers cités dans les annexes sont des choix du projet, pas
une vérification actuelle de leurs tarifs, disponibilité ou conditions.

## Capture, OCR, majoration et import historique

Capture d'offre future : son détecté avec permission → capture autorisée → OCR
rapide backend → contrôle des champs → features et score. Si Android protège
l'écran, afficher l'indisponibilité et proposer la saisie manuelle. Ne jamais
contourner la protection. Aucune pression de bouton dans Bolt. Il faut mesurer
la latence complète téléphone↔VPS, pas seulement l'inférence du modèle.

Capture de majoration : déclenchement volontaire par bouton de superposition,
image/GPS/date, traitement différé, extraction multiplicateur et zone, puis
corrélation. Pas de capture permanente ni de données d'autres chauffeurs supposées
accessibles. Une confiance OCR faible appelle une vérification.

Import historique (doc 57 §7) : sélectionner plusieurs captures autorisées,
suivre l'extraction/enrichissement, revoir chaque course, corriger prix/durée/zone,
identifier les doublons, exclure les lignes douteuses et confirmer l'import.
Écrans futurs : lots d'import, détail lot, lignes à revoir, bilan. Afficher ce qui
est importé, rejeté, partiel ou repris. Ne pas recréer automatiquement des revenus
Vault déjà existants. Aucun contrat d'import dédié dans le snapshot.

## Smart Fuel — V2, doc 46

Flux cible : kilométrage compteur au départ ; compteur final, consommation
moyenne affichée au tableau de bord (L/100 km), prix payé au litre en fin de
session. Backend : distance = fin − début, litres = distance × consommation/100,
coût = litres × prix. Le frontend ne poste pas ces champs dans SessionStart ou
SessionComplete actuels : les DTO ne les acceptent pas.

Au plein : une seule dépense carburant au Vault, reliée à l'événement carburant.
L'utilisateur ne ventile pas manuellement chaque plein entre pro et perso.
Réconciliation hebdomadaire backend des paiements et de la consommation pro,
avec mécanisme de cumul documenté. Une semaine négative de ventilation n'est
pas forcément une erreur : le paiement et la consommation sont décalés.

Surfaces à prévoir : saisie compteur initial/final, correction traçable,
consommation de session, achats de carburant et statut provisoire/réconcilié.
La ventilation pro/perso reste interne au backend ; le Vault montre le bénéfice
corrigé, pas une ventilation à gérer. Les observations personnelles passent par le WR. Données manquantes clairement indiquées. Les chiffres
actualisent le bénéfice Vault, puis la cible sadaqa Path ; Vector ne calcule pas
une obligation religieuse. La marge sadaqa appartient à The Path.

Le choix intelligent de station/autonomie, lorsqu'il sera raccordé, expose prix,
distance/détour et fraîcheur, avec validation utilisateur. Ne pas fabriquer une
liste de stations ou un stock d'essence. Véhicules multiples : évolution ultérieure.

## HUD — V6+ uniquement après stabilisation V1–V5, doc 55

Vision : la carte devient la surface principale, les autres fonctions des
panneaux contextuels. Ne pas remplacer maintenant le socle session/dashboard.
Deux modes : STANDBY (vue large, diamètre indicatif 50 km dans la vision) et
NAVIGATION (zoom dynamique sur trajet). Le HUD informe ; l'utilisateur décide.

| Couche | Données et interactions futures |
|---|---|
| Zones chaudes | Rentabilité/historique, score, source et fraîcheur, tap pour détail |
| Aviation | Avions/arrivées pertinents, terminal et demande après débarquement |
| Événements | Lieu, horaire de fin, fenêtre de sortie et impact attendu |
| Stations essence | Prix daté, type carburant, détour et lien Smart Fuel |
| Mosquées | Données The Path, horaires/source et proximité ; pas d'inférence de prière accomplie |
| Raccourcis personnels | Entrée/sortie, horaires de validité, gain observé et statut ; seulement itinéraires autorisés |
| Position et trace | GPS actuel, précision, trace récente, pause et usage batterie |
| Voies | Observations par segment/destination/branche, nombre d'échantillons et confiance |

Panneau latéral accordéon : filtre par couche `always`, `driving_only`,
`standby_only`, `never`, puis éléments individuellement visibles/masqués.
Certaines tables de la vision ajoutent transports/incidents : ce sont des
variantes à consolider, pas huit nouvelles APIs déjà définies.

Barre haute : heure et contexte pertinent du backend (session, prière/énergie
uniquement comme affichage de leur domaine). Barre basse prévue : Mission,
Stats, Settings, Tools, ouvrant des panneaux. Tap = détail, double tap/long press
selon usage carte validé, sans cacher une action critique dans un geste obscur.
Thème jour/nuit, fonctionnement dégradé sans réseau, cache daté, pause couches,
réduction rafraîchissement et respect batterie.

Navigation : plan de route/ETA et recalcul futur, pas remplacement universel de
Waze/Google Maps, pas de navigation vocale dans la vision doc 55. Les demandes
vocales d'information sont une autre fonction. Carte et routage sont prévus avec
MapLibre/Valhalla dans le projet, sans obligation de les déployer pour ce kit.

Voies : collecte explicitement activée, contexte directionnel, distinction des
branches et mesures agrégées. Ne pas promettre la détection fiable de la voie à
partir du GPS standard ni encourager changements de voie rapides. Pas de règles
de circulation déduites d'une vieille annexe (voie bus/parking, par exemple).
Les contraintes légales et signalisation réelle priment sur un raccourci personnel.

## Rapport Vector et autres pistes

Rapport hebdomadaire : meilleures/piores zones, pertes retour à vide, pertinence
aéroport/événements, résultats de recommandations et taux horaire mesuré. Le WR
reste dans Imperium. Les propositions de règle sont expliquées, appuyées par des
données et approuvées avant promotion ; pas de réécriture silencieuse du comportement.

Pistes plus lointaines, sans engagement : radar météo sur carte, incidents,
travaux, historique géographique, vue 3D/AR à l'arrêt, Android Auto/CarPlay et
montre. Une mention historique de densité de chauffeurs ne donne aucun droit de
collecter des positions privées ni une garantie de disponibilité des données.
