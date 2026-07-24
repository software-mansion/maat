# GCP Experiment Runners

Experiment partitions do not run on GitHub-hosted runners. Each partition gets a freshly created
GCP VM, runs there, and the VM is deleted when the partition finishes.

## Why

Ma'at reports [step timings](./timings.md) and compares them across Cairo versions, which only means
something if the hardware underneath is the same from run to run. GitHub-hosted runners give no CPU
model guarantee — the same workflow can land on different silicon on consecutive runs, and the
resulting timing differences are indistinguishable from real compiler regressions.

GCP machine families from the second generation onwards are each backed by a single CPU platform, so
pinning the machine type pins the CPU model. We use **C4 (Intel Emerald Rapids)**: it has the best
single-thread performance available, which is what the Cairo compiler is mostly bound by, and being
the newest Intel family it will stay in service the longest before a forced re-baseline.

Two settings matter as much as the family choice:

- **`--threads-per-core=1`** disables SMT. Hyperthread siblings contend for execution ports, and that
  contention is the largest source of run-to-run timing noise. This halves usable vCPU, hence
  `c4-standard-16` (16 vCPU → 8 physical cores) rather than an 8-vCPU shape.
- **One VM per partition.** Partitions sharing a VM would contend for CPU and page cache in a way
  that varies with how the work happens to interleave, and that noise looks exactly like a
  regression.

## Cost

VMs exist only for the duration of a partition, and GCP bills per second with a one-minute minimum.
An experiment costs roughly `partitions × duration × hourly rate`; check the pricing calculator for
the current `c4-standard-16` rate in your zone.

Two safeguards against paying for VMs nobody is using:

- The `Delete VM` step runs with `if: always()`, so it fires on failure as well as success.
- `--max-run-duration=6h --instance-termination-action=DELETE` makes GCP delete the VM server-side
  regardless. This is the one that matters: the teardown step cannot run if the workflow is
  cancelled or the runner dies, and `cancel-in-progress: true` makes cancellation routine. Raise the
  duration if experiments ever legitimately run longer than six hours, or they will be killed
  mid-run.

Spot VMs would be 60–90% cheaper but are not used: the `run` job is `fail-fast: true`, so a single
preemption discards the whole experiment. Worth revisiting alongside partition-level checkpointing.

## One-time project setup

### Workload Identity Federation

The workflow authenticates with WIF, so there are no long-lived service account keys in GitHub.
Create a pool and provider for the repository, and a service account for the workflow to impersonate.
See [`google-github-actions/auth`](https://github.com/google-github-actions/auth#setup) for the
current setup steps.

### Service account roles

Grant the service account:

| Role | Why |
| --- | --- |
| `roles/compute.instanceAdmin.v1` | Create and delete experiment VMs |
| `roles/compute.osAdminLogin` | SSH to the VM *with sudo* (the startup flow needs root) |
| `roles/iap.tunnelResourceAccessor` | Open the IAP SSH tunnel |

`roles/compute.osLogin` is not enough — the workflow runs `sudo usermod`, which needs the admin
variant.

### Network

Run once per project:

```shell
ZONE=europe-west4-a scripts/gcp/setup-network.sh
```

This creates the isolated network the VMs run in. See [Network isolation](#network-isolation) for
what it builds and why.

### Repository variables

Set under *Settings → Secrets and variables → Actions → Variables*:

| Variable | Required | Description |
| --- | --- | --- |
| `GCP_WIF_PROVIDER` | yes | Full workload identity provider resource name |
| `GCP_SERVICE_ACCOUNT` | yes | Service account email the workflow impersonates |
| `GCP_ZONE` | yes | Zone to create VMs in, e.g. `europe-west4-a` |
| `GCP_MACHINE_TYPE` | no | Defaults to `c4-standard-16` |
| `GCP_NETWORK` | no | Defaults to `maat-net` |
| `GCP_SUBNET` | no | Defaults to `maat-subnet` |
| `EXPECTED_CPU_MODEL` | no | Pins the CPU model; see below |

Check C4 availability in your zone before picking one — it is not in every region yet:

```shell
gcloud compute machine-types list --filter="name=c4-standard-16 AND zone~'europe-west'"
```

If C4 is unavailable, **C3** (Intel Sapphire Rapids) is the fallback: wider zone coverage, also a
single-CPU family, slightly older.

## Network isolation

Experiment VMs run arbitrary third-party code. Every package Ma'at builds comes from the Cairo
ecosystem, and `scarb build` executes build scripts and procedural macros from those packages. Treat
a VM as hostile and keep it away from anything else in the project.

`scripts/gcp/setup-network.sh` builds the boundary. It is enforced in four independent places, so no
single mistake opens it up:

| Layer | Effect |
| --- | --- |
| Dedicated custom-mode VPC (`maat-net`) | VPCs do not route to one another unless peered. Nothing on this network can reach the default network, or any other, over internal IPs. |
| Egress deny for `10/8`, `172.16/12`, `192.168/16` | VMs cannot reach *any* internal address — including each other, and including anything that would become reachable if this VPC were ever peered by mistake. |
| Ingress from `35.235.240.0/20` only | Only IAP can connect in, and IAP authenticates before forwarding. Everything else is denied. |
| `--no-service-account --no-scopes` | The VM holds no GCP credentials, so it cannot call the API even for resources it could route to. |

The egress deny covers the VM's own subnet, so the four partition VMs cannot see each other either.
That is deliberate: partitions are meant to be independent, and it removes a route for one
compromised build to affect another's timings.

Two constraints to preserve if you edit any of this:

- **Never peer `maat-net`**, and never attach a Cloud Router, VPN, or Interconnect to it. Peering is
  what would make the layer-1 guarantee moot; the egress deny is what stops that being fatal.
- **Do not enable Private Google Access** on the subnet. The VMs have no service account and no
  business reaching the GCP API.

Egress to the metadata server (`169.254.169.254`) is permitted by GCP regardless of firewall rules,
which is what lets OS Login and the startup script work. It exposes nothing here — with no service
account attached, the metadata server holds no tokens to steal.

### What this does not cover

**The VMs still have public internet egress, and that is not fully closable.** A run has to pull the
sandbox image from ghcr.io and dependencies from crates.io and the Scarb registry, all of which are
CDN-backed with addresses that cannot be sensibly allowlisted. So:

- Nothing you run on **internal IPs** is reachable from an experiment VM. This is the guarantee, and
  it holds.
- Anything you expose on a **public IP** is reachable from an experiment VM *exactly as it is from
  any host on the internet* — no more, but no less. If you have a public load balancer, a Cloud SQL
  instance with a public IP, or an API gateway, an experiment VM can send packets to it. It has no
  credentials and no privileged network position, so it is an anonymous internet client, but it is
  not blocked.

If that residual exposure matters, the options are, roughly in order of cost:

1. Restrict your public endpoints by source IP, and give the experiment VMs a fixed egress IP via
   Cloud NAT so they can be excluded.
2. Replace internet egress with an HTTP proxy on an allowlist of registry hosts, add `--no-address`,
   and point Docker and Scarb at the proxy. This is the real fix, and it is a project of its own —
   the registries redirect to CDNs, so the allowlist is not short.
3. Run experiments in a separate GCP project entirely, which turns quota and IAM into a boundary too.

Option 3 is the one worth considering if this ever holds anything sensitive; the current setup is
sized for "keep third-party build scripts away from our infrastructure", which it does.

### Verifying the boundary

The firewall rules have not been exercised against a live project. On the first run, confirm from a
VM that internal egress is actually dead — a deny rule with a typo'd range fails open and looks
identical to a working one until someone checks:

```shell
gcloud compute ssh maat-debug --zone="$ZONE" --tunnel-through-iap

# Should all hang and time out:
curl -sS --max-time 5 http://10.0.0.1/ ; echo "exit=$?"
nc -zv -w 5 10.128.0.2 22 ; echo "exit=$?"
# Pick a real internal IP from your default network for a meaningful test:
nc -zv -w 5 <internal-ip-of-something-you-run> 22 ; echo "exit=$?"

# Should succeed (the run depends on it):
curl -sS --max-time 10 -o /dev/null -w '%{http_code}\n' https://ghcr.io/v2/

# Should fail -- no service account is attached:
curl -sS --max-time 5 -H 'Metadata-Flavor: Google' \
  http://169.254.169.254/computeMetadata/v1/instance/service-accounts/ ; echo "exit=$?"
```

You can also check reachability without a VM using Connectivity Tests, which evaluates the rules
rather than the live path:

```shell
gcloud network-management connectivity-tests create maat-isolation-check \
  --source-instance="projects/$PROJECT/zones/$ZONE/instances/maat-debug" \
  --destination-instance="projects/$PROJECT/zones/$ZONE/instances/<some-other-vm>" \
  --protocol=TCP --destination-port=22
```

Expect a `UNREACHABLE` result with the drop attributed to the egress deny rule.

## Pinning the CPU model

`scripts/gcp/assert-cpu.sh` runs on each VM before the partition starts. It prints the CPU the VM
actually landed on, and fails the run if it is not the expected one — a wrong CPU makes every timing
in the report meaningless, and losing the run beats publishing a phantom regression.

`EXPECTED_CPU_MODEL` is unset initially, in which case the guard only observes and warns. To pin it:

1. Run an experiment.
2. Find `cpu model:` in the *Verify the VM landed on the expected CPU* step's log.
3. Set `EXPECTED_CPU_MODEL` to that exact string.

It is deliberately not hardcoded — the model string is a property of the fleet in your zone, not
something to guess at.

The guard also fails if SMT is enabled, which catches a machine type that silently ignored
`--threads-per-core=1`.

## Noise floor

Ephemeral VMs land on a different physical host every run, with different neighbours. Pinning the
machine type fixes the CPU model but not the contention, so expect a few percent of run-to-run drift
even with everything above in place. Eliminating that would need a sole-tenant node, which bills
around the clock and defeats the purpose of ephemeral VMs.

For detecting compiler regressions this is fine — the question is "did this step get 40% slower", not
2%. Just don't read small timing deltas as signal.

## Local SSD

`scripts/gcp/startup.sh` puts Docker's data root on local SSD when the machine type provides one
(any `*-lssd` shape), striping across devices if there are several. Step timings include container
start and cache population, so disk latency variance lands directly in the compared numbers.

The default `c4-standard-16` has no local SSD and the script falls back to the boot disk. To use one,
set `GCP_MACHINE_TYPE` to the `-lssd` variant — verify the exact shape name and its availability in
your zone first, as C4 local SSD shapes are not offered everywhere.

## Debugging a VM

VMs are deleted on failure. To keep one alive, re-run the workflow with the `Delete VM` step disabled,
or create one by hand:

```shell
gcloud compute instances create maat-debug \
  --zone="$ZONE" \
  --machine-type=c4-standard-16 \
  --threads-per-core=1 \
  --image-family=ubuntu-2404-lts-amd64 \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=200GB \
  --boot-disk-type=hyperdisk-balanced \
  --network=maat-net \
  --subnet=maat-subnet \
  --tags=maat-runner \
  --metadata=enable-oslogin=TRUE \
  --metadata-from-file=startup-script=scripts/gcp/startup.sh \
  --no-service-account --no-scopes \
  --max-run-duration=2h \
  --instance-termination-action=DELETE

gcloud compute ssh maat-debug --zone="$ZONE" --tunnel-through-iap
```

Keep `--max-run-duration` on debug VMs too, so a forgotten one reaps itself.

Startup script output goes to the serial console:

```shell
gcloud compute instances get-serial-port-output maat-debug --zone="$ZONE"
```

To find VMs a broken run left behind:

```shell
gcloud compute instances list --filter="labels.maat-run:*"
```

## Possible improvements

- **Custom image.** Every VM currently spends 2–3 minutes installing Docker and uv, and that setup
  varies with apt mirror weather. Baking an image would cut it to boot time.
- **Record the CPU model in the report.** The guard checks the CPU but the report does not carry it,
  so a report cannot be audited after the fact for what it ran on.
