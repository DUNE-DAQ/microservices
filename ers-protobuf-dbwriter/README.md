# ERS Database Performance Optimization

## 🚀 The Problem
The ERS dashboard was slow because the "ERSstream" table lacked indexes. Every refresh triggered a **Sequential Scan**, reading every row on disk. This took ~236 seconds (4 minutes) for only 500k rows.

## 🛠 The Fix
Apply a **Composite B-Tree Index** on `(session, "time" DESC)`. This allows PostgreSQL to jump directly to specific session logs without a manual sort.

### 1. Optimized Grafana Query
Update your dashboard SQL to avoid mathematical operations on the "time" column itself.

```sql
SELECT 
    severity, 
    time/1000000 as time, 
    application_name, 
    message, 
    issue_name, 
    host_name
FROM "ERSstream"
WHERE session='${session}' 
  AND time >= $__from * 1000000 
  AND time <= $__to * 1000000
ORDER BY time DESC
LIMIT 500
```

### 2. Production Application (Safe)
Run this inside the `ApplicationDbErrorReporting` database. The `CONCURRENTLY` keyword ensures the DAQ pipeline stays online while the index builds.

```sql
CREATE INDEX CONCURRENTLY idx_ersstream_session_time 
ON "ERSstream" (session, "time" DESC);
```

## 📈 Results
* **Before Index:** ~236,000 ms (4 minutes)
* **After Index:** ~24 ms
* **Improvement:** 10,000x Speedup

---

## 💡 Troubleshooting Tips & Tricks

### How to access the Database Pod
Access the database using the environment variables already defined in the pod's container.
```bash
# Uses the pod's internal environment variable (injected via K8s secrets) to authenticate automatically
kubectl exec -it <pod_name> -n ers -- sh -c 'psql $DATABASE_URI'
```

### Useful PostgreSQL Commands
Once inside the `psql` prompt:
* **List all databases:** `\l`
* **Connect to the ERS database:** `\c ApplicationDbErrorReporting`
* **List all tables:** `\dt`
* **Show table schema/indexes:** `\d "ERSstream"`

### Safe Exits
* **Exit query results (pager):** Press `q`
* **Exit psql prompt:** Type `\q` or `Ctrl+D`
* **Exit pod session:** Type `exit` or `Ctrl+D`

### Testing Performance
Use these to verify if the index is working:

**Standard Query Example:**
```sql
SELECT * FROM "ERSstream" WHERE session = '<session>' LIMIT 10;
```

**Analyze Performance:**
Adding `EXPLAIN ANALYZE` before any query shows you exactly how the database is finding the data (Look for "Index Scan" vs "Seq Scan").
```sql
EXPLAIN ANALYZE 
SELECT * FROM "ERSstream" 
WHERE session = '<session>' 
ORDER BY time DESC 
LIMIT 10;
```

