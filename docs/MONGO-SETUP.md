# MongoDB — grant access to the `kfc` database

## The problem you hit

```
MongoServerError: not authorized on kfc to execute command { delete: "products" ... }
code: 13, codeName: 'Unauthorized'
```

Your connection + password are correct — the user `agent_user_1` logged in fine.
But that user's role only covers the `camp_ads` database, so it can't
read/write the new `kfc` database yet. Fix: grant it `readWrite` on `kfc`.

You do this once, on the VPS, as a Mongo **admin** user (the root/admin account
you created when you enabled auth — NOT `agent_user_1`, which lacks the
privilege to grant roles).

---

## Step 1 — open a mongo shell on the VPS (Bitvise → terminal)

**If Mongo runs in Docker** (the Claw-a-thon setup did):

```bash
docker ps                     # find the mongo container name, e.g. "mongo" or "*_mongo_1"
docker exec -it <mongo_container> mongosh -u <ADMIN_USER> -p --authenticationDatabase admin
```

**If Mongo runs natively on the host:**

```bash
mongosh "mongodb://127.0.0.1:27017/admin" -u <ADMIN_USER> -p
```

Enter the admin password when prompted. `<ADMIN_USER>` is your root/admin
account (often `admin` or `root`).

> Don't know the admin user? Run without `-u/-p` if the server allows localhost
> access, or check how auth was set up. As a fallback you can look at existing
> users (see Step 3).

---

## Step 2 — grant readWrite on `kfc`

Inside the mongo shell:

```javascript
db.grantRolesToUser("agent_user_1", [{ role: "readWrite", db: "kfc" }])
```

That's it. (Mongo creates the `kfc` database automatically on first write, so
no need to create it explicitly.)

Verify the grant took:

```javascript
db.getUser("agent_user_1")
// look for:  roles: [ { role: 'readWrite', db: 'camp_ads' }, { role: 'readWrite', db: 'kfc' } ]
```

Exit with `exit`.

---

## Step 3 — finding the admin credentials

`grantRolesToUser` is an admin command, so you MUST be authenticated as a user
that has role-management rights (`root`, or `userAdmin`/`userAdminAnyDatabase`).
Connecting with no `-u/-p` (as you did) gives zero privileges → "requires
authentication". And `agent_user_1` almost certainly lacks the grant privilege.

### 3a. First, just try agent_user_1 — it might have admin rights

```bash
mongosh "mongodb://agent_user_1:pawngrammers@127.0.0.1:27017/?authSource=admin"
```
```javascript
db.getUser("agent_user_1")   // look at its "roles"
```
If `roles` contains `root`, `userAdminAnyDatabase`, or `userAdmin` on admin, run
the Step 2 grant right here and you're done. If it only has `readWrite` on
`camp_ads`, go to 3b.

### 3b. Find the root/admin account

If Mongo runs in **Docker** and was created with root env vars, read them:
```bash
docker ps
docker inspect <mongo_container> --format '{{json .Config.Env}}'
# look for MONGO_INITDB_ROOT_USERNAME / MONGO_INITDB_ROOT_PASSWORD
```
Also check the Claw-a-thon project on the VPS for a compose/.env with those vars.

Then connect as that admin user and do Step 2:
```bash
mongosh "mongodb://<ADMIN_USER>:<ADMIN_PASS>@127.0.0.1:27017/admin?authSource=admin"
```
```javascript
db.grantRolesToUser("agent_user_1", [{ role: "readWrite", db: "kfc" }])
```

### 3c. Last resort — no admin user exists / lost

Temporarily restart mongod without auth, create/fix a user, then re-enable.
⚠️ This briefly makes the DB open and restarts it (may interrupt your live
Claw-a-thon agent). Only if 3a/3b fail — ping me and I'll give exact steps for
your setup (native vs Docker).

---

## Step 4 — re-run the seed (from your laptop, project root)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\seed.ps1
```

Now the seed writes to `kfc` successfully. Verify:

```bash
cd backend && npm start
curl http://localhost:3000/api/admin/stats
```

---

## Alternative (quick but broad)

If you'd rather not scope per-database, you can give the user access to all DBs:

```javascript
db.grantRolesToUser("agent_user_1", [{ role: "readWriteAnyDatabase", db: "admin" }])
```

Scoped `readWrite` on `kfc` (Step 2) is cleaner and recommended.
