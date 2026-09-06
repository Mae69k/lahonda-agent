# LaHonda Agent 🤖

Bot Discord de modération complet — permissions par rôle, warns, cases, anti-spam, anti-lien, anti-raid, anti-nuke, quarantaine, logs et mode panique.

## Structure du projet

```
lahonda-agent/
├── main.py                 # Point d'entrée du bot
├── requirements.txt
├── Procfile                 # Pour Railway
├── .env.example
├── .gitignore
├── utils/
│   ├── database.py          # Base de données SQLite (aiosqlite)
│   └── permissions.py       # Système de permissions à 4 niveaux
└── cogs/
    ├── config.py             # /config role..., /permissions, /permission command
    ├── moderation.py         # warn, kick, ban, timeout, purge, case, etc.
    ├── antispam.py           # /antispam ...
    ├── antilink.py           # /antilink ...
    ├── antiraid.py           # /antiraid ..., /lockdown ...
    ├── antinuke.py           # /antinuke ...
    ├── security.py           # /quarantine, /security ..., /panic ...
    ├── logs.py               # /logs ...
    └── info.py               # /userinfo, /serverinfo
```

## Toutes les commandes

**Permissions** : `/config role creator|admin|moderator|member`, `/permissions`, `/permission command`

**Modération** : `/warn`, `/warnings`, `/unwarn`, `/clearwarnings`, `/timeout`, `/untimeout`, `/kick`, `/ban`, `/unban`, `/purge`, `/slowmode`, `/lock`, `/unlock`, `/nick`, `/note`, `/history`, `/case view|edit|reason`

**Anti-spam** : `/antispam enable|disable|status|config`

**Anti-lien** : `/antilink enable|disable|status`, `/antilink whitelist add|remove|list`, `/antilink blacklist add|remove|list`

**Anti-raid** : `/antiraid enable|disable|status|config`, `/lockdown enable|disable|status`

**Anti-nuke** : `/antinuke enable|disable|status|config`

**Sécurité** : `/quarantine`, `/unquarantine`, `/security scan|permissions|status|report`, `/panic enable|disable`

**Logs** : `/logs setup|moderation|security|members|messages|server`

**Info** : `/userinfo`, `/serverinfo`

Chaque commande a un niveau minimum requis par défaut (Member/Moderator/Admin/Creator), modifiable avec `/permission command`.

---

## 🚀 Déploiement complet sur Railway (de GitHub au 24/7)

### Étape 1 — Créer le bot sur Discord

1. Va sur https://discord.com/developers/applications → **New Application**
2. Onglet **Bot** → **Reset Token** → copie le token (garde-le secret, jamais dans le code)
3. Toujours dans **Bot**, active :
   - `SERVER MEMBERS INTENT`
   - `MESSAGE CONTENT INTENT`
4. Onglet **OAuth2 → URL Generator** :
   - Scopes : `bot`, `applications.commands`
   - Permissions : `Administrator` (le plus simple pour un bot de modération complet), ou au minimum Kick/Ban/Moderate Members/Manage Channels/Manage Roles/Manage Messages
5. Copie l'URL générée en bas de page, ouvre-la dans ton navigateur et invite le bot sur ton serveur

### Étape 2 — Mettre le code sur GitHub

1. Crée un nouveau dépôt sur https://github.com/new (peut être privé)
2. Sur ta machine, dans le dossier du projet dézippé :
   ```bash
   git init
   git add .
   git commit -m "Initial commit - LaHonda Agent"
   git branch -M main
   git remote add origin https://github.com/TON_PSEUDO/lahonda-agent.git
   git push -u origin main
   ```
   ⚠️ Le `.gitignore` fourni exclut déjà `.env` et la base de données — ton token ne sera jamais poussé sur GitHub.

### Étape 3 — Créer le projet sur Railway

1. Va sur https://railway.app et connecte-toi avec ton compte GitHub
2. **New Project** → **Deploy from GitHub repo**
3. Sélectionne ton dépôt `lahonda-agent`
4. Railway détecte automatiquement le `Procfile` et installe les dépendances via `requirements.txt`

### Étape 4 — Configurer les variables d'environnement

1. Dans ton projet Railway, va dans l'onglet **Variables**
2. Ajoute une variable :
   - `DISCORD_TOKEN` = ton token copié à l'étape 1
3. Railway redéploie automatiquement dès qu'une variable change

### Étape 5 — Vérifier le déploiement

1. Onglet **Deployments** → clique sur le déploiement en cours → **View Logs**
2. Tu dois voir apparaître :
   ```
   ✅ Connecté en tant que LaHonda Agent#1234
   📡 Présent sur 1 serveur(s)
   🔄 X commande(s) slash synchronisée(s)
   ```
3. Si tu vois une erreur `DISCORD_TOKEN introuvable`, vérifie l'orthographe exacte de la variable dans Railway

### Étape 6 — Faire tourner le bot en 24/7

Par défaut, Railway garde ton service actif tant que le plan (gratuit ou payant) a des crédits/heures disponibles — un `worker` (notre cas, pas un service web) tourne en continu sans se mettre en veille, contrairement à un service web sans requêtes entrantes. Pour garantir la stabilité :

1. Onglet **Settings → Restart Policy** : mets `Always` pour que Railway relance le bot automatiquement en cas de crash
2. Si tu es sur le plan gratuit, surveille ta consommation d'heures dans **Usage** — passe sur un plan payant (Hobby, ~5$/mois) si tu veux un fonctionnement garanti sans interruption
3. Chaque `git push` sur ta branche `main` redéploie automatiquement le bot avec le nouveau code (CI/CD intégré)

### Étape 7 — Configuration initiale sur ton serveur Discord

Une fois le bot en ligne, configure-le directement dans Discord :

```
/config role creator @Fondateurs
/config role admin @Admins
/config role moderator @Modérateurs
/config role member @Membres

/logs setup #logs
/antispam enable
/antilink enable
/antiraid enable
/antinuke enable
```

Et voilà, ton bot tourne en 24/7 et est entièrement configuré. 🎉

## Prochaines étapes possibles

- Migrer vers PostgreSQL (Railway propose une base gratuite) si le bot grossit sur plusieurs serveurs
- Ajouter un tableau de bord web pour la configuration
- Système de tickets de support
