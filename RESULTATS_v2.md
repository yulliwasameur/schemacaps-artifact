# SchemaCaps — résultats du pilote, classement v2 (écarts 8 et 9 ; générés par report2.py)

| Strate | Paires | Schémas modifiés | Compatibles | CA noyau | CA strict | Accept-all | Épinglage | Compat | Non-amp |
|---|---|---|---|---|---|---|---|---|---|
| A | 337 | 87 | 63 | 0 | 31 | 0 | 109 | 24 | 34 |
| B | 228 | 1110 | 517 | 84 | 226 | 0 | 1895 | 593 | 361 |
| Total | 565 | 1197 | 580 | 84 | 257 | 0 | 2004 | 617 | 395 |

- Noyau (argument d'autorité déclaré ajouté ou élargi) : 84 des 580 évolutions compatibles (14.5 %) ; répartition : agent-device (42), @sentry/mcp-server (20), @wonderwhy-er/desktop-commander (10), @zereight/mcp-gitlab (8), @notionhq/notion-mcp-server (3), firecrawl-mcp (1).
- Strict (définition 1) : 257 évolutions compatibles. Raisons parmi les compatibles : object_opened 129, new_authority_arg 80, became_optional 26, nullable 17, object_introduced_open 17, constraint_dropped 14, unresolved_ref 11, cross_constraint 10, widened 6, hint_raised 1.
- Ré-approbations : épinglage 2004 ; compatibilité 617 ; non-amplification stricte 395 (80.3 % de moins que l'épinglage) ; noyau seul 150.
- Indécis (règle d'amplification) : 19. Outils ajoutés : 907 (dont 721 avec un chemin d'autorité).
- Témoins sur le noyau : {'widened:found': 6, 'new_authority_arg:found': 126} ; contrôle de correction sur les « compatible = oui » : {'not_found': 580}.
- Temps de classement d'un outil modifié : médiane 5.9 ms, p99 141.2 ms.

**Réserve.** Rôles d'autorité par règle lexicale ; validation humaine en cours (176 cas, `agreement.py`).
