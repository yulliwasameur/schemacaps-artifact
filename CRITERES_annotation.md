# Guide d'annotation — « argument porteur d'autorité » (SchemaCaps)

**But.** Pour chaque cas (paquet, outil, argument), décider si l'argument est *porteur d'autorité* :
`oui` / `non` / `incertain`. On juge le **rôle sémantique** de l'argument, pas l'existence d'une faille.

**Règle (une phrase).** Un argument est porteur d'autorité si la valeur fournie par l'appelant permet à
l'agent de **(a)** redéfinir la **cible** de l'action, **(b)** **exfiltrer** ou envoyer des données vers une
**destination externe**, **(c)** changer le **principal / locataire** au nom de qui l'action s'exécute, ou
**(d)** changer le **mode ou le moyen d'exécution**. Sinon, `non`.

| Marquer `oui` si la valeur désigne… | Marquer `non` si la valeur ne fait que… |
|---|---|
| une **ressource** touchée : chemin, fichier, dépôt, projet, base, enregistrement, id d'objet créé/modifié/supprimé | **filtrer / chercher / trier** : `query`, `q`, `search`, `filter`, `sort`, `order` |
| une **destination** : URL, webhook, e-mail, endpoint, hôte, canal, bucket | **paginer** : `limit`, `cursor`, `page`, `per_page`, `offset` |
| un **principal / locataire** : compte, owner, tenant, namespace, organisation | porter un **contenu** libre : `body`, `text`, `message`, `content`, `title`, `description` |
| un **exécutable / mode** : interpréteur (`shell`), script exécuté, bascule local→distant (`isUrl`) | un **jeton de concurrence** ou de contrôle : `sha`, `last_commit_id`, `ref` de lecture seule |
| | une **métadonnée** sans effet de cible : `labels`, `milestone`, `is_private`, `encoding` |

**Cohérence — le point qui a fait dérailler le pilote.** Applique la règle **de la même façon à tous les cas
comparables**. Si `webhookUrl` est `oui` (destination), alors `bundleUrl`, `destination`, `metroHost`,
`profileUrl` le sont aussi. Si `path` (gitlab) est `oui` (ressource), alors `path` (agent-device),
`iosXctestrunFile`, `saveScript` le sont aussi. On ne traite pas un cas différemment parce qu'il est
« intéressant » pour le papier.

**Procédure par cas.** 1) Lire paquet / outil / argument. 2) Si le nom ne suffit pas, consulter le schéma ou la
doc de la version indiquée. 3) Choisir `oui` / `non` / `incertain`. 4) Justification courte (une ligne) + source
consultée. `incertain` est un choix légitime pour les cas frontières (ex. un id qui peut être lecture seule ou
cible d'écriture selon l'outil) — précise ce qui manque pour trancher.

**Indépendance (obligatoire pour que le κ ait un sens).**
- **Deux personnes distinctes**, **chacune de son côté**, sans se consulter et sans regarder les réponses de
  l'autre ni une proposition automatique.
- On **ne vise aucun résultat** (ni un κ, ni une précision, ni « sauver » un exemple). On annote, on accepte ce
  qui sort.
- Les **désaccords sont normaux et attendus** (typiquement 10–20 % des cas). C'est eux qui donnent sa valeur au
  κ et à l'arbitrage.
- **Arbitrage** par la troisième personne (Annotateur 3) uniquement sur les cas où les deux diffèrent, après coup.

**Ce que le script produira ensuite** (`agreement.py`, à partir des deux fiches remplies) : l'accord brut, le
**κ de Cohen**, la **précision** de la règle lexicale (parmi les arguments signalés, combien sont confirmés) et
surtout son **rappel** (parmi les arguments jugés porteurs d'autorité, combien la règle avait signalés — la
direction critique en sécurité), plus le décompte validé après arbitrage. Ces chiffres — quels qu'ils soient —
remplaceront le décompte lexical provisoire dans le papier.
