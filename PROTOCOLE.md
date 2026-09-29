# SchemaCaps — protocole du pilote (figé le 29/09/2026, avant toute fouille)

## Question
Parmi les évolutions réelles des schémas d'entrée (`inputSchema`) des outils de serveurs MCP publiés,
combien sont *compatibles* (tout ancien appel reste valide) tout en *élargissant* l'autorité sur un
argument porteur d'autorité ? Combien de ré-approbations une règle de non-amplification évite-t-elle
par rapport à l'épinglage d'empreinte ?

## Corpus (règle écrite avant la fouille)
- **Strate A — serveurs de référence officiels.** Tous les paquets npm `@modelcontextprotocol/server-*`
  qui sont des serveurs MCP exécutables (hors SDK, bibliothèques et squelettes), et les paquets PyPI
  officiels `mcp-server-fetch`, `mcp-server-git`, `mcp-server-time`, `mcp-server-sqlite`.
- **Strate B — serveurs tiers les plus adoptés.** Les 15 paquets npm les plus téléchargés (téléchargements
  hebdomadaires, API de recherche npm au 29/09/2026) portant le mot-clé `mcp-server` ou `mcp`, qui sont
  des serveurs MCP stdio lançables sans compte (hors SDK, frameworks, clients, proxies).
- **Fenêtre :** toutes les versions stables (sans suffixe de pré-version) publiées du 01/01/2025 au 29/09/2026.

## Extraction
- Chaque version est installée isolément (`npm install <pkg>@<v>` ou `pip install <pkg>==<v>` dans un venv),
  lancée en stdio avec des arguments neutres (répertoire temporaire, jetons factices), interrogée par
  `initialize` puis `tools/list` (délai 60 s).
- Les schémas sont archivés tels quels, avec l'empreinte SHA-256 de leur forme JSON canonique.
- Une version qui ne démarre pas ou ne répond pas est **comptée et exclue**, jamais reconstruite.

## Classement d'une paire de versions successives (par outil)
- Outil ajouté / retiré / inchangé (empreinte identique) / modifié.
- Pour un outil modifié : `compatible` si S_old ⊆ S_new (tout ancien appel valide) ; `resserré` si S_new ⊆ S_old ;
  décidé par `jsonsubschema` (correct mais incomplet : « indécis » quand il échoue).
- **Amplifiant** si, sur au moins un argument porteur d'autorité, S_new admet des valeurs que S_old refusait
  (projection du schéma sur cet argument, S_new_a ⊄ S_old_a), ou si un nouvel argument porteur d'autorité apparaît.
- Rôles porteurs d'autorité : annotation **provisoire** par règle lexicale (destinataire, chemin, URL, dépôt,
  compte, commande, requête SQL, identifiant de ressource...), publiée en entier, **à valider par deux annotateurs
  humains** (Annotateur 1, Annotateur 2) avant tout usage dans le papier.

## Règles comparées
1. Épinglage d'empreinte (type ETDI / Vercel detectToolDrift) : tout outil modifié ⇒ ré-approbation.
2. Compatibilité : un outil modifié compatible passe sans ré-approbation.
3. Non-amplification (SchemaCaps) : ré-approbation ssi amplifiant ou indécis.

## Mesures
Paires, outils modifiés, compatibles, compatibles-et-amplifiants, ré-approbations par règle, taux d'indécis,
échecs d'extraction. Tous les nombres sont produits par les scripts du dépôt, jamais tapés à la main.

## Critère d'arrêt
Si aucune évolution compatible-et-amplifiante n'est trouvée, le résultat est rapporté tel quel.
