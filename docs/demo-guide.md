# CloudDeploy Monitor: Live Demo Guide

A step-by-step script for presenting the project. Allow about 15 minutes.

| Item | Value |
|---|---|
| Live app | http://54.210.44.15 |
| Health check | http://54.210.44.15/health |
| Status API | http://54.210.44.15/api/status |
| GitHub repo | https://github.com/sagniksannigrahi/clouddeploy-monitor |
| Pipeline runs | https://github.com/sagniksannigrahi/clouddeploy-monitor/actions |
| SSH | `ssh -i ~/Downloads/CloudDeploy-Deploy-Key.pem ubuntu@54.210.44.15` |

---

## 0. Before the demo (10 minutes earlier)

1. **AWS Academy:** start the lab and make sure the instance `CloudDeploy-Monitor` is **Running**.
   - If it was stopped, the **public IP has changed**. Update the `EC2_HOST` and `EC2_KNOWN_HOSTS` GitHub secrets (README section 13), the UptimeRobot URL, and the links in this guide.
2. **Network:** use Wi-Fi that allows SSH and plain HTTP. Some college networks block port 22 and intercept port 80. A phone hotspot works. Quick check:
   ```bash
   nc -z -G 5 54.210.44.15 22 && echo "SSH reachable"
   curl -s http://54.210.44.15/health
   ```
3. Open these browser tabs: the live app, GitHub Actions, UptimeRobot dashboard, and your email inbox.
4. Open the project in VS Code with a terminal in the project folder.

---

## 1. Introduce the problem (1 min)

> "Deploying by hand is slow and risky: people skip tests, ship broken code, and only notice outages when users complain. This project automates the whole path from code to a monitored cloud server, using free tools and a single t3.micro EC2 instance."

Show the architecture diagram in `README.md` (VS Code: right-click → *Open Preview*).

---

## 2. Show the live application (2 min)

Open **http://54.210.44.15**.

**Point out:**

- **Application health:** the green dot comes from a live `GET /health` call that the page repeats every 30 s.
- **Deployment status:** the commit hash and "Deployed by GitHub Actions".
- **Cloud infrastructure:** AWS EC2, us-east-1, t3.micro, Ubuntu 26.04. The app reads these from EC2 instance metadata; none of them are hard-coded.
- **CI/CD pipeline:** the 6 stages.

Then open the APIs:

```bash
curl http://54.210.44.15/health
```
Expected:
```json
{"application":"CloudDeploy Monitor","status":"healthy"}
```

```bash
curl -s http://54.210.44.15/api/status | python3 -m json.tool
```
Expected: `"platform": "AWS EC2"`, `"instance_type": "t3.micro"`, the current `"commit"`, and `"uptime_seconds"`. There are no IPs, instance IDs or secrets.

---

## 3. Show the code and tests (2 min)

In VS Code, briefly show `app.py` (three routes), `Dockerfile` and `deploy.sh`.

```bash
source .venv/bin/activate
pytest -v
```
Expected: **`15 passed`**.

---

## 4. Show the server (2 min)

```bash
ssh -i ~/Downloads/CloudDeploy-Deploy-Key.pem ubuntu@54.210.44.15
```

On the server:

```bash
docker ps
```
Expected: one container `clouddeploy-monitor`, status `Up ... (healthy)`, ports `0.0.0.0:80->8080/tcp`.

```bash
docker logs --tail 10 clouddeploy-monitor     # Gunicorn access logs
docker stats --no-stream                       # memory well under the 300 MB limit
docker inspect clouddeploy-monitor --format '{{.HostConfig.RestartPolicy.Name}}'   # unless-stopped
free -h && df -h /                             # small footprint on a t3.micro
ls /opt/clouddeploy/app                        # where deployments are unpacked
exit
```

> "Port 80 is public. Gunicorn's port 8080 is only reachable inside Docker, not from the internet."

---

## 5. Demonstrate automated deployment (4 min)

This is the key part of the demo. Make a visible change and push it:

```bash
# Change the version number shown by the status API
sed -i '' 's/APP_VERSION = "1.0.0"/APP_VERSION = "1.1.0"/' app.py
pytest -q                       # still passes
git commit -am "Bump version to 1.1.0 for demo"
git push
```

Switch to the **GitHub → Actions** tab and open the new run:

| Job | What to say | Typical time |
|---|---|---|
| Run tests | "pytest runs on a fresh GitHub server." | ~20 s |
| Build and test Docker image | "The image is built and `/health` is checked inside the container." | ~40 s |
| Deploy to AWS EC2 | "The code is packaged, copied with **SCP**, then over **SSH** the server rebuilds the image, swaps the container, and health-checks it. The host key is verified, so it can't be tricked by a fake server." | ~1–2 min |

When the run is green, refresh the app or run:

```bash
curl -s http://54.210.44.15/api/status | python3 -m json.tool | grep -E '"version"|"commit"|"deployed_by"'
```
Expected: `"version": "1.1.0"`, the new commit hash, and `"deployed_by": "GitHub Actions"`.

### Optional: show that a failing test blocks deployment

```bash
sed -i '' 's/"status": "healthy",$/"status": "BROKEN",/' test_app.py   # make a test fail
git commit -am "Demo: failing test" && git push
```
In Actions, **Run tests** goes red and **Build** and **Deploy** are skipped. The live site is unchanged. Undo it:

```bash
git revert --no-edit HEAD && git push
```

### Optional: explain automatic rollback

`deploy.sh` keeps the previous image. If the new container fails its health check within 40 seconds, the script removes it, restarts the previous version, and fails the pipeline. This was tested locally with a deliberately broken `/health`.

---

## 6. Demonstrate monitoring and downtime recovery (4 min, plus waiting)

Open the UptimeRobot dashboard and show the monitor `CloudDeploy Monitor` (HTTP(s), `http://54.210.44.15/health`, 5-minute interval). Show its uptime %, response time graph and history.

**Simulate an outage:**

```bash
ssh -i ~/Downloads/CloudDeploy-Deploy-Key.pem ubuntu@54.210.44.15 "docker stop clouddeploy-monitor"
curl -m 5 http://54.210.44.15/health     # → connection refused
```

> "I use `docker stop` because the restart policy would bring a crashed container straight back. Stopping it on purpose simulates a real outage."

Within **5–10 minutes**, UptimeRobot marks the monitor **Down** and sends an email. Show both. Continue the presentation or take questions while you wait.

**Recover:**

```bash
ssh -i ~/Downloads/CloudDeploy-Deploy-Key.pem ubuntu@54.210.44.15 "docker start clouddeploy-monitor"
curl http://54.210.44.15/health          # → healthy again
```

At the next check, the monitor goes **Up** and an "Up" email arrives. The incident, with its duration, now appears in the monitor history.

**Show self-healing (optional):**

```bash
ssh -i ~/Downloads/CloudDeploy-Deploy-Key.pem ubuntu@54.210.44.15 \
  "docker kill --signal=KILL clouddeploy-monitor; sleep 5; docker ps --format '{{.Names}} {{.Status}}'"
```
The container is killed and Docker restarts it automatically (`--restart unless-stopped`).

---

## 7. Wrap-up (30 s)

> "Every push to main is tested, containerised, deployed to EC2 over a verified SSH connection, health-checked with automatic rollback, and monitored with email alerts, all on free tools and one t3.micro instance."

---

## Viva questions and answers

**1. What is CI/CD?**
Continuous Integration means every change is automatically built and tested. Continuous Deployment means every change that passes is automatically released. Here, GitHub Actions does both on every push to `main`.

**2. Why Docker instead of running Python directly on EC2?**
The container packages the exact Python version and dependencies, so it runs the same on a laptop, in GitHub Actions and on EC2. It also isolates the app from the OS and makes replacing a version a single command.

**3. Why Gunicorn and not `flask run`?**
Flask's built-in server is for development only: it is single-process and not hardened. Gunicorn is a production WSGI server that runs multiple worker processes.

**4. How does GitHub Actions log in to EC2 securely?**
With SSH key authentication. The private key is stored as an encrypted GitHub Secret (`EC2_SSH_KEY`), written to the runner only during the job and deleted afterwards. The server's host key is pinned in `EC2_KNOWN_HOSTS` and `StrictHostKeyChecking yes` is set, so SSH refuses to connect to an impostor. Password login is disabled on the server.

**5. Why is SSH open to 0.0.0.0/0? Isn't that insecure?**
GitHub-hosted runners use thousands of changing IP addresses, so the port can't be limited to one IP. The risk is reduced because only key-based login is accepted, root can't log in with a password, and password authentication is off. Improvements would be a self-hosted runner, AWS SSM, or a VPN.

**6. What happens if a test fails?**
The `test` job fails. `docker` and `deploy` depend on it (`needs:`), so they are skipped and nothing reaches the server.

**7. What happens if the new version crashes on the server?**
`deploy.sh` checks `/health` for up to 40 s. If it fails, the script removes the new container, restarts the previous image, and exits with an error so the pipeline turns red.

**8. What is the purpose of `/health`?**
It's a cheap endpoint that monitoring tools and the deploy script call to confirm the app is up. It returns HTTP 200 with `{"status": "healthy"}`.

**9. Difference between `/health` and `/api/status`?**
`/health` is minimal and fast, for machines. `/api/status` gives details for humans (version, commit, region, uptime) but excludes secrets, IPs and instance IDs.

**10. What does `--restart unless-stopped` do?**
Docker restarts the container if it crashes or the server reboots, unless an administrator stopped it on purpose.

**11. Why port 80 outside and 8080 inside?**
Port 80 is the standard HTTP port, so users don't type a port number. Inside the container, the app runs as a non-root user, which can't bind to ports below 1024, so it uses 8080. Docker maps 80 to 8080.

**12. How does UptimeRobot detect downtime?**
It sends an HTTP request to `/health` every 5 minutes from its own servers. A non-2xx/3xx response or a timeout marks the monitor down and triggers an email. A successful check afterwards marks it up again.

**13. What would you improve with more time?**
HTTPS with a domain and Let's Encrypt; building the image once in CI and pushing it to a registry; zero-downtime blue/green deploys; Slack alerts; a dedicated, revocable deploy key.

**14. What does the project cost?**
Everything is free except the EC2 instance, which uses AWS Academy credits while running. No Elastic IP, load balancer or NAT gateway is used. Old Docker images are cleaned up automatically to save disk space.

**15. Why does the public IP change, and how would you fix it?**
Without an Elastic IP, AWS assigns a new public IP each time the instance starts. An Elastic IP or a domain name would fix this. We avoided an Elastic IP here to save AWS credits.
