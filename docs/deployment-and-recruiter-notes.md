# Deployment & recruiter notes

Consolidated from project chat: EC2/ALB/DNS security and ways to strengthen the portfolio for tech recruiters.

---

## How to know the EC2 public DNS and IP are secured

### What “secured” means here

The EC2 **public IP and public DNS always exist** on a public instance. Security is not hiding them—it’s **blocking traffic** except what you intend.

The `sde_security_group` is set up so:

| Port | Who can connect |
|------|------------------|
| **8080** (Airflow) | Only the **ALB** security group—not the open internet |
| **22** (SSH) | IPs in `var.admin_cidr_blocks` (default **`0.0.0.0/0`** = whole internet) |

So **Airflow on the EC2 IP is meant to be closed from the internet**; **SSH may still be wide open** unless you changed `admin_cidr_blocks`.

### Traffic flow

```text
Users  →  Cloudflare (your domain)  →  ALB DNS  →  EC2 :8080 (Airflow)
You    →  EC2 public IP :22 (SSH only)
```

### What stays / what to use after deploy

| Endpoint | Stays? | Use for |
|----------|--------|---------|
| **Cloudflare domain** (e.g. `airflow.yourdomain.com`) | Yes — **main URL** | Browsers, team, bookmarks, CI smoke tests |
| **ALB DNS** (`*.elb.amazonaws.com`) | Yes — AWS resource | **Cloudflare CNAME target**; direct hit for debugging |
| **EC2 public IP** | Yes | **SSH / debugging** — not Airflow UI in prod |
| **EC2 public DNS** | Yes | Same as IP — optional for SSH |

**Airflow UI:** `http://airflow.yourdomain.com` (or `https://` with ACM + Cloudflare). Do **not** share `http://<ec2-ip>:8080` for normal use.

### 1. Check in AWS (source of truth)

**Console:** EC2 → Instances → your instance → **Security** tab → inbound rules.

You want:

- **8080** → Source = ALB security group, **not** `0.0.0.0/0`
- **22** → Source = **your IP**/32 (not `0.0.0.0/0` in production)

**CLI:**

```bash
INSTANCE_ID=$(terraform -chdir=terraform output -raw ec2_instance_id)
aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].{PublicIp:PublicIpAddress,PublicDns:PublicDnsName,SecurityGroups:SecurityGroups}' \
  --output table

SG_ID=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' --output text)

aws ec2 describe-security-groups --group-ids "$SG_ID" \
  --query 'SecurityGroups[0].IpPermissions' --output table
```

### 2. Test from your laptop

```bash
EC2_IP=$(terraform -chdir=terraform output -raw ec2_public_ip)

# Airflow on EC2 should FAIL from internet
curl -v --max-time 5 "http://${EC2_IP}:8080/health"

ALB=$(terraform -chdir=terraform output -raw alb_dns_name)
curl -v --max-time 5 "http://${ALB}/health"
```

**Expected if 8080 is secured:**

- `curl` to `http://<ec2-ip>:8080` → **fails**
- `curl` to ALB or Cloudflare URL → **works**

### 3. External scan (optional)

```bash
nmap -Pn -p 22,8080,80,443 <ec2_public_ip>
```

- **8080 closed/filtered** on EC2 IP → good
- **22 open** → SSH exposed to whatever CIDR is in the SG

### 4. Secured vs still risky

| Item | Status |
|------|--------|
| Airflow not on EC2 IP from internet | **Good** — 8080 only from ALB SG |
| Airflow for users | **Via ALB + Cloudflare** |
| EC2 IP/DNS “secret” | **No** — always discoverable |
| SSH | **Weak by default** — `admin_cidr_blocks = ["0.0.0.0/0"]` |
| ALB 80/443 | Open to internet (normal); WAF helps if enabled |

**Tighten SSH** in `terraform.tfvars`:

```hcl
admin_cidr_blocks = ["YOUR.HOME.IP/32"]
```

### 5. Quick checklist

- [ ] EC2 inbound **8080** source = ALB security group only
- [ ] EC2 inbound **22** ≠ `0.0.0.0/0`
- [ ] `curl http://EC2_IP:8080` fails from your machine
- [ ] `curl http://ALB_DNS/health` or Cloudflare URL succeeds
- [ ] No direct Airflow URL shared (`:8080` on IP)
- [ ] (Optional) WAF on ALB, HTTPS + Cloudflare Full (strict)

**Bottom line:** EC2 public IP/DNS are **secured for Airflow** when port **8080 is not reachable on the EC2 IP** but **is reachable through the ALB/domain**. Restrict SSH to your IP for full hardening.

### Cloudflare + ALB (DNS not in Route53)

1. `terraform output alb_dns_name`
2. Cloudflare **CNAME** `airflow` → that ALB name (grey cloud first for testing)
3. Confirm `http://airflow.yourdomain.com/health`
4. For HTTPS: ACM in AWS → validation CNAMEs in Cloudflare → HTTPS listener on ALB → Cloudflare **Full (strict)**

---

## 10 ways to make this project more impressive for tech recruiters

### 1. One-page architecture doc + diagram (your design)

Add `docs/architecture.md` with: Cloudflare → ALB → EC2 → Docker (Airflow/Postgres), CoinCap API → CSV → quality → Quarto, and what Terraform owns. Link at the top of README; replace template clone URLs with **your** repo story.

### 2. Turn on CI and make it green

`.github/workflows/ci.yml` is commented out. Enable `make ci` on every PR (lint, `pytest`, DAG import tests). Badge the README: **CI passing**.

### 3. End-to-end data quality story with metrics

Extend Cuallee in `coincap_elt.py`: publish check results to a table or JSON artifact, fail the DAG on `FAIL`, trend completeness over time. Mention **SLAs / data contracts** in README.

### 4. Real warehouse layer

README mentions DuckDB/MinIO; add one layer: **DuckDB** staging → mart after CSV, or **S3/MinIO** raw zone. One SQL model file shows medallion thinking, not only orchestration.

### 5. Infrastructure as a narrative: `terraform apply` → live URL

Document Cloudflare + ACM + HTTPS; outputs for `airflow_url` and cost ($5 budget). Short **Deployment runbook**: apply, DNS CNAME, `/health` check.

### 6. Secrets and config hygiene

No committed secrets; SSM or GitHub Actions secrets for prod; Airflow Connections via env/secrets backend. README: “secrets locally vs AWS.”

### 7. Observability you can demo

Use `observability.tf`: CloudWatch dashboards (ALB 5xx, target health, EC2 CPU), log groups, optional structured logs. Interview line: “I’d know the pipeline broke before users do.”

### 8. CI/CD for the container

`ecr.tf` + custom image: workflow build → push ECR → deploy EC2 (SSM/SSH). Shows **artifact pipeline** ownership.

### 9. Testing beyond `DagBag`

Unit tests for transforms, mock CoinCap HTTP, one integration test in a test container. Mention coverage or “critical path tested.”

### 10. “Project highlights” for resume/LinkedIn

Example bullets:

- *Orchestrated CoinCap ELT on Airflow 3 (TaskFlow API) with branch-on-quality and Quarto reporting*
- *Provisioned AWS (ALB, WAF, EC2, CloudWatch) via Terraform; DNS/TLS via Cloudflare*
- *Dockerized stack with custom image, build metadata DAG, and release verification*

Add before/after metrics if possible (runtime, row counts, cost/month).

### Bonus framing

- **Rename clearly** — e.g. “CoinCap Analytics Platform” vs generic template name
- **3-minute Loom** — UI, DAG run, Terraform outputs, one quality-failure scenario
- **Pin versions** — Airflow 3.2, providers, Terraform lockfile

### Highest ROI

1. Green CI  
2. Your architecture diagram  
3. One real warehouse step  
4. Documented live deploy URL  
5. Resume bullets you can defend in an interview  

---

## Dynamic DAG creation

Pipelines are defined in **`dags/config/pipelines.yaml`** and materialized at parse time by **`dags/dynamic_coincap_dags.py`** (factory: **`dags/lib/coincap_factory.py`**).

| Config field | Purpose |
|--------------|---------|
| `id` | DAG suffix → `coincap_elt_<id>` |
| `endpoint` | CoinCap API path (`exchanges`, `assets`, `markets`) |
| `schedule` | Cron schedule per DAG |
| `quality_column` | Cuallee completeness column |
| `render_dashboard` | Run Quarto dashboard task (exchanges only today) |
| `enabled` | `false` skips DAG generation |

**Add a new feed:** append a pipeline block to `pipelines.yaml` and refresh the DAGs folder (no new `.py` file). Rebuild the image if you added Python dependencies (`PyYAML` is already in `requirements.txt`).

**Tests:** `tests/dags/test_dynamic_dags.py` asserts each enabled pipeline registers a DAG without import errors.

### SQL → DAG

Registry table `pipeline_config.pipelines` (seeded in `migrations/001_pipeline_registry.sql`) is read at parse time via `lib/pipeline_loader.py`. Set `pipeline_type` to `sql_transform` and `sql_file` to a path under `dags/sql/` to generate `sql_elt_<id>` DAGs without new Python.
