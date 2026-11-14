# Écarts au protocole (datés, écrits avant l'extraction)

1. **29/09/2026 15:35 UTC — plafond de 20 versions par paquet.** La fenêtre contient 1 856 versions stables
   (46 paquets). Pour tenir dans le budget d'une session, chaque paquet contribue au plus 20 versions, choisies à
   intervalles réguliers dans la liste triée par date de publication, première et dernière incluses (toutes si ≤ 20).
   Conséquence : une « paire successive » peut couvrir plusieurs versions publiées ; elle représente l'évolution vue
   par un client qui met à jour à cette cadence. Le nombre de versions publiées entre deux versions échantillonnées
   est enregistré pour chaque paire.
2. **29/09/2026 15:35 UTC — paquets sans version dans la fenêtre.** `server-google-maps`, `server-brave-search`,
   `server-postgres`, `server-everart` n'ont aucune version stable dans la fenêtre : ils sont listés et exclus.
3. **29/09/2026 15:35 UTC — squelettes exclus de la strate A.** `server-basic-{preact,react,solid,svelte,vanillajs,vue}`
   sont des gabarits d'application (exclus par la règle « hors squelettes »).
4. **29/09/2026 15:35 UTC — strate B.** Les 15 paquets retenus, dans l'ordre des téléchargements hebdomadaires
   (fichier `npm_search_2026-09-29.json`) : @storybook/mcp, @upstash/context7-mcp, agent-device,
   @notionhq/notion-mcp-server, firecrawl-mcp, hostinger-api-mcp, @azure/mcp, @sentry/mcp-server,
   @zereight/mcp-gitlab, @wonderwhy-er/desktop-commander, @ui5/mcp-server, n8n-mcp, figma-developer-mcp,
   openinputbridge-mcp, nx-mcp. Exclus comme SDK, frameworks, clients, proxies ou installateurs : @modelcontextprotocol/sdk,
   ai, claude-cup, @modelcontextprotocol/{core,server,client,node,express,hono}, @ai-sdk/mcp, agent-install,
   @storybook/addon-mcp, @assistant-ui/react, fallow, yahoo-finance2, mcp-handler, eve, mcp-remote, @copilotkit/aimock,
   mcporter, @reactuses/core, pi-mcp-adapter, @blaxel/core, @better-auth/mcp, @lovable.dev/mcp-js, @posthog/mcp,
   @langchain/mcp-adapters, @better-auth/cimd, @clerk/mcp-tools, add-mcp, @devframes/agentic,
   @raishin/vanguard-frontier-agentic, @payloadcms/plugin-mcp, agentdb, mockserver-client, ruvector, @oh-my-pi/pi-mnemopi, agentic-flow, @usenotra/geo, supergateway, @mcp-b/transports, @mcp-b/global, @modelcontextprotocol/hono, @mcp-b/webmcp-ts-sdk, blume, @tanstack/ai-mcp, @sap-ux/fiori-docs-embeddings, cline, @copilotkit/mcp-apps-renderer, @github/mcp-registry, easy-skills, pi-mcp-extension, @azure/mcp-win32-x64 (bibliothèques, bases vectorielles, harnais d'agents, passerelles, binaires de plateforme).
5. **29/09/2026 16:05 UTC — résolution des dépendances à la date de publication (correction d'un biais de mesure).**
   Le premier lancement installait chaque ancienne version avec les dépendances *actuelles* (plages `^` résolues en 2026).
   Pour plusieurs serveurs officiels, cela produit des schémas vides (incompatibilité zod / zod-to-json-schema apparue
   après la publication) : un artefact de reproduction, pas l'évolution réellement vue par les utilisateurs.
   Toutes les extractions sont refaites avec `npm install --before=<publication + 1 jour>` et
   `uv pip install --exclude-newer <publication + 1 jour>`. Les résultats du premier lancement sont archivés dans
   `raw_run1/` et écartés.
6. **29/09/2026 19:10 UTC — seconde passe d'extraction avec un client JSON-RPC brut.** Le diagnostic des échecs
   « no_response » montre que plusieurs serveurs répondent correctement à `tools/list` (Desktop Commander 0.2.x,
   Azure MCP, nx-mcp) mais que le client du SDK Python rejette la réponse (validation stricte des modèles, ou
   arguments de lancement différents pour Azure : `server start --transport stdio`). Les versions en échec sont
   rejouées une fois avec un client JSON-RPC minimal sans validation (`extract_raw.py`, délai 35 s par variante de lancement). Les versions
   récupérées portent `client: raw_jsonrpc_pass2`. Aucune version réussie en première passe n'est modifiée.
7. **29/09/2026 20:00 UTC — règle « paramètre retiré d'un objet ouvert » sortie du compte principal.** L'inspection
   des cas Hostinger et Azure montre que `constraint_dropped` correspond surtout à un paramètre porteur d'autorité
   *retiré* de la déclaration d'un objet resté ouvert (`additionalProperties` absent) : la valeur n'est plus contrainte
   par le schéma, mais l'effet côté serveur est inconnu (paramètre ignoré ou déplacé). Ces cas ne comptent plus comme
   amplifiants dans le résultat principal ; ils sont rapportés à part, comme borne haute.

---
**Erratum (29/09/2026, ajouté après relecture).** (a) Les heures des écarts 6 et 7 ont été notées à l'heure de Paris
et non en UTC : d'après les dates de modification des fichiers, l'écart 6 date de 17:29 UTC (`extract_raw.py`) et
l'écart 7 de 17:40 UTC (`classify.py`, `DEVIATIONS.md`). (b) L'en-tête « écrits avant l'extraction » ne vaut que pour
les écarts 1 à 4 ; les écarts 5 à 7 ont été décidés après avoir vu des résultats intermédiaires. (c) Écart 1 : 45
paquets ont au moins une version dans la fenêtre (le « 46 » comptait un paquet sans version stable).

8. **29/09/2026, après la relecture adversariale — classement v2 (`classify2.py`, `witness2.py`).** La relecture a
   montré que `classify.py` ne décide pas la définition du papier : il ignore `required` (une valeur devenue facultative),
   les valeurs par défaut, les chemins imbriqués, l'ouverture d'objet et le retrait d'une déclaration sur objet ouvert ;
   il manque deux cas à cause d'un test `bool(properties)` au lieu de la fermeture de l'objet ; il traite `string→string|null`
   comme un élargissement ; et `witness.py` perd les témoins égaux à `null`. `classify2.py` corrige ces points, applique la
   précondition « produit » (combinateur dans l'ancien schéma sur le chemin d'un argument d'autorité → indécis) et relève
   les indices d'outil MCP (`readOnlyHint`, `destructiveHint`, `openWorldHint`). Les résultats v1 restent archivés
   (`results/changes.csv`, `pairs.csv`, `summary.json`) ; le papier rapporte v2 et donne l'écart avec v1.
   Les feuilles d'annotation passent de 65 à 158 cas (46 signalés, 112 non signalés pour mesurer le rappel).

9. **29/09/2026, après la seconde relecture — compléments à `classify2.py`** (version de l'écart 8 archivée dans
   `classify2_dev8.py`, résultats dans `results/v2_dev8_*`). Ajouts : sous-objet nouveau et ouvert sous un ancêtre fermé
   (nouvelle coordonnée ⋆), `additionalProperties` typé comparé par le vérificateur, descente dans les branches
   `anyOf/oneOf/allOf` de la nouvelle version (union des branches), `$ref` non résolu → indécis,
   `minProperties/maxProperties/propertyNames/patternProperties` ajoutés à la précondition « produit », disparition
   d'une valeur par défaut, indices d'outil relevés intégrés à la règle. Effet : ré-approbations de la règle stricte
   343 → 395 ; noyau compatible-et-amplifiant inchangé (84). Feuilles d'annotation régénérées (176 cas : 44 signalés,
   132 non signalés), colonne « Modification » neutralisée pour ne pas révéler le groupe.

10. **30/09/2026, révision 2 après relecture externe stricte** (versions précédentes archivées : `classify2_dev9.py`,
   `results/v2_dev9_*`, `prototype/archive/`).
   (a) *06:07 UTC, non consigné à l'époque, consigné ici :* `nullable` ajouté à l'ensemble « demander » (`null` ≠
   absence, §2) et sentinelle de l'oracle corrigée (un témoin `null` était écarté). Effet : 395 → 412 ré-approbations,
   257 → 274 compatibles strictement amplifiants.
   (b) Un objet fermé qui devient `{}`, `true` ou non contraint est une ouverture (`object_opened`) ; un retrait d'un
   parent resté fermé est une restriction ; un changement de forme demande (`shape_changed`). Effet sur le corpus : nul.
   (c) `jsonsubschema` est incorrect pour un booléen non restreint comparé à un booléen restreint par `enum`/`const`
   (3 sondes sur 20). Normalisation des booléens + garde par contre-exemple (Hypothesis, 60 tirages, 2 s, graine fixe) sur
   tout verdict « ⊆ ». Effet sur le corpus : garde appelée 407 fois (lexical) / 467 (sans étiquettes), 0 verdict
   renversé, 0 échec de génération (garde sans signal, borne de temps vérifiée dans le test).
   (d) Étiqueteurs : mode sans étiquettes (rôle inconnu ⇒ autorité, défaut du proxy) ajouté ; le coût est rapporté
   pour les deux ; la règle lexicale reste une heuristique dont le rappel est mesuré.
   (e) Oracle v2 : audite toute re-liaison silencieuse (compatible, incompatible, compatibilité indécise), tirages
   déterministes, échecs de génération comptés ; en mode sans étiquettes, inclusion du schéma entier et défauts.
   (f) Changements incompatibles : décision explicite — la règle est orthogonale à la compatibilité ; un changement
   incompatible non amplifiant est re-lié sans demande (des appels peuvent échouer, aucune autorité n'est gagnée).
   (g) Proxy révision 2 : manifeste versionné et h_A, U cumulatif, P et h_P, identité du serveur, validation des appels,
   politique sur chemins imbriqués et éléments de tableaux, `null` ≠ absence, défauts déclarés, reçus à SHA-256 complet
   numérotés et chaînés, commande `verify`, boucle mono-fil (pas de concurrence entre traitement des listes et des appels sur l'état des capacités).
   (h) Rejeu réel sur les paires exactes de versions (Table 5) ; surcoût re-mesuré. (i) `robustness.py` ajouté
   (régénère l'intervalle par rééchantillonnage des paquets, graine fixe : [3,5 ; 25,2] % contre [3,4 ; 25,2] % publié).
   (j) Double annotation indépendante achevée (176 cas) et arbitrage des 29 désaccords. (k) Manifeste par version
   avec empreintes des registres (`results/releases.csv`).


## Écart n° 11 — 14/11/2026, version finale (post hoc)

Un banc à référence exacte (`adversarial_bench.py`, `make adversarial` ; graine fixe ; fragment de JSON Schema à
domaines finis tranché par énumération, indépendamment de `jsonsubschema`) a été ajouté à la demande d'un relecteur.
Il a révélé deux cas où la règle soumise re-liait en silence un changement amplifiant :

- **(a)** une déclaration requise ou munie d'un défaut retirée d'un objet fermé : sa valeur effective devient ⊥,
  que l'ancienne marge excluait. La règle demande désormais (`removed_to_bottom`) ; l'oracle label-free avait le même
  angle mort (il ne comparait les défauts que sur les chemins présents dans les deux versions) et le signale désormais.
- **(b)** un champ nouvellement déclaré sur un objet dont l'ancienne version ne l'admettait que par un
  `additionalProperties` typé : la nouvelle déclaration doit rester incluse dans ce schéma (`declared_beyond_star`).

Quatre tests de régression ajoutés (48 au total). Effet sur le pilote : aucun nombre label-free ne change ; en mode
lexical, une ré-approbation de plus (412 → 413, total 1 319 → 1 320) et un re-lien silencieux de moins audité par
l'oracle. Les temps de décision et le surcoût sont ceux de la mesure d'origine (x86-64, 2 cœurs, règle soumise) ; la
correction n'ajoute des appels au vérificateur gardé (≤ 2 s chacun) que pour les déclarations retirées et les champs
nouvellement déclarés sous un `additionalProperties` typé.

**Seconde graine (déclarée avant exécution, 14/11/2026, 16:13 UTC).** La règle corrigée ayant d'abord été évaluée
sur le banc même qui avait révélé les trous (graine 20261114, post hoc), un second tirage du même générateur utilise la
graine **20270223**, consignée ici avant d'être lancée (auto-attesté, comme l'horodatage du protocole) (`BENCH_SEED=20270223 BENCH_OUT=adversarial_bench_seed2.json`). Les
deux exécutions sont rapportées. La garde est bornée en temps (2 s par inclusion) : le banc est déterministe sur une
machine donnée mais pourrait en principe différer sur une machine beaucoup plus lente ; le critère de reproduction est
0 re-lien silencieux erroné de la règle corrigée et 0 fausse acceptation du vérificateur gardé.

**Analyses ajoutées pour la version finale après les audits (14/11/2026, post hoc).** (i) `simple_pin.py` mesure la
règle la plus simple, « épingler sauf si le nouveau schéma d'entrée est inclus dans l'ancien » (vérificateur gardé,
schéma entier, descriptions et valeurs effectives ignorées), sur le pilote et les deux graines du banc. (ii)
`agreement.py` publie aussi les deux composantes de K (changements signalés par le lexique et confirmés après
arbitrage ; changements portés par des arguments d'autorité que le lexique a manqués). Aucun nombre antérieur ne change.
