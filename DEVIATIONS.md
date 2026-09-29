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
